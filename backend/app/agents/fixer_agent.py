from __future__ import annotations

import ast
import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Tuple

from app.agents.base_agent import BaseAgent
from app.core.logger import logger
from app.services.llm.router import LLMRouter
from app.memory.memory_manager import MemoryManager
from app.project.project_context import ProjectContext


class FixerAgent(BaseAgent):
    """
    Autonomous software repair agent.

    The Fixer receives an existing source project, analyzes the
    failure information, asks an LLM to repair the project, and
    returns the complete repaired SOURCE project.

    Runtime/debug artifacts are never considered source files.

    Important protection:

    If the LLM accidentally removes a Python import while the
    imported symbol is still used, the Fixer automatically
    restores that import before returning the repaired project.

    Example:

        Original:

            from app import add

            def test_add():
                assert add(2, 3) == 5

        Bad LLM response:

            def test_add():
                assert add(2, 3) == 5

        Fixer automatically restores:

            from app import add

            def test_add():
                assert add(2, 3) == 5
    """

    MIN_RESPONSE_LENGTH = 50
    MAX_FILE_PATH_LENGTH = 250
    MAX_FILES = 150

    MIN_SIZE_RATIO = 0.2
    MIN_ORIGINAL_SIZE_TO_CHECK = 200

    # ==========================================================
    # FORBIDDEN FILES
    # ==========================================================

    FORBIDDEN_PATH_PATTERNS = (
        ".env",
        ".env.local",
        ".env.production",
        ".env.development",
        ".pem",
        ".key",
        "id_rsa",
        "id_ed25519",
        "__pycache__",
        ".pyc",
        "node_modules",
        ".git/",
    )

    # ==========================================================
    # RUNTIME / DEBUG ARTIFACTS
    # ==========================================================

    RUNTIME_ARTIFACT_PATH_PATTERNS = (
        "execution/",
        "history/",
        ".autodev_debug/",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        "coverage/",
        "dist/",
        "build/",
        ".tox/",
        ".venv/",
        "venv/",
    )

    # ==========================================================
    # CRITICAL FILES
    # ==========================================================

    CRITICAL_FILE_NAMES = (
        "requirements.txt",
        "package.json",
        "pyproject.toml",
        "Pipfile",
        "go.mod",
        "Cargo.toml",
    )

    # ==========================================================
    # ENTRY POINTS
    # ==========================================================

    ENTRY_POINTS_BY_PROJECT_TYPE = {
        "python": (
            "main.py",
        ),
        "fastapi": (
            "app.py",
            "main.py",
        ),
        "node": (
            "package.json",
        ),
        "express": (
            "package.json",
        ),
        "react": (
            "package.json",
            "src/App.jsx",
            "src/App.tsx",
        ),
    }

    # ==========================================================
    # PLACEHOLDER DETECTION
    # ==========================================================

    PLACEHOLDER_PATTERNS = (
        re.compile(
            r"#\s*remaining\s+(code|implementation)",
            re.IGNORECASE,
        ),
        re.compile(
            r"//\s*remaining\s+(code|implementation)",
            re.IGNORECASE,
        ),
        re.compile(
            r"#\s*omitted",
            re.IGNORECASE,
        ),
        re.compile(
            r"//\s*omitted",
            re.IGNORECASE,
        ),
        re.compile(
            r"#\s*rest of the code",
            re.IGNORECASE,
        ),
        re.compile(
            r"//\s*rest of the code",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*\.\.\.\s*$",
            re.MULTILINE,
        ),
        re.compile(
            r"\bTODO\b",
        ),
        re.compile(
            r"\bFIXME\b",
        ),
        re.compile(
            r"remaining implementation",
            re.IGNORECASE,
        ),
    )

    # ==========================================================
    # LANGUAGE LABELS
    # ==========================================================

    LANGUAGE_PATTERN = re.compile(
        r"(?m)"
        r"^(FILE:\s*[^\r\n]+)"
        r"(\r?\n)"
        r"(python|py|javascript|js|typescript|ts|"
        r"json|html|css|java|cpp|c\+\+|c|"
        r"bash|shell|sh|yaml|yml|markdown|md|"
        r"text|plaintext)"
        r"(\r?\n)",
        flags=re.IGNORECASE,
    )

    # ==========================================================
    # FILE BLOCKS
    # ==========================================================

    FILE_PATTERN = re.compile(
        r"(?m)^FILE:\s*(.+?)\s*$"
    )

    CODE_FENCE_LINE = re.compile(
        r"(?m)^[ \t]*```[\w+-]*[ \t]*$"
    )

    # ==========================================================
    # INIT
    # ==========================================================

    def __init__(self, llm=None):
        super().__init__()

        self.llm = llm or LLMRouter.get_llm()

        self.project_context = ProjectContext()

    # ==========================================================
    # BASIC HELPERS
    # ==========================================================

    @staticmethod
    def _to_text(value) -> str:
        """
        Convert arbitrary values into readable text.
        """

        if value is None:
            return ""

        if isinstance(value, dict):
            return json.dumps(
                value,
                indent=2,
                ensure_ascii=False,
            )

        if isinstance(value, list):
            try:
                return json.dumps(
                    value,
                    indent=2,
                    ensure_ascii=False,
                )
            except Exception:
                return "\n".join(
                    str(item)
                    for item in value
                )

        return str(value)

    @staticmethod
    def _extract_category(execution_error) -> str:
        """
        Extract error category from execution report.
        """

        if isinstance(execution_error, dict):
            return execution_error.get(
                "category",
                "Unknown",
            )

        return "Unknown"

    @staticmethod
    def _normalize_path_key(path: str) -> str:
        """
        Normalize paths for comparison.
        """

        normalized = (
            path
            .replace("\\", "/")
            .strip()
        )

        if normalized.startswith("./"):
            normalized = normalized[2:]

        return PurePosixPath(
            normalized
        ).as_posix().lower()

    # ==========================================================
    # RUNTIME ARTIFACT DETECTION
    # ==========================================================

    def _is_runtime_artifact_path(
        self,
        path: str,
    ) -> bool:
        """
        Determine whether a path belongs to runtime/debug data.
        """

        normalized = (
            path
            .replace("\\", "/")
            .strip()
            .lower()
        )

        if normalized.startswith("./"):
            normalized = normalized[2:]

        for pattern in self.RUNTIME_ARTIFACT_PATH_PATTERNS:

            if normalized.startswith(pattern):
                return True

        return False

    # ==========================================================
    # RESPONSE NORMALIZATION
    # ==========================================================

    def _normalize_response(
        self,
        response: str,
    ) -> str:
        """
        Normalize LLM response into FILE blocks.
        """

        response = response.strip()

        response = self.CODE_FENCE_LINE.sub(
            "",
            response,
        )

        response = response.strip()

        first = response.find("FILE:")

        if first == -1:
            raise RuntimeError(
                "Repair response contains no FILE blocks."
            )

        if first > 0:

            logger.warning(
                "Discarding text before first FILE block."
            )

            response = response[first:]

        response = self._remove_language_labels(
            response
        )

        return response.strip()

    # ==========================================================
    # LANGUAGE LABEL REMOVAL
    # ==========================================================

    def _remove_language_labels(
        self,
        response: str,
    ) -> str:
        """
        Remove accidental language labels after FILE lines.
        """

        return self.LANGUAGE_PATTERN.sub(
            r"\1\2\4",
            response,
        )

    # ==========================================================
    # EXTRACT FILE BLOCKS
    # ==========================================================

    def _extract_file_blocks(
        self,
        response: str,
    ) -> List[Tuple[str, str]]:
        """
        Extract FILE blocks from LLM response.
        """

        matches = list(
            self.FILE_PATTERN.finditer(
                response
            )
        )

        if not matches:
            return []

        files: List[Tuple[str, str]] = []

        for index, match in enumerate(matches):

            path = match.group(1).strip()

            start = match.end()

            if index + 1 < len(matches):
                end = matches[index + 1].start()
            else:
                end = len(response)

            content = (
                response[start:end]
                .replace("\r\n", "\n")
                .strip()
            )

            files.append(
                (
                    path,
                    content,
                )
            )

        return files

    # ==========================================================
    # BUILD FILE BLOCK RESPONSE
    # ==========================================================

    @staticmethod
    def _build_file_blocks(
        files: List[Tuple[str, str]],
    ) -> str:
        """
        Convert file tuples back into FILE blocks.
        """

        blocks = []

        for path, content in files:

            blocks.append(
                f"FILE: {path}\n\n{content.strip()}"
            )

        return "\n\n".join(blocks)

    # ==========================================================
    # FILTER SOURCE PROJECT
    # ==========================================================

    def _filter_source_project(
        self,
        code: str,
    ) -> str:
        """
        Remove runtime/debug artifacts before sending the project
        to the LLM.
        """

        try:

            blocks = self._extract_file_blocks(
                code
            )

        except Exception:

            logger.exception(
                "Failed to parse source project."
            )

            return code

        if not blocks:
            return code

        source_blocks: List[str] = []

        for path, content in blocks:

            if self._is_runtime_artifact_path(
                path
            ):

                logger.debug(
                    "Excluding runtime artifact "
                    "from fixer prompt: %s",
                    path,
                )

                continue

            source_blocks.append(
                f"FILE: {path}\n\n{content}"
            )

        if not source_blocks:
            return ""

        return "\n\n".join(
            source_blocks
        )

    # ==========================================================
    # ORIGINAL FILES
    # ==========================================================

    def _extract_original_files(
        self,
        code: str,
    ) -> Dict[str, str]:
        """
        Extract original source files.
        """

        try:

            blocks = self._extract_file_blocks(
                code
            )

        except Exception:

            return {}

        result: Dict[str, str] = {}

        for path, content in blocks:

            if self._is_runtime_artifact_path(
                path
            ):
                continue

            result[
                self._normalize_path_key(path)
            ] = content

        return result

    # ==========================================================
    # PATH VALIDATION
    # ==========================================================

    def _validate_file_path(
        self,
        path: str,
    ) -> None:
        """
        Validate generated source file paths.
        """

        if not path:

            raise RuntimeError(
                "Generated file path is empty."
            )

        if self._is_runtime_artifact_path(
            path
        ):

            raise RuntimeError(
                "Runtime/generated artifact cannot be "
                f"returned by Fixer Agent: {path}"
            )

        if len(path) > self.MAX_FILE_PATH_LENGTH:

            raise RuntimeError(
                f"File path too long: {path}"
            )

        normalized = (
            path
            .replace("\\", "/")
            .strip()
        )

        if normalized.startswith("/"):

            raise RuntimeError(
                f"Absolute path not allowed: {path}"
            )

        if re.match(
            r"^[A-Za-z]:",
            normalized,
        ):

            raise RuntimeError(
                f"Windows absolute path not allowed: {path}"
            )

        parts = normalized.split("/")

        if ".." in parts:

            raise RuntimeError(
                f"Directory traversal detected: {path}"
            )

        if any(
            part.strip() == ""
            for part in parts
        ):

            raise RuntimeError(
                f"Invalid path: {path}"
            )

        lower = normalized.lower()

        for forbidden in self.FORBIDDEN_PATH_PATTERNS:

            if forbidden in lower:

                raise RuntimeError(
                    f"Forbidden path generated: {path}"
                )

    # ==========================================================
    # PLACEHOLDER VALIDATION
    # ==========================================================

    def _check_placeholder_content(
        self,
        path: str,
        content: str,
    ) -> None:
        """
        Reject incomplete source files.
        """

        for pattern in self.PLACEHOLDER_PATTERNS:

            if pattern.search(content):

                raise RuntimeError(
                    f"Generated file '{path}' contains "
                    "placeholder content instead of a real "
                    f"implementation "
                    f"(matched: {pattern.pattern!r})."
                )

    # ==========================================================
    # SUSPICIOUS SHRINKAGE
    # ==========================================================

    def _check_suspicious_shrinkage(
        self,
        path: str,
        content: str,
        original_files: Dict[str, str],
    ) -> None:
        """
        Prevent accidental replacement of large source files
        with tiny responses.
        """

        original = original_files.get(
            self._normalize_path_key(path)
        )

        if original is None:
            return

        original_len = len(
            original.strip()
        )

        if original_len < self.MIN_ORIGINAL_SIZE_TO_CHECK:
            return

        new_len = len(
            content.strip()
        )

        if new_len < (
            original_len
            * self.MIN_SIZE_RATIO
        ):

            raise RuntimeError(
                f"Generated file '{path}' shrank "
                f"suspiciously "
                f"({original_len} -> {new_len} chars)."
            )

    # ==========================================================
    # CRITICAL FILES
    # ==========================================================

    def _check_critical_files_preserved(
        self,
        generated_keys: set,
        original_files: Dict[str, str],
    ) -> None:
        """
        Ensure dependency/configuration files remain.
        """

        for name in self.CRITICAL_FILE_NAMES:

            key = self._normalize_path_key(
                name
            )

            if (
                key in original_files
                and key not in generated_keys
            ):

                raise RuntimeError(
                    f"Critical file '{name}' existed "
                    "in the original project but is "
                    "missing from the repair."
                )

    # ==========================================================
    # ENTRY POINTS
    # ==========================================================

    def _check_entry_points_preserved(
        self,
        project_type: Optional[str],
        generated_keys: set,
        original_files: Dict[str, str],
    ) -> None:
        """
        Ensure expected startup files remain.
        """

        if not project_type:
            return

        expected = (
            self.ENTRY_POINTS_BY_PROJECT_TYPE.get(
                project_type.lower()
            )
        )

        if not expected:
            return

        for entry_point in expected:

            key = self._normalize_path_key(
                entry_point
            )

            if (
                key in original_files
                and key not in generated_keys
            ):

                raise RuntimeError(
                    f"Entry point '{entry_point}' existed "
                    f"in the original {project_type} "
                    "project but is missing from the repair."
                )

    # ==========================================================
    # PYTHON IMPORT ANALYSIS
    # ==========================================================

    @staticmethod
    def _get_python_import_lines(
        source: str,
    ) -> List[str]:
        """
        Return original Python import statements.

        AST is used to identify import statements while the
        original source lines are preserved exactly.
        """

        try:

            tree = ast.parse(
                source
            )

        except SyntaxError:

            return []

        lines = source.splitlines()

        imports: List[str] = []

        for node in ast.walk(tree):

            if isinstance(
                node,
                (
                    ast.Import,
                    ast.ImportFrom,
                ),
            ):

                start = node.lineno - 1

                end = getattr(
                    node,
                    "end_lineno",
                    node.lineno,
                )

                statement = "\n".join(
                    lines[start:end]
                ).strip()

                if statement:
                    imports.append(
                        statement
                    )

        return imports

    # ==========================================================
    # PYTHON IMPORTED SYMBOLS
    # ==========================================================

    @staticmethod
    def _get_imported_names(
        source: str,
    ) -> Dict[str, str]:
        """
        Map imported Python names to their original import
        statements.

        Example:

            from app import add

        becomes:

            {
                "add": "from app import add"
            }
        """

        try:

            tree = ast.parse(
                source
            )

        except SyntaxError:

            return {}

        lines = source.splitlines()

        result: Dict[str, str] = {}

        for node in ast.walk(tree):

            if isinstance(
                node,
                (
                    ast.Import,
                    ast.ImportFrom,
                ),
            ):

                start = node.lineno - 1

                end = getattr(
                    node,
                    "end_lineno",
                    node.lineno,
                )

                statement = "\n".join(
                    lines[start:end]
                ).strip()

                if not statement:
                    continue

                if isinstance(
                    node,
                    ast.Import,
                ):

                    for alias in node.names:

                        bound_name = (
                            alias.asname
                            or alias.name.split(".")[0]
                        )

                        result[
                            bound_name
                        ] = statement

                elif isinstance(
                    node,
                    ast.ImportFrom,
                ):

                    for alias in node.names:

                        if alias.name == "*":
                            continue

                        bound_name = (
                            alias.asname
                            or alias.name
                        )

                        result[
                            bound_name
                        ] = statement

        return result

    # ==========================================================
    # PYTHON USED NAMES
    # ==========================================================

    @staticmethod
    def _get_python_used_names(
        source: str,
    ) -> set:
        """
        Return names referenced by a Python source file.
        """

        try:

            tree = ast.parse(
                source
            )

        except SyntaxError:

            return set()

        used = set()

        for node in ast.walk(tree):

            if isinstance(
                node,
                ast.Name,
            ):

                if isinstance(
                    node.ctx,
                    ast.Load,
                ):

                    used.add(
                        node.id
                    )

        return used

    # ==========================================================
    # CHECK MISSING PYTHON IMPORTS
    # ==========================================================

    def _find_missing_python_imports(
        self,
        original: str,
        repaired: str,
    ) -> List[str]:
        """
        Find imports that disappeared from the repaired file
        while the imported symbol is still used.

        This specifically prevents the failure seen in:

            from app import add

            def test_add():
                assert add(2, 3) == 5

        becoming:

            def test_add():
                assert add(2, 3) == 5
        """

        original_imports = (
            self._get_imported_names(
                original
            )
        )

        if not original_imports:
            return []

        used_names = (
            self._get_python_used_names(
                repaired
            )
        )

        try:

            repaired_tree = ast.parse(
                repaired
            )

        except SyntaxError:

            # Syntax validation will report this separately.
            return []

        repaired_import_names = set()

        for node in ast.walk(
            repaired_tree
        ):

            if isinstance(
                node,
                ast.Import,
            ):

                for alias in node.names:

                    repaired_import_names.add(
                        alias.asname
                        or alias.name.split(".")[0]
                    )

            elif isinstance(
                node,
                ast.ImportFrom,
            ):

                for alias in node.names:

                    if alias.name != "*":

                        repaired_import_names.add(
                            alias.asname
                            or alias.name
                        )

        missing = []

        for name, statement in (
            original_imports.items()
        ):

            if (
                name in used_names
                and name not in repaired_import_names
            ):

                missing.append(
                    statement
                )

        return list(
            dict.fromkeys(
                missing
            )
        )

    # ==========================================================
    # RESTORE MISSING PYTHON IMPORTS
    # ==========================================================

    def _restore_missing_python_imports(
        self,
        original: str,
        repaired: str,
        path: str,
    ) -> str:
        """
        Restore Python imports that were accidentally removed
        while their symbols are still being used.

        Only Python files are processed.
        """

        if not path.lower().endswith(".py"):
            return repaired

        missing_imports = (
            self._find_missing_python_imports(
                original,
                repaired,
            )
        )

        if not missing_imports:
            return repaired

        logger.warning(
            "Restoring %d missing Python import(s) "
            "in repaired file: %s",
            len(missing_imports),
            path,
        )

        for statement in reversed(
            missing_imports
        ):

            repaired = (
                statement
                + "\n\n"
                + repaired.lstrip()
            )

        return repaired

    # ==========================================================
    # PYTHON SYNTAX VALIDATION
    # ==========================================================

    def _validate_python_syntax(
        self,
        path: str,
        content: str,
    ) -> None:
        """
        Validate Python syntax before accepting the repair.
        """

        if not path.lower().endswith(".py"):
            return

        try:

            ast.parse(
                content,
                filename=path,
            )

        except SyntaxError as exc:

            raise RuntimeError(
                f"Generated Python file '{path}' "
                f"contains invalid syntax: {exc}"
            ) from exc

    # ==========================================================
    # IMPORT PRESERVATION
    # ==========================================================

    def _protect_python_imports(
        self,
        file_blocks: List[Tuple[str, str]],
        original_files: Dict[str, str],
    ) -> List[Tuple[str, str]]:
        """
        Protect important Python imports before final validation.
        """

        repaired_files = []

        for path, content in file_blocks:

            normalized = (
                self._normalize_path_key(
                    path
                )
            )

            original = original_files.get(
                normalized
            )

            if original is not None:

                content = (
                    self._restore_missing_python_imports(
                        original,
                        content,
                        path,
                    )
                )

            repaired_files.append(
                (
                    path,
                    content,
                )
            )

        return repaired_files

    # ==========================================================
    # TEST FILE PROTECTION
    # ==========================================================

    def _check_test_imports_preserved(
        self,
        path: str,
        original: str,
        repaired: str,
    ) -> None:
        """
        Strong protection for test files.

        If a test still uses an imported symbol, its import must
        remain available after repair.
        """

        normalized = (
            self._normalize_path_key(
                path
            )
        )

        is_test = (
            normalized.startswith("test")
            or "/test" in normalized
            or normalized.startswith("tests/")
            or "/tests/" in normalized
            or Path(path).name.startswith("test_")
        )

        if not is_test:
            return

        missing = (
            self._find_missing_python_imports(
                original,
                repaired,
            )
        )

        if missing:

            raise RuntimeError(
                f"Test file '{path}' lost required "
                f"imports: {missing}"
            )

    # ==========================================================
    # PROMPT
    # ==========================================================

    def _build_prompt(
        self,
        code: str,
        review: str,
        validation: str,
        tests: str,
        execution: str,
        retry: str,
        memory_context: str,
        project_context: str,
        retry_count: int = 0,
    ) -> str:

        retry_notice = ""

        if retry_count >= 2:

            retry_notice = (
                "\n"
                "==========================================================\n"
                "RETRY WARNING\n"
                "==========================================================\n\n"
                f"This is repair attempt #{retry_count}.\n"
                "The previous repair did NOT solve the issue.\n"
                "Do not simply repeat the previous fix.\n"
                "Analyze the failure again and use a genuinely "
                "different approach if necessary.\n"
            )

        return f"""
You are AutoDev AI's autonomous software repair engineer.

Your job is to repair the USER'S SOURCE PROJECT.

==========================================================
CRITICAL RULE — PRESERVE SOURCE CODE
==========================================================

The project below is the source of truth.

You must return the COMPLETE repaired source project.

Do NOT unnecessarily delete existing code.

Do NOT rewrite working code without a reason.

Do NOT remove imports that are still required.

Do NOT remove test imports.

If a function/class/module is still used, preserve the required
imports and dependencies.

==========================================================
IMPORT PRESERVATION RULE
==========================================================

This rule is extremely important.

Before modifying a source file:

1. Inspect its existing imports.
2. Determine which imported names are used.
3. Preserve all imports that remain necessary.
4. Do not remove an import merely because the import statement
   looks unnecessary.
5. Tests are especially important.

Example:

Original:

from app import add

def test_add():
    assert add(2, 3) == 5

Correct repair:

from app import add

def test_add():
    assert add(2, 3) == 5

INCORRECT repair:

def test_add():
    assert add(2, 3) == 5

The second version is invalid because 'add' is undefined.

==========================================================
SOURCE FILES VS RUNTIME ARTIFACTS
==========================================================

SOURCE FILES include:

- Python files
- JavaScript files
- TypeScript files
- React files
- HTML files
- CSS files
- configuration files
- dependency files
- test files
- README files

RUNTIME/DEBUG ARTIFACTS include:

- execution/
- history/
- .autodev_debug/
- __pycache__/
- .pytest_cache/
- .mypy_cache/
- .ruff_cache/
- coverage/
- build/
- dist/
- .venv/
- venv/

Runtime/debug artifacts are ONLY diagnostic evidence.

They are NOT source files.

NEVER return runtime/debug artifacts.

==========================================================
CURRENT SOURCE PROJECT
==========================================================

{code}

==========================================================
PROJECT CONTEXT
==========================================================

{project_context}

==========================================================
AI REVIEW
==========================================================

{review}

==========================================================
VALIDATION REPORT
==========================================================

{validation}

==========================================================
TEST RESULTS
==========================================================

{tests}

==========================================================
EXECUTION / DEBUG REPORT
==========================================================

The following is diagnostic evidence.

It is NOT source code.

Do NOT convert this information into FILE blocks.

{execution}

==========================================================
PREVIOUS REPAIR ATTEMPTS
==========================================================

{retry}

{retry_notice}

==========================================================
RELEVANT PAST FIXES
==========================================================

{memory_context}

==========================================================
OBJECTIVE
==========================================================

Repair ONLY real problems.

Preserve all working functionality.

Fix:

- syntax errors
- runtime errors
- imports
- dependencies
- configuration
- startup issues
- package.json
- requirements.txt
- failing tests
- missing source files
- invalid source paths

DO NOT modify tests merely to make them pass.

Tests represent expected behavior.

Only change a test when the test itself is clearly incorrect
and the requirements/specification prove that it is incorrect.

Never include built-in Python modules such as:

tkinter
sqlite3
json
os
sys
typing
pathlib
logging
asyncio

in requirements.txt.

==========================================================
OUTPUT FORMAT
==========================================================

Return ONLY the COMPLETE REPAIRED SOURCE PROJECT.

Every source file MUST begin with:

FILE: relative/path

Example:

FILE: app.py

print("hello")

FILE: requirements.txt

pytest

FILE: tests/test_app.py

from app import add

def test_add():
    assert add(2, 3) == 5

==========================================================
ABSOLUTE OUTPUT RULES
==========================================================

Start immediately with FILE:

Do NOT use markdown.

Do NOT use code fences.

Do NOT explain anything.

Do NOT return runtime/debug artifacts.

Do NOT return:

execution/
history/
.autodev_debug/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
coverage/
build/
dist/
.venv/
venv/

Do NOT return logs.

Do NOT return execution reports.

Do NOT return temporary files.

Do NOT return cache files.

Do NOT return generated debug files.

Do NOT leave placeholder comments such as:

# remaining code
# omitted
# rest of the code
...
TODO
FIXME

Every returned source file must be complete.

Return ONLY FILE blocks.
"""

    # ==========================================================
    # DEBUG ARTIFACTS
    # ==========================================================

    def _save_debug_artifacts(
        self,
        project_directory: Optional[str],
        prompt: str,
        raw_response: str,
        normalized_response: str,
    ) -> None:
        """
        Save Fixer debugging information.

        These files are diagnostic only and are never part of
        the generated source project.
        """

        if not project_directory:
            return

        try:

            debug_dir = (
                Path(project_directory)
                / ".autodev_debug"
                / "fixer"
            )

            debug_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            timestamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S_%f"
            )

            (
                debug_dir
                / f"{timestamp}_prompt.txt"
            ).write_text(
                prompt,
                encoding="utf-8",
            )

            (
                debug_dir
                / f"{timestamp}_response_raw.txt"
            ).write_text(
                raw_response,
                encoding="utf-8",
            )

            (
                debug_dir
                / f"{timestamp}_response_normalized.txt"
            ).write_text(
                normalized_response,
                encoding="utf-8",
            )

        except Exception:

            logger.exception(
                "Failed to save Fixer debug artifacts."
            )

    # ==========================================================
    # MAIN RUN
    # ==========================================================

    async def run(
        self,
        code,
        review=None,
        validation=None,
        tests=None,
        execution_error=None,
        retry_history=None,
        project_directory: str | None = None,
        project_type: Optional[str] = None,
        memory: Optional[MemoryManager] = None,
        retry_count: Optional[int] = None,
        save_debug: bool = False,
    ) -> str:

        logger.info("=" * 60)
        logger.info("Fixer Agent Started")
        logger.info("=" * 60)

        # ------------------------------------------------------
        # Validate input
        # ------------------------------------------------------

        if not code or not code.strip():

            raise ValueError(
                "Project code cannot be empty."
            )

        # ------------------------------------------------------
        # Preserve original source BEFORE filtering.
        # ------------------------------------------------------

        original_source_code = code

        original_files = (
            self._extract_original_files(
                original_source_code
            )
        )

        # ------------------------------------------------------
        # Remove runtime/debug artifacts BEFORE sending the
        # project to the LLM.
        # ------------------------------------------------------

        code = self._filter_source_project(
            code
        )

        if not code.strip():

            raise RuntimeError(
                "No source files remain after filtering "
                "runtime artifacts."
            )

        # ------------------------------------------------------
        # Convert reports to text
        # ------------------------------------------------------

        review_text = (
            self._to_text(review)
            or "No review."
        )

        validation_text = (
            self._to_text(validation)
            or "No validation report."
        )

        tests_text = (
            self._to_text(tests)
            or "No test report."
        )

        execution_text = (
            self._to_text(execution_error)
            or "No execution report."
        )

        retry_text = (
            self._to_text(retry_history)
            or "No retry history."
        )

        # ------------------------------------------------------
        # Build project context
        # ------------------------------------------------------

        project_context = ""

        if project_directory:

            try:

                project_context = (
                    self.project_context.build(
                        project_directory
                    )
                )

            except Exception:

                logger.exception(
                    "Failed to build project context."
                )

                project_context = ""

        if not project_context:

            project_context = (
                "No project context available."
            )

        # ------------------------------------------------------
        # Error category
        # ------------------------------------------------------

        category = (
            self._extract_category(
                execution_error
            )
        )

        # ------------------------------------------------------
        # Retry count
        # ------------------------------------------------------

        if retry_count is None:

            if isinstance(
                retry_history,
                list,
            ):

                retry_count = len(
                    retry_history
                )

            else:

                retry_count = 0

        # ------------------------------------------------------
        # Memory
        # ------------------------------------------------------

        memory = (
            memory
            or MemoryManager()
        )

        memory_query = "\n\n".join(
            part
            for part in (
                f"category: {category}",
                execution_text,
                review_text,
                validation_text,
            )
            if part
        )

        memory_items = memory.retrieve(
            prompt=memory_query,
            limit=5,
        )

        memory_context = (
            memory.build_context(
                memory_items
            )
        )

        # ------------------------------------------------------
        # Build repair prompt
        # ------------------------------------------------------

        prompt = self._build_prompt(
            code=code,
            review=review_text,
            validation=validation_text,
            tests=tests_text,
            execution=execution_text,
            retry=retry_text,
            memory_context=memory_context,
            project_context=project_context,
            retry_count=retry_count,
        )

        logger.info(
            "Sending repair request to LLM..."
        )

        # ------------------------------------------------------
        # LLM
        # ------------------------------------------------------

        try:

            response = await self.llm.generate(
                prompt
            )

        except Exception as exc:

            logger.exception(
                "Fixer generation failed."
            )

            raise RuntimeError(
                f"Fixer failed: {exc}"
            ) from exc

        if response is None:

            raise RuntimeError(
                "LLM returned None."
            )

        raw_response = str(
            response
        ).strip()

        if not raw_response:

            raise RuntimeError(
                "LLM returned an empty response."
            )

        # ------------------------------------------------------
        # Normalize
        # ------------------------------------------------------

        response = self._normalize_response(
            raw_response
        )

        # ------------------------------------------------------
        # Save debug artifacts
        # ------------------------------------------------------

        if save_debug:

            self._save_debug_artifacts(
                project_directory,
                prompt,
                raw_response,
                response,
            )

        # ------------------------------------------------------
        # Extract generated files BEFORE validation.
        # ------------------------------------------------------

        file_blocks = (
            self._extract_file_blocks(
                response
            )
        )

        if not file_blocks:

            raise RuntimeError(
                "Fixer did not return any FILE blocks."
            )

        # ------------------------------------------------------
        # Protect Python imports.
        #
        # This is the important fix for your current failure.
        # ------------------------------------------------------

        file_blocks = (
            self._protect_python_imports(
                file_blocks,
                original_files,
            )
        )

        # ------------------------------------------------------
        # Rebuild response after import protection.
        # ------------------------------------------------------

        response = self._build_file_blocks(
            file_blocks
        )

        # ------------------------------------------------------
        # Reject identical response.
        # ------------------------------------------------------

        if response.strip() == code.strip():

            raise RuntimeError(
                "Fixer returned an identical, "
                "unmodified project."
            )

        # ------------------------------------------------------
        # Validate repaired project.
        # ------------------------------------------------------

        self._validate_response(
            response,
            original_files=original_files,
            project_type=project_type,
        )

        logger.info(
            "Fixer Agent finished successfully."
        )

        logger.info("=" * 60)
        logger.info("Fixer Agent Finished")
        logger.info("=" * 60)

        # ------------------------------------------------------
        # Save successful repair to memory.
        # ------------------------------------------------------

        try:

            memory.save(
                memory_type="fix",
                prompt=execution_text,
                error=execution_text,
                fix=response[:4000],
                review="Automatic repair generated.",
                success=True,
                category=category,
            )

        except Exception:

            logger.exception(
                "Failed to save repair memory."
            )

        return response

    # ==========================================================
    # VALIDATION
    # ==========================================================

    def _validate_response(
        self,
        response: str,
        original_files: Optional[
            Dict[str, str]
        ] = None,
        project_type: Optional[str] = None,
    ) -> None:

        original_files = (
            original_files
            or {}
        )

        if not response:

            raise RuntimeError(
                "Fixer returned an empty project."
            )

        if len(response) < self.MIN_RESPONSE_LENGTH:

            raise RuntimeError(
                "Fixer response is too short."
            )

        if not response.startswith(
            "FILE:"
        ):

            raise RuntimeError(
                "Fixer output must start with FILE:."
            )

        file_blocks = (
            self._extract_file_blocks(
                response
            )
        )

        if not file_blocks:

            raise RuntimeError(
                "No FILE blocks were returned."
            )

        if len(file_blocks) > self.MAX_FILES:

            raise RuntimeError(
                f"Too many generated files "
                f"({len(file_blocks)})."
            )

        logger.info(
            "Fixer generated %d file(s).",
            len(file_blocks),
        )

        seen = set()

        for path, content in file_blocks:

            # --------------------------------------------------
            # Path validation
            # --------------------------------------------------

            self._validate_file_path(
                path
            )

            normalized = (
                self._normalize_path_key(
                    path
                )
            )

            if normalized in seen:

                raise RuntimeError(
                    f"Duplicate generated file: {path}"
                )

            seen.add(normalized)

            # --------------------------------------------------
            # Content validation
            # --------------------------------------------------

            if not content.strip():

                raise RuntimeError(
                    f"Generated file is empty: {path}"
                )

            if len(content.strip()) < 3:

                raise RuntimeError(
                    f"Generated file appears incomplete: {path}"
                )

            # --------------------------------------------------
            # Placeholder validation
            # --------------------------------------------------

            self._check_placeholder_content(
                path,
                content,
            )

            # --------------------------------------------------
            # Python syntax validation
            # --------------------------------------------------

            self._validate_python_syntax(
                path,
                content,
            )

            # --------------------------------------------------
            # Suspicious shrinkage
            # --------------------------------------------------

            self._check_suspicious_shrinkage(
                path,
                content,
                original_files,
            )

            # --------------------------------------------------
            # Test import protection
            # --------------------------------------------------

            original = original_files.get(
                normalized
            )

            if original is not None:

                self._check_test_imports_preserved(
                    path,
                    original,
                    content,
                )

            logger.debug(
                "Validated repaired file: %s",
                path,
            )

        # ------------------------------------------------------
        # Critical files
        # ------------------------------------------------------

        self._check_critical_files_preserved(
            seen,
            original_files,
        )

        # ------------------------------------------------------
        # Entry points
        # ------------------------------------------------------

        self._check_entry_points_preserved(
            project_type,
            seen,
            original_files,
        )

    # ==========================================================
    # PUBLIC DEBUG HELPER
    # ==========================================================

    def get_file_blocks(
        self,
        response: str,
    ) -> List[Tuple[str, str]]:

        response = (
            self._normalize_response(
                response
            )
        )

        return (
            self._extract_file_blocks(
                response
            )
        )