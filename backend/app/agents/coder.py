
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from app.agents.base_agent import BaseAgent
from app.core.logger import logger
from app.models.task import Task
from app.services.llm.router import LLMRouter
from app.memory.memory_manager import MemoryManager
from app.project.project_context import ProjectContext


class CoderAgent(BaseAgent):
    """
    Converts a Planner Task into a complete executable project.

    Expected LLM output:

    FILE: app.py
    print("Hello")

    FILE: test_app.py
    def test_example():
        assert True

    FILE: README.md
    # Project

    FILE: requirements.txt
    pytest
    """

    MIN_RESPONSE_LENGTH = 50
    MAX_FILE_PATH_LENGTH = 250
    MAX_FILES = 150

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

    TEST_FILE_NAMES = {
        "test.py",
        "tests.py",
        "test_app.py",
        "test_main.py",
        "tests/test.py",
        "tests/test_app.py",
        "tests/test_main.py",
    }

    DOCUMENTATION_FILES = {
        "readme.md",
        "readme.txt",
        "readme",
    }

    # ==========================================================
    # INIT
    # ==========================================================

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.project_context = ProjectContext()

    # ==========================================================
    # MAIN
    # ==========================================================

    async def run(
        self,
        task: Task,
        project_directory: str | None = None,
        memory: Optional[MemoryManager] = None,
    ) -> str:

        logger.info("=" * 70)
        logger.info("Coder Agent Started")
        logger.info("=" * 70)

        self._validate_task(task)

        llm = LLMRouter.get_llm()

        memory = memory or MemoryManager()

        memory_items = memory.retrieve(
            prompt=f"{task.title}\n{task.description}",
            limit=10,
        )

        memory_context = memory.build_context(
            memory_items
        )

        steps = "\n".join(
            f"{i}. {step.strip()}"
            for i, step in enumerate(
                filter(None, task.steps or []),
                start=1,
            )
        )

        project_context = self._build_project_context(
            project_directory
        )

        prompt = self._build_prompt(
            task=task,
            steps=steps,
            memory_context=memory_context,
            project_context=project_context,
        )

        logger.info(
            "Sending project generation request to LLM..."
        )

        response = await self._generate_response(
            llm,
            prompt,
        )

        response = self._normalize_response(
            response
        )

        logger.info("=" * 70)
        logger.info("NORMALIZED CODER RESPONSE")
        logger.info("=" * 70)
        logger.info("\n%s", response)
        logger.info("=" * 70)

        # ------------------------------------------------------
        # FIRST VALIDATION
        # ------------------------------------------------------

        try:

            self._validate_response(
                response
            )

        except RuntimeError as exc:

            logger.warning(
                "Initial Coder output failed validation: %s",
                exc,
            )

            # --------------------------------------------------
            # AUTOMATIC CORRECTION
            # --------------------------------------------------

            response = await self._correct_response(
                llm=llm,
                response=response,
                error=str(exc),
                task=task,
            )

            response = self._normalize_response(
                response
            )

            logger.info("=" * 70)
            logger.info("NORMALIZED CORRECTED CODER RESPONSE")
            logger.info("=" * 70)
            logger.info("\n%s", response)
            logger.info("=" * 70)

            # --------------------------------------------------
            # SECOND VALIDATION
            # --------------------------------------------------

            self._validate_response(
                response
            )

        self._log_project_summary(
            response
        )

        try:

            file_count = len(
                self.get_file_blocks(
                    response
                )
            )

            memory.save(
                memory_type="generation",
                prompt=(
                    f"{task.title}\n"
                    f"{task.description}"
                ),
                language=self._get_task_language(
                    task
                ),
                framework=self._get_task_framework(
                    task
                ),
                review=(
                    f"Generated {file_count} files."
                ),
                success=True,
            )

        except Exception:

            logger.exception(
                "Failed to save generation memory."
            )

        logger.info(
            "Project generation successful."
        )

        logger.info("=" * 70)
        logger.info("Coder Agent Finished")
        logger.info("=" * 70)

        return response

    # ==========================================================
    # LLM GENERATION
    # ==========================================================

    async def _generate_response(
        self,
        llm,
        prompt: str,
    ) -> str:

        try:

            response = await llm.generate(
                prompt
            )

        except Exception as exc:

            logger.exception(
                "Project generation failed: %s",
                exc,
            )

            raise RuntimeError(
                "LLM project generation failed."
            ) from exc

        if response is None:

            raise RuntimeError(
                "LLM returned None."
            )

        response = str(
            response
        ).strip()

        if not response:

            raise RuntimeError(
                "LLM returned an empty response."
            )

        logger.info(
            "Raw response size: %d characters",
            len(response),
        )

        logger.info("=" * 70)
        logger.info("RAW CODER LLM RESPONSE")
        logger.info("=" * 70)
        logger.info("\n%s", response)
        logger.info("=" * 70)

        return response

    # ==========================================================
    # AUTOMATIC CORRECTION
    # ==========================================================

    async def _correct_response(
        self,
        llm,
        response: str,
        error: str,
        task: Task,
    ) -> str:

        logger.info(
            "Requesting corrected project generation..."
        )

        correction_prompt = f"""
You are AutoDev AI.

The previous Coder Agent generated an INVALID project.

PROJECT:

Title:
{task.title}

Description:
{task.description}

VALIDATION ERROR:

{error}

PREVIOUS INVALID OUTPUT:

{response}

====================================================
YOUR TASK
====================================================

Regenerate the COMPLETE project correctly.

====================================================
ABSOLUTE OUTPUT RULES
====================================================

Return ONLY project FILE blocks.

A FILE header must ALWAYS be followed immediately by
the complete content of that file.

VALID:

FILE: app.py
import sys

def main():
    print("Hello")

FILE: test_app.py
from app import main

def test_main():
    assert callable(main)

INVALID:

FILE: app.py
FILE: test_app.py
FILE: README.md

Do NOT output a filename manifest.

Do NOT output empty FILE blocks.

Do NOT repeat FILE headers.

Do NOT repeat file paths.

Do NOT use markdown code fences.

Do NOT explain anything.

Do NOT provide analysis.

Do NOT provide a summary.

Do NOT provide commentary.

Do NOT say "Here is the project".

Every generated file must contain complete real content.

Every import must work.

Every dependency must exist.

Every test must test real functionality.

The project must be runnable.

====================================================
EXPECTED FORMAT
====================================================

FILE: relative/path

complete file contents

FILE: another/path

complete file contents

FILE: README.md

complete README contents

====================================================
FINAL RULE
====================================================

Start immediately with:

FILE:

Return ONLY FILE blocks.
"""

        try:

            corrected_response = await llm.generate(
                correction_prompt
            )

        except Exception as exc:

            logger.exception(
                "Corrected project generation failed: %s",
                exc,
            )

            raise RuntimeError(
                "Coder Agent failed during automatic correction."
            ) from exc

        if corrected_response is None:

            raise RuntimeError(
                "LLM returned None during correction."
            )

        corrected_response = str(
            corrected_response
        ).strip()

        if not corrected_response:

            raise RuntimeError(
                "LLM returned an empty response during correction."
            )

        logger.info(
            "Corrected response size: %d characters",
            len(corrected_response),
        )

        logger.info("=" * 70)
        logger.info("RAW CORRECTED CODER RESPONSE")
        logger.info("=" * 70)
        logger.info(
            "\n%s",
            corrected_response
        )
        logger.info("=" * 70)

        return corrected_response

    # ==========================================================
    # TASK VALIDATION
    # ==========================================================

    def _validate_task(
        self,
        task: Task,
    ) -> None:

        if task is None:

            raise ValueError(
                "Task cannot be None."
            )

        if not task.title or not task.title.strip():

            raise ValueError(
                "Task title cannot be empty."
            )

        if (
            not task.description
            or not task.description.strip()
        ):

            raise ValueError(
                "Task description cannot be empty."
            )

    # ==========================================================
    # PROJECT CONTEXT
    # ==========================================================

    def _build_project_context(
        self,
        project_directory: str | None,
    ) -> str:

        if not project_directory:

            return ""

        logger.info(
            "Analyzing existing project..."
        )

        try:

            self.project_context.build(
                project_directory
            )

            return (
                self.project_context.build_llm_context(
                    max_chars=8000
                )
            )

        except Exception:

            logger.exception(
                "Project analysis failed."
            )

            return ""

    # ==========================================================
    # PROMPT
    # ==========================================================

    def _build_prompt(
        self,
        task: Task,
        steps: str,
        memory_context: str,
        project_context: str,
    ) -> str:

        language = self._get_task_language(
            task
        )

        framework = self._get_task_framework(
            task
        )

        return f"""
You are AutoDev AI.

You are an elite autonomous software engineer.

Your job is to generate a COMPLETE, RUNNABLE, TESTABLE,
DOCUMENTED software project from the planner specification.

====================================================
PROJECT
====================================================

Title:
{task.title}

Description:
{task.description}

Language:
{language}

Framework:
{framework or "None"}

Project Type:
{getattr(task, "project_type", "") or "Not specified"}

Database:
{getattr(task, "database", "") or "None"}

Authentication:
{getattr(task, "authentication", "") or "None"}

Testing:
{getattr(task, "testing", "") or "Automated tests required"}

====================================================
EXISTING PROJECT
====================================================

{project_context or "No existing project."}

====================================================
PREVIOUS LEARNINGS
====================================================

{memory_context or "No previous learning available."}

====================================================
IMPLEMENTATION PLAN
====================================================

{steps or "No implementation steps provided."}

====================================================
CORE REQUIREMENTS
====================================================

Generate the ENTIRE project.

The generated project must:

1. Be executable.
2. Be internally consistent.
3. Contain all required source files.
4. Contain automated tests.
5. Contain useful documentation.
6. Contain dependency/configuration files when appropriate.
7. Have correct imports.
8. Have correct file paths.
9. Have no missing functions.
10. Have no TODO placeholders.
11. Have no FIXME placeholders.
12. Have no pseudocode.
13. Have no fake implementations.
14. Have no hardcoded secrets.
15. Never create a real .env file.
16. Use .env.example when configuration is required.
17. Ensure all generated files work together.
18. Ensure the entry point can actually be executed.
19. Ensure tests can actually run.
20. Ensure README explains installation, usage and testing.

====================================================
MANDATORY PROJECT COMPLETENESS
====================================================

Unless the project type genuinely does not require them,
generate:

• Source code
• Automated tests
• README.md
• .gitignore

Generate dependency files when dependencies exist.

Python projects:

• requirements.txt when third-party packages are required
• pyproject.toml when appropriate
• pytest tests

Node projects:

• package.json
• appropriate test setup
• README.md

Web projects:

• package.json or equivalent
• source files
• tests where appropriate
• README.md

CLI projects:

• executable entry point
• automated tests
• README.md
• .gitignore

====================================================
IMPORTANT
====================================================

Do NOT blindly add unnecessary files.

A Python project using only the standard library does NOT
need requirements.txt.

Do NOT add Docker, Kubernetes, databases, authentication,
CI/CD or infrastructure unless required.

====================================================
PYTHON
====================================================

If using Python:

• Use pytest for automated tests.
• Test important functionality.
• Test normal cases.
• Test important error cases.
• Ensure the entry point works.
• Ensure imports work.
• Do not put standard-library modules in requirements.txt.

Standard-library examples:

os
sys
json
re
math
pathlib
typing
logging
asyncio
sqlite3
datetime
collections

These must NOT be placed in requirements.txt.

If the project has no third-party dependencies,
requirements.txt may be omitted.

====================================================
TESTING
====================================================

Tests are REQUIRED where automated testing is practical.

Tests must test REAL functionality.

Do NOT create fake tests such as:

def test_everything():
    assert True

Tests must actually import and execute the generated code.

For a calculator, test:

• addition
• subtraction
• multiplication
• division
• division by zero
• invalid input where applicable

Make sure test expectations match the implementation.

====================================================
DOCUMENTATION
====================================================

README.md should contain:

• Project name
• Project description
• Features
• Requirements
• Installation
• Usage
• Testing instructions

Keep documentation relevant to the project.

====================================================
EXISTING PROJECT RULES
====================================================

If an existing project is provided:

• Modify existing files whenever possible.
• Reuse the existing architecture.
• Preserve existing APIs.
• Preserve naming conventions.
• Preserve coding style.
• Do not regenerate the entire project unnecessarily.
• Only create new files when required.
• Do not remove working functionality without reason.

====================================================
SECURITY
====================================================

Never generate:

• real API keys
• passwords
• access tokens
• private keys
• certificates containing secrets
• .env files
• credential files

Use placeholders in .env.example.

====================================================
OUTPUT FORMAT
====================================================

Return ONLY the actual project files.

IMPORTANT:

A FILE header MUST ALWAYS be immediately followed by
that file's COMPLETE content.

NEVER output a list of filenames first.

NEVER output a file manifest.

NEVER output empty FILE blocks.

NEVER repeat a FILE header.

NEVER repeat a file path.

For example, this is INVALID:

FILE: app.py
FILE: test_app.py
FILE: README.md

This is VALID:

FILE: app.py
import sys

def add(a, b):
    return a + b

FILE: test_app.py
from app import add

def test_add():
    assert add(2, 3) == 5

FILE: README.md
# Calculator

Return files in dependency order when possible.

====================================================
STRICT OUTPUT RULES
====================================================

Start immediately with:

FILE:

Do NOT use markdown code fences.

Do NOT explain anything.

Do NOT summarize.

Do NOT provide analysis.

Do NOT provide commentary.

Do NOT say "Here is the project".

Do NOT output a filename manifest.

Do NOT omit required files.

Do NOT output empty files.

Do NOT repeat files.

Every imported third-party package must exist in the dependency
configuration.

Every generated source file must be complete.

Every generated test must execute against real functionality.

The project must be runnable after building.

Return ONLY FILE blocks.
"""

    # ==========================================================
    # RESPONSE NORMALIZATION
    # ==========================================================

    def _normalize_response(
        self,
        response: str,
    ) -> str:

        response = response.strip()

        # Remove opening markdown fence.
        response = re.sub(
            r"^\s*```(?:\w+)?\s*",
            "",
            response,
            flags=re.IGNORECASE,
        )

        # Remove closing markdown fence.
        response = re.sub(
            r"\s*```\s*$",
            "",
            response,
        )

        response = response.strip()

        first_file = response.find(
            "FILE:"
        )

        if first_file == -1:

            raise RuntimeError(
                "LLM response contains no FILE blocks."
            )

        if first_file > 0:

            logger.warning(
                "Discarding text before first FILE block."
            )

            response = response[
                first_file:
            ]

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

        matches = list(
            self.FILE_PATTERN.finditer(
                response
            )
        )

        if not matches:

            return []

        files: List[
            Tuple[str, str]
        ] = []

        for index, match in enumerate(
            matches
        ):

            path = match.group(
                1
            ).strip()

            start = match.end()

            if index + 1 < len(matches):

                end = matches[
                    index + 1
                ].start()

            else:

                end = len(
                    response
                )

            content = (
                response[
                    start:end
                ]
                .replace(
                    "\r\n",
                    "\n",
                )
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
    # DEBUG HELPER
    # ==========================================================

    def get_file_blocks(
        self,
        response: str,
    ) -> List[Tuple[str, str]]:

        response = self._normalize_response(
            response
        )

        return self._extract_file_blocks(
            response
        )

    # ==========================================================
    # VALIDATION
    # ==========================================================

    def _validate_response(
        self,
        response: str,
    ) -> None:

        if not response:

            raise RuntimeError(
                "Generated project is empty."
            )

        if len(response) < self.MIN_RESPONSE_LENGTH:

            raise RuntimeError(
                "Generated project is too small."
            )

        if not response.startswith(
            "FILE:"
        ):

            raise RuntimeError(
                "Project must start with 'FILE:'."
            )

        file_blocks = (
            self._extract_file_blocks(
                response
            )
        )

        if not file_blocks:

            raise RuntimeError(
                "No FILE blocks found."
            )

        if len(file_blocks) > self.MAX_FILES:

            raise RuntimeError(
                f"Project contains too many files "
                f"({len(file_blocks)})."
            )

        logger.info(
            "Generated %d files.",
            len(file_blocks),
        )

        seen = set()

        for path, content in file_blocks:

            self._validate_file_path(
                path
            )

            normalized = (
                path.replace(
                    "\\",
                    "/",
                ).lower()
            )

            if normalized in seen:

                raise RuntimeError(
                    f"Duplicate file detected: {path}"
                )

            seen.add(
                normalized
            )

            if not content.strip():

                raise RuntimeError(
                    f"Empty generated file: {path}"
                )

            if len(content.strip()) < 3:

                raise RuntimeError(
                    f"Generated file appears incomplete: {path}"
                )

            logger.debug(
                "Validated file: %s",
                path,
            )

    # ==========================================================
    # PROJECT SUMMARY
    # ==========================================================

    def _log_project_summary(
        self,
        response: str,
    ) -> None:

        files = (
            self._extract_file_blocks(
                response
            )
        )

        paths = [
            path.replace(
                "\\",
                "/",
            )
            for path, _ in files
        ]

        test_files = [
            path
            for path in paths
            if self._is_test_file(
                path
            )
        ]

        documentation_files = [
            path
            for path in paths
            if path.lower().split(
                "/"
            )[-1]
            in self.DOCUMENTATION_FILES
        ]

        dependency_files = [
            path
            for path in paths
            if path.lower().split(
                "/"
            )[-1]
            in {
                "requirements.txt",
                "pyproject.toml",
                "package.json",
                "pom.xml",
                "build.gradle",
                "cargo.toml",
            }
        ]

        logger.info(
            "Project summary: files=%d, tests=%d, "
            "documentation=%d, dependency_files=%d",
            len(files),
            len(test_files),
            len(documentation_files),
            len(dependency_files),
        )

        if not test_files:

            logger.warning(
                "Generated project contains no obvious test file."
            )

        if not documentation_files:

            logger.warning(
                "Generated project contains no README/documentation file."
            )

    # ==========================================================
    # TEST FILE DETECTION
    # ==========================================================

    def _is_test_file(
        self,
        path: str,
    ) -> bool:

        normalized = path.replace(
            "\\",
            "/",
        ).lower()

        filename = normalized.split(
            "/"
        )[-1]

        if filename.startswith(
            "test_"
        ):

            return True

        if filename.endswith(
            "_test.py"
        ):

            return True

        if filename in {
            "test.js",
            "test.ts",
            "test.jsx",
            "test.tsx",
            "tests.js",
            "tests.ts",
        }:

            return True

        return (
            normalized
            in self.TEST_FILE_NAMES
        )

    # ==========================================================
    # TASK METADATA HELPERS
    # ==========================================================

    def _get_task_language(
        self,
        task: Task,
    ) -> str:

        language = getattr(
            task,
            "language",
            None,
        )

        if language:

            return str(
                language
            )

        return "Unknown"

    def _get_task_framework(
        self,
        task: Task,
    ) -> str:

        framework = getattr(
            task,
            "framework",
            None,
        )

        if framework:

            return str(
                framework
            )

        return ""

    # ==========================================================
    # FILE PATH VALIDATION
    # ==========================================================

    def _validate_file_path(
        self,
        path: str,
    ) -> None:

        if not path:

            raise RuntimeError(
                "Generated file path is empty."
            )

        if len(path) > self.MAX_FILE_PATH_LENGTH:

            raise RuntimeError(
                f"Path too long: {path}"
            )

        normalized = path.replace(
            "\\",
            "/",
        ).strip()

        if normalized.startswith(
            "/"
        ):

            raise RuntimeError(
                f"Absolute Unix path not allowed: {path}"
            )

        if re.match(
            r"^[A-Za-z]:",
            normalized,
        ):

            raise RuntimeError(
                f"Absolute Windows path not allowed: {path}"
            )

        parts = normalized.split(
            "/"
        )

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

        filename = parts[-1]

        allowed_extensionless = {
            "Dockerfile",
            "Makefile",
            "Procfile",
            "LICENSE",
        }

        if (
            "." not in filename
            and filename not in allowed_extensionless
        ):

            raise RuntimeError(
                f"Filename has no extension: {path}"
            )

        lower = normalized.lower()

        if lower == ".env.example":

            logger.debug(
                "Allowed path: %s",
                path,
            )

            return

        forbidden_files = {
            ".env",
            ".env.local",
            ".env.production",
            ".env.development",
            "id_rsa",
            "id_ed25519",
        }

        if filename.lower() in forbidden_files:

            raise RuntimeError(
                f"Forbidden file generated: {path}"
            )

        forbidden_dirs = {
            "__pycache__",
            "node_modules",
            ".git",
        }

        for part in parts[:-1]:

            if part.lower() in forbidden_dirs:

                raise RuntimeError(
                    f"Forbidden directory generated: {path}"
                )

        forbidden_extensions = {
            ".pem",
            ".key",
            ".pyc",
        }

        for ext in forbidden_extensions:

            if filename.lower().endswith(
                ext
            ):

                raise RuntimeError(
                    f"Forbidden file generated: {path}"
                )

        logger.debug(
            "Validated path: %s",
            path,
        )
