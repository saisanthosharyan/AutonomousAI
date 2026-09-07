from __future__ import annotations

import ast
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
    from app import main

    def test_example():
        assert callable(main)

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

    # Standard-library modules that should never be treated
    # as project-local modules.
    PYTHON_STDLIB_MODULES = {
        "abc",
        "argparse",
        "ast",
        "asyncio",
        "base64",
        "collections",
        "contextlib",
        "copy",
        "csv",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "functools",
        "hashlib",
        "http",
        "inspect",
        "io",
        "itertools",
        "json",
        "logging",
        "math",
        "os",
        "pathlib",
        "pickle",
        "platform",
        "random",
        "re",
        "shutil",
        "socket",
        "sqlite3",
        "statistics",
        "string",
        "subprocess",
        "sys",
        "tempfile",
        "textwrap",
        "threading",
        "time",
        "traceback",
        "typing",
        "unittest",
        "urllib",
        "uuid",
        "warnings",
        "xml",
        "zipfile",
    }

    # ==========================================================
    # INIT
    # ==========================================================

    def __init__(self, *args, llm=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.llm = llm
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

        llm = self.llm or LLMRouter.get_llm()

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
                response,
                task,
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
                response,
                task,
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

====================================================
PROJECT
====================================================

Title:
{task.title}

Description:
{task.description}

====================================================
VALIDATION ERROR
====================================================

{error}

====================================================
PREVIOUS INVALID OUTPUT
====================================================

{response}

====================================================
YOUR TASK
====================================================

Regenerate the COMPLETE project correctly.

Do not only patch the validation error.

Return the complete project again.

====================================================
ABSOLUTE OUTPUT RULES
====================================================

Return ONLY project FILE blocks.

A FILE header must ALWAYS be followed by the complete
content of that file.

VALID:

FILE: app.py
import sys

def main():
    print("Hello")

FILE: test_app.py
from app import main

def test_main():
    assert callable(main)

FILE: README.md
# Project

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
MANDATORY PROJECT FILES
====================================================

Unless genuinely inappropriate for the project, include:

- Source code
- Automated tests
- README.md
- .gitignore

Python projects must use pytest.

Node projects must include package.json.

Generate dependency files whenever third-party dependencies
are actually required.

Do not add unnecessary dependencies.

====================================================
CRITICAL PYTHON TEST RULE
====================================================

Every Python test that directly uses functions, classes,
or variables from application source code MUST explicitly
import them.

Example:

FILE: main.py

def add(a, b):
    return a + b

FILE: test_main.py

from main import add

def test_add():
    assert add(2, 3) == 5

This is INVALID:

FILE: test_main.py

def test_add():
    assert add(2, 3) == 5

because "add" has not been imported.

Never reference an application function or class that has
not been imported or otherwise defined in the test.

For a calculator, tests should include:

from main import add, subtract, multiply, divide
import pytest

def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(5, 3) == 2

def test_multiply():
    assert multiply(4, 3) == 12

def test_divide():
    assert divide(10, 2) == 5

def test_division_by_zero():
    with pytest.raises(ValueError):
        divide(10, 0)

====================================================
TEST VALIDATION
====================================================

Before returning the project, mentally verify:

1. Every test imports the application code it tests.
2. Every imported local module exists.
3. Every imported function/class exists.
4. Test expectations match implementation behavior.
5. Tests can be collected by pytest.
6. Tests execute real functionality.
7. Tests do not merely assert True.
8. Tests do not reference undefined application symbols.
9. Test imports match actual file names.
10. pytest is available when required.

====================================================
PYTHON
====================================================

If using Python:

- Use pytest for automated tests.
- Test important functionality.
- Test normal cases.
- Test important error cases.
- Ensure the entry point works.
- Ensure imports work.
- Do not put standard-library modules in requirements.txt.
- Do not create unnecessary requirements.txt files.
- Use relative/local imports only when they match the
  generated package structure.

====================================================
DOCUMENTATION
====================================================

README.md must contain:

- Project name
- Project description
- Features
- Requirements
- Installation
- Usage
- Testing instructions

====================================================
SECURITY
====================================================

Never generate:

- Real API keys
- Passwords
- Access tokens
- Private keys
- Secret certificates
- .env files
- Credential files

Use .env.example for configuration placeholders.

====================================================
VALIDATION-FIRST CORRECTION
====================================================

The previous response failed validation.

You MUST correct the specific validation error.

Do not copy the invalid file structure blindly.

If the validation error is a duplicate file:

- output that file exactly once
- preserve only one correct version
- never output the same path twice

If the validation error is a technology mismatch:

- follow the requested technology exactly
- remove files belonging to the wrong technology
- generate the correct files for the requested stack

For an HTML/CSS/JavaScript frontend project:

ALLOWED:

FILE: index.html
FILE: style.css
FILE: script.js
FILE: README.md
FILE: .gitignore

Do NOT generate:

main.py
app.py
test_main.py
test_app.py
requirements.txt
pytest configuration
Flask
FastAPI
Django
Express
or unrelated backend code.

Before returning the response, internally check:

1. Every file path is unique.
2. Every file has content.
3. The requested technology is used.
4. No forbidden technology files exist.
5. Required files exist.
6. README.md exists.
7. .gitignore exists.
8. No FILE header is repeated.

====================================================
OUTPUT FORMAT
====================================================

Return ONLY the actual project files.

A FILE header MUST ALWAYS be followed immediately by
that file's COMPLETE content.

NEVER output a list of filenames first.

NEVER output a file manifest.

NEVER output empty FILE blocks.

NEVER repeat a FILE header.

NEVER repeat a file path.

Return files in dependency order when possible.

====================================================
FINAL RULE
====================================================

Start immediately with:

FILE:

Do NOT use markdown code fences.

Do NOT explain anything.

Do NOT summarize.

Do NOT provide analysis.

Do NOT provide commentary.

Do NOT say "Here is the project".

Do NOT omit required files.

Do NOT output empty files.

Do NOT repeat files.

Every imported third-party package must exist in the
dependency configuration.

Every generated source file must be complete.

Every generated test must execute against real functionality.

The project must be runnable after building.

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
    # TECHNOLOGY CONTRACT
    # ==========================================================

    def _build_technology_contract(
        self,
        task: Task,
    ) -> str:
        """
        Infer the required technology from task metadata and
        description so the Coder cannot silently switch stacks.
        """

        text = (
            f"{task.title}\n"
            f"{task.description}\n"
            f"{getattr(task, 'project_type', '')}\n"
            f"{getattr(task, 'language', '')}\n"
            f"{getattr(task, 'framework', '')}"
        ).lower()

        html_requested = bool(
            re.search(r"\bhtml5?\b", text)
        )

        css_requested = bool(
            re.search(r"\bcss3?\b", text)
        )

        javascript_requested = bool(
            re.search(
                r"\bjavascript\b|\bjava\s*script\b|\bjs\b",
                text,
            )
        )

        html_css_js = (
            html_requested
            and css_requested
            and javascript_requested
        )

        if html_css_js:

            return """
FRONTEND TECHNOLOGY CONTRACT

THIS TASK IS A VANILLA FRONTEND PROJECT.

Use ONLY:

- HTML
- CSS
- JavaScript

For this task, generate EXACTLY these files:

FILE: index.html
FILE: style.css
FILE: script.js
FILE: README.md
FILE: .gitignore

DO NOT generate any other files.

FORBIDDEN:

- Python
- .py files
- Flask
- FastAPI
- Django
- Node.js
- Express
- server.js
- server.ts
- backend code
- API servers
- database code
- requirements.txt
- pytest
- test_*.py
- pyproject.toml
- package.json
- npm
- package-lock.json

Do not create a backend.

Do not create a Python application.

Do not create a test framework.

Implement all requested functionality directly
inside index.html, style.css and script.js.

README.md must document how to open and use the frontend.

.gitignore must contain appropriate frontend/editor/OS ignores.

Return exactly 5 FILE blocks.

No additional files are allowed.
"""

        return """
TECHNOLOGY CONTRACT

Follow the requested language and framework exactly.

Never substitute another programming language or framework
unless the project specification explicitly requires it.

Do not introduce a backend, database, framework or dependency
that the user did not request.
"""

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

        technology_contract = (
            self._build_technology_contract(
                task
            )
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

====================================================
TECHNOLOGY CONTRACT
====================================================

{technology_contract}

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
4. Contain automated tests where automated testing is practical
   and appropriate for the requested project.
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
19. If tests are generated, ensure they can actually run.
20. Ensure README explains installation, usage and testing
    when applicable.

====================================================
MANDATORY PROJECT COMPLETENESS
====================================================

Unless the project type genuinely does not require them,
generate:

- Source code
- Automated tests
- README.md
- .gitignore

Generate dependency files when dependencies exist.

Python projects:

- requirements.txt when third-party packages are required
- pyproject.toml when appropriate
- pytest tests

Node projects:

- package.json
- appropriate test setup
- README.md
- .gitignore

Web projects:

- package.json or equivalent
- source files
- tests where appropriate
- README.md
- .gitignore

CLI projects:

- executable entry point
- automated tests
- README.md
- .gitignore

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

- Use pytest for automated tests.
- Test important functionality.
- Test normal cases.
- Test important error cases.
- Ensure the entry point works.
- Ensure imports work.
- Do not put standard-library modules in requirements.txt.

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
subprocess
unittest

These must NOT be placed in requirements.txt.

====================================================
CRITICAL TEST IMPORT REQUIREMENT
====================================================

Every Python test that directly uses functions, classes,
or variables from generated application code MUST import
those objects.

Example:

FILE: main.py

def add(a, b):
    return a + b

FILE: test_main.py

from main import add

def test_add():
    assert add(2, 3) == 5

INVALID:

FILE: test_main.py

def test_add():
    assert add(2, 3) == 5

The invalid example references "add" without importing it.

Before returning the project, verify:

- Every local application symbol used by a test is imported.
- Every imported local module exists.
- Every imported function/class exists.
- Test imports match actual generated file names.
- Tests can be collected by pytest.
- Tests execute real application functionality.
- Tests do not reference undefined names.
- Tests do not merely assert True.

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

- addition
- subtraction
- multiplication
- division
- division by zero
- invalid input where applicable

Example:

FILE: main.py

def add(a, b):
    return a + b

FILE: test_main.py

from main import add

def test_add():
    assert add(2, 3) == 5

Make sure test expectations match the implementation.

====================================================
DOCUMENTATION
====================================================

README.md should contain:

- Project name
- Project description
- Features
- Requirements
- Installation
- Usage
- Testing instructions

Keep documentation relevant to the project.

====================================================
EXISTING PROJECT RULES
====================================================

If an existing project is provided:

- Modify existing files whenever possible.
- Reuse the existing architecture.
- Preserve existing APIs.
- Preserve naming conventions.
- Preserve coding style.
- Do not regenerate the entire project unnecessarily.
- Only create new files when required.
- Do not remove working functionality without reason.

====================================================
SECURITY
====================================================

Never generate:

- real API keys
- passwords
- access tokens
- private keys
- certificates containing secrets
- .env files
- credential files

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

FILE: main.py
def add(a, b):
    return a + b

FILE: test_main.py
from main import add

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

        if not isinstance(response, str):
            raise RuntimeError(
                "LLM response must be a string."
            )

        response = response.strip()

        if not response:
            raise RuntimeError(
                "LLM response is empty."
            )

        # ------------------------------------------------------
        # Locate the first FILE block.
        #
        # The LLM may put a short explanation before the
        # generated project. Everything before the first FILE:
        # declaration is discarded.
        # ------------------------------------------------------

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

        # ------------------------------------------------------
        # Remove language labels that may appear immediately
        # after FILE declarations.
        #
        # File-level Markdown fences are intentionally NOT
        # removed here.
        #
        # They are handled safely by _extract_file_blocks()
        # because README files can legitimately contain nested
        # Markdown code fences.
        # ------------------------------------------------------

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
    # DUPLICATE FILE NORMALIZATION
    # ==========================================================

    def _remove_exact_duplicate_files(
        self,
        file_blocks: List[Tuple[str, str]],
    ) -> List[Tuple[str, str]]:
        """
        Remove exact duplicate file blocks produced by the LLM.

        If the same normalized path appears more than once:

        - identical content -> keep the first occurrence
        - different content -> raise an error

        This prevents weak LLMs from accidentally repeating
        files such as .gitignore while still protecting against
        conflicting generated files.
        """

        unique_files: List[
            Tuple[str, str]
        ] = []

        seen_files = {}

        for path, content in file_blocks:

            normalized_path = (
                path.replace("\\", "/")
                .strip()
                .lower()
            )

            if normalized_path not in seen_files:

                seen_files[
                    normalized_path
                ] = (
                    path,
                    content,
                )

                unique_files.append(
                    (
                        path,
                        content,
                    )
                )

                continue

            previous_path, previous_content = (
                seen_files[
                    normalized_path
                ]
            )

            if (
                previous_content.strip()
                == content.strip()
            ):

                logger.warning(
                    "Removing exact duplicate generated file: %s",
                    path,
                )

                continue

            raise RuntimeError(
                "Conflicting duplicate generated file detected: "
                f"{path}. The same file path was generated with "
                "different contents."
            )

        if len(unique_files) != len(file_blocks):

            logger.warning(
                "Removed %d exact duplicate file block(s).",
                len(file_blocks) - len(unique_files),
            )

        return unique_files

    # ==========================================================
    # EXTRACT FILE BLOCKS
    # ==========================================================
    def _extract_file_blocks(
        self,
        response: str,
    ) -> List[Tuple[str, str]]:

        if not isinstance(response, str):
            return []

        response = response.replace(
            "\r\n",
            "\n",
        )

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

        for index, match in enumerate(matches):

            # --------------------------------------------------
            # Extract file path.
            # --------------------------------------------------

            path = match.group(
                1
            ).strip()

            if not path:
                raise RuntimeError(
                    "Generated FILE block has an empty path."
                )

            # --------------------------------------------------
            # Determine content boundaries.
            # --------------------------------------------------

            start = match.end()

            if index + 1 < len(matches):

                end = matches[
                    index + 1
                ].start()

            else:

                end = len(
                    response
                )

            content = response[
                start:end
            ]

            content = content.replace(
                "\r\n",
                "\n",
            ).strip()

            # --------------------------------------------------
            # Remove an OUTER Markdown fence.
            #
            # Supported:
            #
            # ```python
            # ```py
            # ```javascript
            # ```typescript
            # ```json
            # ```markdown
            # ```text
            # ```
            #
            # Only the fence surrounding the entire file block
            # is removed.
            #
            # This is important because README.md may contain
            # legitimate nested Markdown fences.
            # --------------------------------------------------

            lines = content.splitlines()

            if lines:

                first_line = lines[0].strip()

                opening_fence_match = re.match(
                    r"^```(?:[A-Za-z0-9_+#.\-]+)?$",
                    first_line,
                )

                if opening_fence_match:

                    # Remove opening fence.
                    lines = lines[1:]

                    # Remove matching final fence only if it is
                    # the final non-empty line.
                    #
                    # This prevents us from deleting legitimate
                    # code fences inside README.md.
                    if lines:

                        last_non_empty_index = None

                        for reverse_index in range(
                            len(lines) - 1,
                            -1,
                            -1,
                        ):

                            if lines[
                                reverse_index
                            ].strip():

                                last_non_empty_index = (
                                    reverse_index
                                )

                                break

                        if (
                            last_non_empty_index
                            is not None
                            and lines[
                                last_non_empty_index
                            ].strip()
                            == "```"
                        ):

                            del lines[
                                last_non_empty_index
                            ]

                    content = "\n".join(
                        lines
                    ).strip()

            # --------------------------------------------------
            # Handle an unusual case where the LLM puts a fence
            # immediately after whitespace/newlines.
            # --------------------------------------------------

            if content:

                content_lines = (
                    content.splitlines()
                )

                if content_lines:

                    first_line = (
                        content_lines[0].strip()
                    )

                    if re.match(
                        r"^```(?:[A-Za-z0-9_+#.\-]+)?$",
                        first_line,
                    ):

                        content_lines = (
                            content_lines[1:]
                        )

                        if content_lines:

                            last_non_empty_index = None

                            for reverse_index in range(
                                len(content_lines) - 1,
                                -1,
                                -1,
                            ):

                                if content_lines[
                                    reverse_index
                                ].strip():

                                    last_non_empty_index = (
                                        reverse_index
                                    )

                                    break

                            if (
                                last_non_empty_index
                                is not None
                                and content_lines[
                                    last_non_empty_index
                                ].strip()
                                == "```"
                            ):

                                del content_lines[
                                    last_non_empty_index
                                ]

                        content = "\n".join(
                            content_lines
                        ).strip()

            # --------------------------------------------------
            # Remove accidental trailing standalone fence.
            #
            # This only applies when the entire extracted file
            # ended with a fence. It does NOT touch internal
            # README Markdown fences.
            # --------------------------------------------------

            if content:

                content_lines = (
                    content.splitlines()
                )

                if (
                    content_lines
                    and content_lines[-1].strip()
                    == "```"
                ):

                    content_lines.pop()

                    content = "\n".join(
                        content_lines
                    ).strip()

            # --------------------------------------------------
            # Final content validation.
            # --------------------------------------------------

            if not content:
                raise RuntimeError(
                    f"Generated file is empty after "
                    f"normalization: {path}"
                )

            # --------------------------------------------------
            # Remove accidental whitespace around the file
            # while preserving the actual source formatting.
            # --------------------------------------------------

            content = content.strip()

            files.append(
                (
                    path,
                    content,
                )
            )

        # ------------------------------------------------------
        # Normalize duplicates.
        #
        # Exact-content duplicates (e.g. a repeated .gitignore
        # block) are collapsed into a single file. Conflicting
        # duplicates (same path, different content) still raise.
        # ------------------------------------------------------

        files = self._remove_exact_duplicate_files(
            files
        )

        logger.info(
            "Extracted %d clean file blocks.",
            len(files),
        )

        for path, content in files:

            first_content_line = (
                content.splitlines()[0]
                if content.splitlines()
                else ""
            )

            logger.debug(
                "Generated file: %s | first line: %s",
                path,
                first_content_line[:120],
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
        task: Task,
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

        # ------------------------------------------------------
        # SEMANTIC PROJECT VALIDATION
        # ------------------------------------------------------

        self._validate_project_technology(
            task,
            file_blocks,
        )

        self._validate_project_completeness(
            file_blocks
        )

        self._validate_python_files(
            file_blocks
        )

        self._validate_python_tests(
            file_blocks
        )

        logger.info(
            "Complete Coder response validation passed."
        )

    # ==========================================================
    # TECHNOLOGY VALIDATION
    # ==========================================================

    def _validate_project_technology(
        self,
        task: Task,
        file_blocks: List[Tuple[str, str]],
    ) -> None:
        """
        Ensure the generated project follows the requested
        technology stack.
        """

        text = (
            f"{task.title}\n"
            f"{task.description}\n"
            f"{getattr(task, 'project_type', '')}\n"
            f"{getattr(task, 'language', '')}\n"
            f"{getattr(task, 'framework', '')}"
        ).lower()

        html_requested = bool(
            re.search(r"\bhtml5?\b", text)
        )

        css_requested = bool(
            re.search(r"\bcss3?\b", text)
        )

        javascript_requested = bool(
            re.search(
                r"\bjavascript\b|\bjava\s*script\b|\bjs\b",
                text,
            )
        )

        is_frontend_html_css_js = (
            html_requested
            and css_requested
            and javascript_requested
        )

        if not is_frontend_html_css_js:
            return

        paths = [
            path.replace("\\", "/").lower()
            for path, _ in file_blocks
        ]

        file_contents = {
            path.replace("\\", "/").lower(): content.lower()
            for path, content in file_blocks
        }

        filenames = {
            path.split("/")[-1]
            for path in paths
        }

        forbidden_python = [
            path
            for path in paths
            if path.endswith(".py")
        ]

        if forbidden_python:

            raise RuntimeError(
                "Technology mismatch: frontend HTML/CSS/JavaScript "
                f"project contains Python files: "
                f"{', '.join(forbidden_python)}"
            )

        if "index.html" not in filenames:

            raise RuntimeError(
                "Technology mismatch: HTML/CSS/JavaScript "
                "project is missing index.html."
            )

        if "style.css" not in filenames:

            raise RuntimeError(
                "Technology mismatch: HTML/CSS/JavaScript "
                "project is missing style.css."
            )

        if "script.js" not in filenames:

            raise RuntimeError(
                "Technology mismatch: HTML/CSS/JavaScript "
                "project is missing script.js."
            )

        # --------------------------------------------------
        # Content-level inspection.
        #
        # A model could name a file innocuously (e.g. api.js)
        # while still embedding backend/server code inside it.
        # File-name checks alone can't catch that, so inspect
        # file contents for telltale backend imports/usage.
        # --------------------------------------------------

        forbidden_backend_patterns = [
            "require(\"express\")",
            "require('express')",
            "from express",
            "import express",
            "from fastapi",
            "import fastapi",
            "from flask",
            "import flask",
            "from django",
            "import django",
            "http.createserver",
            "https.createserver",
        ]

        backend_matches = []

        for path, content in file_contents.items():
            for pattern in forbidden_backend_patterns:
                if pattern in content:
                    backend_matches.append(
                        f"{path}: {pattern}"
                    )

        if backend_matches:

            raise RuntimeError(
                "Technology mismatch: frontend project "
                "contains backend/server code: "
                + ", ".join(backend_matches)
            )

        logger.info(
            "HTML/CSS/JavaScript technology validation passed."
        )

    # ==========================================================
    # PROJECT COMPLETENESS VALIDATION
    # ==========================================================

    def _validate_project_completeness(
        self,
        file_blocks: List[Tuple[str, str]],
    ) -> None:

        filenames = {
            path.replace("\\", "/").lower().split("/")[-1]
            for path, _ in file_blocks
        }

        # README
        if not any(
            name in filenames
            for name in self.DOCUMENTATION_FILES
        ):

            raise RuntimeError(
                "Generated project is missing README documentation."
            )

        # Git hygiene
        if ".gitignore" not in filenames:

            raise RuntimeError(
                "Generated project is missing .gitignore."
            )

        # Tests
        #
        # Automated tests are encouraged but not strictly
        # mandatory for every project type (e.g. a simple
        # frontend page with only basic client-side validation
        # may not need a dedicated test framework). Enforcing
        # this here caused AutoDev-AI to force pytest-style
        # tests onto non-Python/non-test-oriented projects.
        test_files = [
            path
            for path, _ in file_blocks
            if self._is_test_file(path)
        ]

        if not test_files:

            logger.info(
                "No automated test files detected. "
                "Tests are optional for this project type."
            )

        logger.info(
            "Project completeness validation passed: "
            "README + .gitignore present."
        )

    # ==========================================================
    # PYTHON SYNTAX VALIDATION
    # ==========================================================

    def _validate_python_files(
        self,
        file_blocks: List[Tuple[str, str]],
    ) -> None:

        for path, content in file_blocks:

            if not path.lower().endswith(".py"):
                continue

            try:

                ast.parse(
                    content,
                    filename=path,
                )

            except SyntaxError as exc:

                line = (
                    exc.lineno
                    if exc.lineno is not None
                    else "unknown"
                )

                column = (
                    exc.offset
                    if exc.offset is not None
                    else "unknown"
                )

                raise RuntimeError(
                    f"Python syntax error in {path}: "
                    f"{exc.msg} "
                    f"(line {line}, column {column})"
                ) from exc

        logger.info(
            "Python syntax validation passed."
        )

    # ==========================================================
    # PYTHON TEST CONSISTENCY VALIDATION
    # ==========================================================

    def _validate_python_tests(
        self,
        file_blocks: List[Tuple[str, str]],
    ) -> None:
        """
        Validate that Python tests actually connect to the
        generated application.

        IMPORTANT:
        Do NOT attempt generic Python undefined-name analysis here.

        Python's AST Name nodes cannot safely distinguish:
        - builtins such as str, int, ValueError
        - pytest/unittest symbols
        - local variables
        - exception variables
        - fixtures
        - dynamically provided names
        - application symbols

        The previous implementation incorrectly rejected valid
        tests such as:

            with pytest.raises(ValueError) as e:
                ...
            assert str(e.value) == "..."

        Therefore this validator only checks the things we can
        determine reliably:

        1. Test files are syntactically valid.
        2. Tests import a generated local application module,
           OR use subprocess/importlib to execute the application.
        3. Imported local modules actually exist.
        4. No generic undefined-name guessing is performed.
        """

        python_files = {
            path.replace("\\", "/"): content
            for path, content in file_blocks
            if path.lower().endswith(".py")
        }

        if not python_files:
            return

        # ------------------------------------------------------
        # Build generated local module names.
        #
        # Examples:
        #
        # main.py
        #     -> main
        #
        # calculator.py
        #     -> calculator
        #
        # app/main.py
        #     -> main
        #
        # __init__.py is intentionally ignored.
        # ------------------------------------------------------

        local_modules = set()

        for path in python_files:
            normalized_path = path.replace(
                "\\",
                "/",
            )

            filename = normalized_path.split(
                "/"
            )[-1]

            if filename == "__init__.py":
                continue

            if not filename.lower().endswith(".py"):
                continue

            module_name = filename[:-3]

            if module_name.isidentifier():
                local_modules.add(
                    module_name
                )

        # ------------------------------------------------------
        # Validate each Python test file.
        # ------------------------------------------------------

        for path, content in file_blocks:

            if not self._is_test_file(path):
                continue

            if not path.lower().endswith(".py"):
                continue

            # Syntax validation is already performed by
            # _validate_python_files().
            #
            # We parse again because this method needs the AST
            # to inspect imports.
            try:
                tree = ast.parse(
                    content,
                    filename=path,
                )

            except SyntaxError:
                continue

            imported_local_modules = set()

            has_subprocess = False
            has_importlib = False

            # --------------------------------------------------
            # Inspect imports only.
            #
            # DO NOT inspect every ast.Name node.
            # --------------------------------------------------

            for node in ast.walk(tree):

                # ----------------------------------------------
                # import something
                # ----------------------------------------------

                if isinstance(node, ast.Import):

                    for alias in node.names:

                        root_module = (
                            alias.name.split(".")[0]
                        )

                        if root_module == "subprocess":
                            has_subprocess = True

                        if root_module == "importlib":
                            has_importlib = True

                        if root_module in local_modules:
                            imported_local_modules.add(
                                root_module
                            )

                # ----------------------------------------------
                # from something import something
                # ----------------------------------------------

                elif isinstance(
                    node,
                    ast.ImportFrom,
                ):

                    if not node.module:
                        continue

                    root_module = (
                        node.module.split(".")[0]
                    )

                    if root_module == "subprocess":
                        has_subprocess = True

                    if root_module == "importlib":
                        has_importlib = True

                    if root_module in local_modules:
                        imported_local_modules.add(
                            root_module
                        )

            # --------------------------------------------------
            # Validate local module imports.
            #
            # Example:
            #
            # FILE: main.py
            #
            # FILE: test_main.py
            # from main import add
            #
            # "main" exists in local_modules, therefore this
            # test is connected to the generated application.
            # --------------------------------------------------

            if imported_local_modules:

                logger.debug(
                    "Python test '%s' imports generated "
                    "local modules: %s",
                    path,
                    ", ".join(
                        sorted(
                            imported_local_modules
                        )
                    ),
                )

            # --------------------------------------------------
            # Tests may legitimately execute the application
            # using subprocess or importlib instead of importing
            # application functions directly.
            #
            # Example:
            #
            # subprocess.run(
            #     [sys.executable, "main.py", ...]
            # )
            #
            # or:
            #
            # importlib.import_module("main")
            # --------------------------------------------------

            elif has_subprocess or has_importlib:

                logger.debug(
                    "Python test '%s' executes application "
                    "through subprocess/importlib.",
                    path,
                )

            # --------------------------------------------------
            # If there are generated application modules but the
            # test doesn't import one and doesn't execute one
            # through subprocess/importlib, reject it.
            #
            # This catches the actual bug we care about:
            #
            # FILE: main.py
            #
            # FILE: test_main.py
            # def test_add():
            #     assert add(2, 3) == 5
            #
            # The test doesn't connect to the generated project.
            # --------------------------------------------------

            else:

                non_test_modules = {
                    module
                    for module in local_modules
                    if not module.startswith("test")
                }

                if non_test_modules:

                    raise RuntimeError(
                        f"Python test file '{path}' does not "
                        f"import any generated local application "
                        f"module. Tests must execute real project "
                        f"functionality."
                    )

            logger.debug(
                "Python test validation passed: %s",
                path,
            )

        logger.info(
            "Python test consistency validation passed."
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
            in {
                item.lower()
                for item in self.TEST_FILE_NAMES
            }
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