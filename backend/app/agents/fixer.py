from __future__ import annotations

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
    Repairs an existing generated software project.

    Unlike the Coder Agent, the Fixer receives an already
    generated project together with execution/debug reports
    and produces a fully repaired version.

    Expected output format:

    FILE: app.py
    ...

    FILE: requirements.txt
    ...

    The Fixer ALWAYS returns the COMPLETE project.
    """

    MIN_RESPONSE_LENGTH = 50
    MAX_FILE_PATH_LENGTH = 250
    MAX_FILES = 150

    # A replacement file is "suspiciously tiny" if it shrank to less
    # than this fraction of its original size (and the original was
    # non-trivial to begin with).
    MIN_SIZE_RATIO = 0.2
    MIN_ORIGINAL_SIZE_TO_CHECK = 200  # chars

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

    # Files that, if present in the original project, must survive a
    # repair. Only enforced when they actually existed beforehand.
    CRITICAL_FILE_NAMES = (
        "requirements.txt",
        "package.json",
        "pyproject.toml",
        "Pipfile",
        "go.mod",
        "Cargo.toml",
    )

    # Expected entry points per detected project type. Only enforced
    # when the corresponding file existed in the original project.
    ENTRY_POINTS_BY_PROJECT_TYPE = {
        "python": ("main.py",),
        "fastapi": ("app.py", "main.py"),
        "node": ("package.json",),
        "express": ("package.json",),
        "react": ("package.json", "src/App.jsx", "src/App.tsx"),
    }

    PLACEHOLDER_PATTERNS = (
        re.compile(r"#\s*remaining\s+(code|implementation)", re.IGNORECASE),
        re.compile(r"//\s*remaining\s+(code|implementation)", re.IGNORECASE),
        re.compile(r"#\s*omitted", re.IGNORECASE),
        re.compile(r"//\s*omitted", re.IGNORECASE),
        re.compile(r"#\s*rest of the code", re.IGNORECASE),
        re.compile(r"//\s*rest of the code", re.IGNORECASE),
        re.compile(r"^\s*\.\.\.\s*$", re.MULTILINE),
        re.compile(r"\bTODO\b"),
        re.compile(r"\bFIXME\b"),
        re.compile(r"remaining implementation", re.IGNORECASE),
    )

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

    FILE_PATTERN = re.compile(
        r"(?m)^FILE:\s*(.+?)\s*$"
    )

    # Matches a fenced code block opener/closer line on its own,
    # e.g. ``` or ```python, anywhere in the text (not just at the
    # very start/end of the response).
    CODE_FENCE_LINE = re.compile(
        r"(?m)^[ \t]*```[\w+-]*[ \t]*$"
    )

    # ==========================================================
    # INIT
    # ==========================================================

    def __init__(self, llm=None):
        """
        llm: optional injected LLM client. When omitted, falls back to
        LLMRouter.get_llm(). The LLM is resolved once here (not per
        call) so an injected fake/mock client is used consistently,
        and so all calls in a single agent instance share one client.
        """

        super().__init__()

        self.llm = llm or LLMRouter.get_llm()
        self.project_context = ProjectContext()

    # ==========================================================
    # HELPERS
    # ==========================================================

    @staticmethod
    def _to_text(value) -> str:
        """
        Convert arbitrary objects into readable text
        before inserting into the repair prompt.
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
        Pull an error category out of the execution/debug report if
        present (RetryManager's DebugManager tags reports with a
        "category" field, e.g. "ImportError", "DatabaseError").
        Falls back to "Unknown" for anything that isn't a dict or
        doesn't have the field, so this is safe to call even when
        execution_error is None or a plain string.
        """

        if isinstance(execution_error, dict):
            return execution_error.get("category", "Unknown")

        return "Unknown"

    @staticmethod
    def _normalize_path_key(path: str) -> str:
        """
        Normalize a file path for duplicate/lookup comparisons so that
        equivalent paths like "app.py" and "./app.py" collide.
        """

        normalized = path.replace("\\", "/").strip()

        if normalized.startswith("./"):
            normalized = normalized[2:]

        return PurePosixPath(normalized).as_posix().lower()

    # ==========================================================
    # RESPONSE NORMALIZATION
    # ==========================================================

    def _normalize_response(
        self,
        response: str,
    ) -> str:
        """
        Normalize the LLM response into clean FILE blocks.
        """

        response = response.strip()

        # Strip every fenced code block marker (```/```lang), not just
        # ones at the very start/end of the response. Models sometimes
        # wrap the output in prose + a single fenced block in the
        # middle of the response; this keeps the FILE content while
        # dropping every fence line.
        response = self.CODE_FENCE_LINE.sub("", response)

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
    # REMOVE LANGUAGE LABELS
    # ==========================================================

    def _remove_language_labels(
        self,
        response: str,
    ) -> str:
        """
        Removes accidental language labels such as:

        FILE: app.py
        python

        leaving only the file content.
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
        Split the repaired project into FILE blocks.

        Returns:
            [
                ("app.py", "..."),
                ("requirements.txt", "..."),
            ]
        """

        matches = list(
            self.FILE_PATTERN.finditer(response)
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

    def _extract_original_files(self, code: str) -> Dict[str, str]:
        """
        Best-effort extraction of the ORIGINAL project's FILE blocks
        (keyed by normalized path) so repairs can be checked against
        it (critical files, entry points, suspicious shrinkage).

        `code` isn't guaranteed to be in FILE: format (callers may
        pass raw source or something else), so this is defensive and
        simply returns {} if nothing parses.
        """

        try:
            blocks = self._extract_file_blocks(code)
        except Exception:
            return {}

        return {
            self._normalize_path_key(path): content
            for path, content in blocks
        }

    # ==========================================================
    # FILE PATH VALIDATION
    # ==========================================================

    def _validate_file_path(
        self,
        path: str,
    ) -> None:
        """
        Validate generated file paths.
        """

        if not path:
            raise RuntimeError(
                "Generated file path is empty."
            )

        if len(path) > self.MAX_FILE_PATH_LENGTH:
            raise RuntimeError(
                f"File path too long: {path}"
            )

        normalized = (
            path.replace("\\", "/")
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
    # PLACEHOLDER / SIZE VALIDATION
    # ==========================================================

    def _check_placeholder_content(self, path: str, content: str) -> None:
        """
        Reject files whose content looks like the model gave up and
        left a placeholder instead of real code (e.g. "# Remaining
        code...", "// omitted", bare "...", TODO/FIXME markers).
        """

        for pattern in self.PLACEHOLDER_PATTERNS:
            if pattern.search(content):
                raise RuntimeError(
                    f"Generated file '{path}' contains placeholder "
                    f"content instead of a real implementation "
                    f"(matched pattern: {pattern.pattern!r})."
                )

    def _check_suspicious_shrinkage(
        self,
        path: str,
        content: str,
        original_files: Dict[str, str],
    ) -> None:
        """
        Reject replacements that are suspiciously tiny compared to
        the original file (e.g. a 500-line app.py replaced with just
        `pass`), while ignoring genuinely small files.
        """

        original = original_files.get(self._normalize_path_key(path))

        if original is None:
            return

        original_len = len(original.strip())

        if original_len < self.MIN_ORIGINAL_SIZE_TO_CHECK:
            return

        new_len = len(content.strip())

        if new_len < original_len * self.MIN_SIZE_RATIO:
            raise RuntimeError(
                f"Generated file '{path}' shrank suspiciously "
                f"({original_len} -> {new_len} chars); likely a "
                f"truncated/placeholder replacement rather than a "
                f"real repair."
            )

    def _check_critical_files_preserved(
        self,
        generated_keys: set,
        original_files: Dict[str, str],
    ) -> None:
        """
        Ensure files like requirements.txt / package.json that
        existed in the original project weren't silently dropped.
        """

        for name in self.CRITICAL_FILE_NAMES:
            key = self._normalize_path_key(name)

            if key in original_files and key not in generated_keys:
                raise RuntimeError(
                    f"Critical file '{name}' existed in the original "
                    f"project but is missing from the repair."
                )

    def _check_entry_points_preserved(
        self,
        project_type: Optional[str],
        generated_keys: set,
        original_files: Dict[str, str],
    ) -> None:
        """
        Ensure the startup file(s) for the detected project type
        weren't accidentally deleted by the repair.
        """

        if not project_type:
            return

        expected = self.ENTRY_POINTS_BY_PROJECT_TYPE.get(
            project_type.lower()
        )

        if not expected:
            return

        for entry_point in expected:
            key = self._normalize_path_key(entry_point)

            if key in original_files and key not in generated_keys:
                raise RuntimeError(
                    f"Entry point '{entry_point}' existed in the "
                    f"original {project_type} project but is missing "
                    f"from the repair."
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
                "\n==========================================================\n"
                "RETRY WARNING\n"
                "==========================================================\n\n"
                f"This is repair attempt #{retry_count}. Your previous repair(s) "
                "did NOT solve the issue. Do not simply repeat the previous "
                "fix — review the retry history above and try a genuinely "
                "different approach.\n"
            )

        return f"""
You are AutoDev AI's autonomous repair engineer.

Repair the COMPLETE software project.

==========================================================
CURRENT PROJECT
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

{execution}

==========================================================
PREVIOUS REPAIR ATTEMPTS
==========================================================

{retry}
{retry_notice}
==========================================================
RELEVANT PAST FIXES (MEMORY)
==========================================================

{memory_context}

==========================================================
OBJECTIVE
==========================================================

Repair ONLY real problems.

Preserve working functionality.

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
- missing files
- invalid file paths

Never include built-in Python modules (tkinter, sqlite3, json,
os, sys, typing, pathlib, logging, asyncio, etc.) in
requirements.txt.

==========================================================
OUTPUT FORMAT
==========================================================

Return the COMPLETE repaired project.

Every file MUST begin with

FILE: relative/path

Example

FILE: app.py

print("hello")

FILE: requirements.txt

fastapi

==========================================================
STRICT RULES
==========================================================

Start immediately with FILE:

Do NOT use markdown.

Do NOT use code fences.

Do NOT explain anything.

Do NOT leave placeholder comments like "# remaining code" or
"..." in place of real implementation — every file must be
complete and runnable.

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
        Optionally persists the prompt sent to the LLM and both the
        raw and normalized responses, for debugging repair failures.
        Best-effort only — never allowed to break the run.
        """

        if not project_directory:
            return

        try:
            debug_dir = Path(project_directory) / ".autodev_debug" / "fixer"
            debug_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

            (debug_dir / f"{timestamp}_prompt.txt").write_text(
                prompt, encoding="utf-8"
            )
            (debug_dir / f"{timestamp}_response_raw.txt").write_text(
                raw_response, encoding="utf-8"
            )
            (debug_dir / f"{timestamp}_response_normalized.txt").write_text(
                normalized_response, encoding="utf-8"
            )

        except Exception:
            logger.exception("Failed to save Fixer debug artifacts.")

    # ==========================================================
    # MAIN
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

        if not code or not code.strip():
            raise ValueError(
                "Project code cannot be empty."
            )

        review_text = self._to_text(review) or "No review."
        validation_text = self._to_text(validation) or "No validation report."
        tests_text = self._to_text(tests) or "No test report."
        execution_text = self._to_text(execution_error) or "No execution report."
        retry_text = self._to_text(retry_history) or "No retry history."

        # project_context was previously undefined at the _build_prompt
        # call site, causing a guaranteed NameError. Build it here from
        # the project directory when one is available.
        project_context = ""

        if project_directory:
            try:
                project_context = self.project_context.build(project_directory)
            except Exception:
                logger.exception(
                    "Failed to build project context; continuing without it."
                )
                project_context = ""

        if not project_context:
            project_context = "No project context available."

        category = self._extract_category(execution_error)

        # Infer a retry attempt number when the caller didn't pass one
        # explicitly, so the "don't repeat the previous fix" notice in
        # the prompt still works with the existing retry_history shape.
        if retry_count is None:
            if isinstance(retry_history, list):
                retry_count = len(retry_history)
            else:
                retry_count = 0

        # Use a shared MemoryManager if one was passed in (recommended),
        # otherwise fall back to a fresh instance so the agent still
        # works standalone. NOTE: a fresh instance has no history, so
        # memory_context will be empty in that case.
        memory = memory or MemoryManager()

        # Search memory with execution + review + validation context
        # combined, plus the detected error category as an explicit
        # term, since raw stderr text alone is often too narrow to
        # surface related past fixes (e.g. "ImportError" as a keyword
        # matches more reliably than the full traceback).
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

        memory_context = memory.build_context(
            memory_items
        )

        # Prompt is built AFTER memory_context and project_context both
        # exist, and now matches _build_prompt's actual signature.
        prompt = self._build_prompt(
            code,
            review_text,
            validation_text,
            tests_text,
            execution_text,
            retry_text,
            memory_context,
            project_context,
            retry_count=retry_count,
        )

        logger.info(
            "Sending repair request to LLM..."
        )

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

        raw_response = str(response).strip()

        if not raw_response:
            raise RuntimeError(
                "LLM returned an empty response."
            )

        response = self._normalize_response(
            raw_response
        )

        if save_debug:
            self._save_debug_artifacts(
                project_directory,
                prompt,
                raw_response,
                response,
            )

        # Reject identical repairs here, at the source, instead of only
        # relying on RetryManager's post-hoc similarity check. This
        # saves a full rebuild + re-execution cycle whenever the LLM
        # just echoes the input back.
        if response.strip() == code.strip():

            raise RuntimeError(
                "Fixer returned an identical, unmodified project."
            )

        original_files = self._extract_original_files(code)

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
        original_files: Optional[Dict[str, str]] = None,
        project_type: Optional[str] = None,
    ) -> None:
        """
        Validate the repaired project before returning it.
        """

        original_files = original_files or {}

        if not response:
            raise RuntimeError(
                "Fixer returned an empty project."
            )

        if len(response) < self.MIN_RESPONSE_LENGTH:
            raise RuntimeError(
                "Fixer response is too short."
            )

        if not response.startswith("FILE:"):
            raise RuntimeError(
                "Fixer output must start with FILE:."
            )

        file_blocks = self._extract_file_blocks(
            response
        )

        if not file_blocks:
            raise RuntimeError(
                "No FILE blocks were returned."
            )

        if len(file_blocks) > self.MAX_FILES:
            raise RuntimeError(
                f"Too many generated files ({len(file_blocks)})."
            )

        logger.info(
            "Fixer generated %d file(s).",
            len(file_blocks),
        )

        seen = set()

        for path, content in file_blocks:

            self._validate_file_path(
                path
            )

            normalized = self._normalize_path_key(path)

            if normalized in seen:
                raise RuntimeError(
                    f"Duplicate generated file: {path}"
                )

            seen.add(normalized)

            if not content.strip():
                raise RuntimeError(
                    f"Generated file is empty: {path}"
                )

            if len(content.strip()) < 3:
                raise RuntimeError(
                    f"Generated file appears incomplete: {path}"
                )

            self._check_placeholder_content(path, content)
            self._check_suspicious_shrinkage(path, content, original_files)

            logger.debug(
                "Validated repaired file: %s",
                path,
            )

        self._check_critical_files_preserved(seen, original_files)
        self._check_entry_points_preserved(project_type, seen, original_files)

    # ==========================================================
    # PUBLIC DEBUG HELPER
    # ==========================================================

    def get_file_blocks(
        self,
        response: str,
    ) -> List[Tuple[str, str]]:
        """
        Return parsed FILE blocks from a Fixer response.
        Useful for testing and debugging.
        """

        response = self._normalize_response(
            response
        )

        return self._extract_file_blocks(
            response
        )