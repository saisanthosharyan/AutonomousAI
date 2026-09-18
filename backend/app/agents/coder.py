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

        generation_mode = str(
            getattr(task, "generation_mode", "project")
            or "project"
        ).strip().lower()

        project_type = str(
            getattr(task, "project_type", "")
            or ""
        ).strip().lower()

        requested_files = [
            str(path).replace("\\", "/").strip()
            for path in (
                getattr(task, "requested_files", None)
                or []
            )
            if str(path).strip()
        ]

        requested_files_text = (
            "\n".join(
                f"- {path}"
                for path in requested_files
            )
            if requested_files
            else "- No explicit file list was provided."
        )

        minimal_generation = generation_mode in {
            "code",
            "script",
        }

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

Project type:
{project_type}

Generation mode:
{generation_mode}

====================================================
EXPLICITLY REQUESTED FILES
====================================================

{requested_files_text}

These requested files are authoritative.

If the user explicitly requested specific files,
generate those files.

Do NOT add unrelated files.

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

Fix the validation error.

Return the complete corrected project.

Do not merely patch one file if other files are required
to make the project work.

However, do NOT create optional files that the user did
not request and that are not technically required.

====================================================
MINIMUM FILE PRINCIPLE
====================================================

The user's request is the source of truth.

Generate the SMALLEST FILE SET that fully satisfies the
user's request.

Only generate a file when at least one of these is true:

1. The user explicitly requested the file.
2. The file is technically required for the requested
   functionality.
3. The file is required because another explicitly
   requested file depends on it.

Do NOT generate files merely because they are common in
software projects.

Do NOT automatically create:

- README.md
- .gitignore
- tests
- requirements.txt
- pyproject.toml
- package.json
- Dockerfile
- docker-compose.yml
- LICENSE
- CI/CD files
- configuration files
- documentation files

unless they are explicitly requested or technically
required.

====================================================
CODE / SCRIPT REQUESTS
====================================================

If generation mode is:

code

or:

script

then prefer the smallest possible implementation.

For a simple programming request, normally generate only
one source file.

Example:

User request:
Write a Python program to print all prime numbers from
1 to 100.

Correct output:

FILE: main.py

<complete Python program>

Do NOT automatically generate:

- README.md
- .gitignore
- tests/test_main.py
- requirements.txt
- pyproject.toml
- Dockerfile
- documentation

unless the user requested them.

====================================================
WEBSITE REQUESTS
====================================================

For a website/frontend request, generate only the files
actually needed.

For example, a simple HTML/CSS/JavaScript website may use:

FILE: index.html

FILE: style.css

FILE: script.js

But README.md and .gitignore are NOT automatically
required.

If the user requests only HTML, generate only HTML unless
additional files are technically required.

If the user requests HTML + CSS, generate the required
HTML and CSS files.

If JavaScript is required, generate the JavaScript file.

Do not create backend files for a frontend-only request.

====================================================
APPLICATION / PROJECT REQUESTS
====================================================

For larger application or project requests, generate the
files required by the requested architecture and features.

Still avoid unnecessary documentation, tests, deployment
files, configuration files, or boilerplate unless:

- explicitly requested,
- technically required,
- or necessary for the requested architecture.

====================================================
EXPLICIT FILE REQUESTS
====================================================

If the task contains explicitly requested files:

{requested_files_text}

those files MUST be generated.

Do not rename them.

Do not replace them with alternative files.

Do not generate unnecessary additional files.

====================================================
DEPENDENCIES
====================================================

Only generate dependency configuration when it is actually
required.

For example:

A Python program using only the standard library does NOT
need requirements.txt.

A Python program using third-party packages MAY require
requirements.txt or pyproject.toml.

A Node application requiring npm packages requires an
appropriate dependency configuration.

Never list standard-library modules as dependencies.

====================================================
TESTS
====================================================

Tests are OPTIONAL unless the user requested tests or the
project technically requires them.

For minimal code/script requests, do NOT create tests
unless explicitly requested.

If tests are requested or technically required:

- Test real functionality.
- Import the application functions/classes correctly.
- Ensure all local imports match actual files.
- Ensure test expectations match implementation.
- Never reference undefined symbols.
- Never create fake tests that only assert True.

====================================================
PYTHON TEST RULE
====================================================

If Python tests are required, every test that uses an
application function or class MUST import it.

Example:

FILE: main.py

def add(a, b):
    return a + b

FILE: test_main.py

from main import add

def test_add():
    assert add(2, 3) == 5

Never write a test that references an application symbol
without importing it.

====================================================
OUTPUT FORMAT
====================================================

Return ONLY project FILE blocks.

A FILE header must ALWAYS be followed by the complete
content of that file.

VALID:

FILE: main.py
print("Hello")

FILE: helper.py
def hello():
    return "Hello"

INVALID:

FILE: main.py
FILE: helper.py

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

====================================================
FILE UNIQUENESS
====================================================

Every generated file path must be unique.

Never generate the same path twice.

If the previous response contained duplicate files,
return exactly one correct version of each file.

====================================================
TECHNOLOGY CONSISTENCY
====================================================

Follow the requested technology exactly.

For a Python request:

Do not generate unrelated HTML, Node, Java, or backend
framework files.

For a frontend request:

Do not generate Python, Flask, FastAPI, Django, or other
backend files unless explicitly requested.

For a Node request:

Use the requested Node technology.

Remove files belonging to unrelated technologies.

====================================================
SECURITY
====================================================

Never generate:

- real API keys
- passwords
- access tokens
- private keys
- secret certificates
- credential files
- real .env files

Use placeholders only when configuration is explicitly
required.

====================================================
VALIDATION-FIRST CORRECTION
====================================================

The previous response failed validation.

Correct the specific validation error:

{error}

Before returning the corrected project, internally verify:

1. Every requested file exists.
2. Every file path is unique.
3. Every file contains complete content.
4. The requested technology is used.
5. No unrelated technology files exist.
6. Imports match actual generated files.
7. Dependencies are actually required.
8. No unnecessary files were added.
9. The project satisfies the user's original request.
10. The validation error has been fixed.

====================================================
FINAL OUTPUT RULE
====================================================

Start immediately with:

FILE:

Return ONLY the actual project files.

No markdown fences.

No explanations.

No summaries.

No commentary.

No filename manifest.

No empty files.

No duplicate files.

No unnecessary files.

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
        Build a technology contract from the user's actual request.

        The contract prevents technology drift without forcing
        optional files such as README.md, .gitignore, or tests.
        """

        text = (
            f"{task.title}\n"
            f"{task.description}\n"
            f"{getattr(task, 'project_type', '')}\n"
            f"{getattr(task, 'language', '')}\n"
            f"{getattr(task, 'framework', '')}"
        ).lower()

        requested_files = [
            str(path).replace("\\", "/").strip()
            for path in (
                getattr(task, "requested_files", None)
                or []
            )
            if str(path).strip()
        ]

        requested_files_text = (
            "\n".join(
                f"- {path}"
                for path in requested_files
            )
            if requested_files
            else "- No explicit file list was provided."
        )

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

        frontend_requested = (
            html_requested
            or css_requested
            or javascript_requested
            or str(
                getattr(task, "project_type", "")
                or ""
            ).strip().lower()
            in {
                "web",
                "website",
                "frontend",
                "static_web",
            }
        )

        if frontend_requested:

            frontend_files = []

            if html_requested:
                frontend_files.append("index.html")

            if css_requested:
                frontend_files.append("style.css")

            if javascript_requested:
                frontend_files.append("script.js")

            if requested_files:
                frontend_files = requested_files

            frontend_files_text = (
                "\n".join(
                    f"- {path}"
                    for path in frontend_files
                )
                if frontend_files
                else "- Generate only the files technically required."
            )

            return f"""
FRONTEND TECHNOLOGY CONTRACT

This task is a frontend/web project.

Use only the frontend technologies actually requested
by the user.

Requested files:

{requested_files_text}

If the user explicitly requested files, those files are
authoritative.

Potential frontend files that may be required:

{frontend_files_text}

IMPORTANT:

Generate ONLY the files required to satisfy the user's
request.

Do NOT automatically generate:

- README.md
- .gitignore
- tests
- test files
- package.json
- package-lock.json
- requirements.txt
- pyproject.toml
- Docker files
- CI/CD files
- backend files
- configuration files

unless the user explicitly requested them or they are
technically required.

For a simple static website, use only the required
HTML/CSS/JavaScript files.

Do not create a backend unless explicitly requested.

Do not create Python files for a frontend-only request.

Do not create Node.js or Express files unless explicitly
requested.

Do not create a database unless explicitly requested.

Do not create a test framework unless tests are explicitly
requested.

Do not create documentation files unless documentation was
explicitly requested.

The user's original request is the source of truth.

Never generate extra files merely because they are common
in frontend projects.

Every generated file must contain complete real content.

Return only FILE blocks.
"""

        return f"""
TECHNOLOGY CONTRACT

Follow the requested language and framework exactly.

The user's requested files are:

{requested_files_text}

The user's request is the source of truth.

Generate only the smallest set of files required to satisfy
the request.

Do NOT automatically add:

- README.md
- .gitignore
- tests
- test files
- dependency files
- Docker files
- CI/CD files
- configuration files
- documentation

unless explicitly requested or technically required.

Never substitute another programming language or framework
unless the project specification explicitly requires it.

Do not introduce a backend, database, framework, dependency,
or unrelated technology that the user did not request.

Every generated file must be complete and functional.

Return only FILE blocks.
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

        language = self._get_task_language(task)
        framework = self._get_task_framework(task)

        technology_contract = self._build_technology_contract(task)

        generation_mode = getattr(
            task,
            "generation_mode",
            None,
        ) or "minimal"

        requested_files = getattr(
            task,
            "requested_files",
            None,
        ) or []

        requested_files_text = "\n".join(
            f"- {item}"
            for item in requested_files
            if str(item).strip()
        )

        return f"""
You are AutoDev AI.

You are an autonomous software engineer.

Your most important responsibility is to generate ONLY what the
USER ACTUALLY REQUESTED.

Do NOT turn a simple coding request into a complete software project.

====================================================
USER REQUEST
====================================================

Title:
{task.title}

Description:
{task.description}

====================================================
PROJECT INFORMATION
====================================================

Project Type:
{getattr(task, "project_type", "") or "Not specified"}

Language:
{language}

Framework:
{framework or "None"}

Generation Mode:
{generation_mode}

Requested Files:
{requested_files_text or "None explicitly specified"}

Database:
{getattr(task, "database", "") or "None"}

Authentication:
{getattr(task, "authentication", "") or "None"}

Testing:
{getattr(task, "testing", "") or "None"}

====================================================
TECHNOLOGY CONTRACT
====================================================

{technology_contract}

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
MOST IMPORTANT GENERATION RULE
====================================================

GENERATE THE MINIMUM NUMBER OF FILES REQUIRED TO SATISFY THE
USER'S REQUEST.

The user's request has higher priority than generic project
conventions.

DO NOT add files simply because they are common in software
projects.

DO NOT automatically create:

- README.md
- .gitignore
- tests
- requirements.txt
- pyproject.toml
- package.json
- Docker files
- CI/CD files
- configuration files
- documentation
- deployment files

unless they are:

1. explicitly requested by the user,
2. required for the requested technology to function,
3. required by an explicitly requested project structure, or
4. genuinely necessary for the application to run.

====================================================
SIMPLE CODE REQUEST RULE
====================================================

If the user asks for a piece of code or a simple program,
generate ONLY the source file(s) necessary to provide that code.

Examples:

User:
"Write a Python program to print all prime numbers from 1 to 100."

Generate:

FILE: main.py

Nothing else.

Do NOT generate:

- test_main.py
- README.md
- .gitignore
- requirements.txt
- pyproject.toml
- setup.py
- Dockerfile

User:
"Give me a Python program for a calculator."

Generate the simplest appropriate Python source file.

Do NOT automatically generate tests, README, gitignore,
dependency files, or infrastructure.

====================================================
WHEN MULTIPLE FILES ARE ACTUALLY NECESSARY
====================================================

Multiple files are allowed when the requested application
actually requires them.

For example:

User:
"Create a responsive website using HTML, CSS and JavaScript."

Generate the necessary frontend files:

FILE: index.html
FILE: style.css
FILE: script.js

Do not add Python, backend, tests, package files, Docker,
databases, or authentication unless requested or required.

====================================================
EXPLICIT FILE REQUESTS
====================================================

If the user explicitly requests files, follow that request.

Example:

"Create a Python project with main.py, tests and README."

Then generate:

FILE: main.py
FILE: tests/test_main.py
FILE: README.md

If the user says:

"Create a GitHub-ready project."

Then project-management files such as README.md and
.gitignore may be appropriate.

====================================================
DEPENDENCIES
====================================================

Only create dependency files when they are actually needed.

A Python program using only the Python standard library
does NOT need:

requirements.txt
pyproject.toml

For example:

import math
import sys
import os

These do not require a requirements.txt file.

If the application uses a third-party package such as:

requests
numpy
pandas
fastapi
flask

then create the appropriate dependency configuration when
it is necessary for the requested project.

====================================================
TESTING
====================================================

Do NOT automatically generate tests for every request.

Generate tests when:

- the user explicitly asks for tests,
- the planner explicitly requires tests,
- the project is explicitly requested as a testable/full project,
- or tests are genuinely necessary for the requested architecture.

For a simple request such as:

"Write a Python program to print prime numbers."

DO NOT generate tests unless requested.

====================================================
DOCUMENTATION
====================================================

Do NOT automatically generate README.md.

README.md should only be generated when:

- the user requests documentation,
- the user requests a complete project,
- the user requests a GitHub-ready project,
- or documentation is genuinely necessary.

====================================================
GITIGNORE
====================================================

Do NOT automatically generate .gitignore.

Only generate .gitignore when:

- the user asks for a complete/GitHub-ready project,
- the user explicitly requests it,
- or it is genuinely required by the requested project setup.

====================================================
FRAMEWORK AND ARCHITECTURE
====================================================

Never introduce technologies that the user did not request.

Do NOT automatically add:

- FastAPI
- Flask
- Django
- React
- Node.js
- Express
- PostgreSQL
- MongoDB
- Redis
- Docker
- Kubernetes
- JWT
- cloud services

unless required by the user's request.

Choose the simplest architecture that solves the problem.

====================================================
EXISTING PROJECT
====================================================

If an existing project is supplied:

- reuse existing files,
- preserve existing architecture,
- preserve existing APIs,
- preserve existing naming,
- preserve existing functionality,
- modify existing files when possible,
- create new files only when necessary.

Do NOT duplicate files.

====================================================
OUTPUT FORMAT
====================================================

Return ONLY actual project files.

Every file MUST use this format:

FILE: path/to/file.ext
<complete file content>

Example:

FILE: main.py
def main():
    print("Hello")

if __name__ == "__main__":
    main()

Do NOT use markdown code fences.

Do NOT provide explanations.

Do NOT provide analysis.

Do NOT provide a filename manifest.

Do NOT list filenames separately before their contents.

Do NOT create empty files.

Do NOT repeat file paths.

Do NOT repeat FILE headers.

====================================================
FILE COUNT RULE
====================================================

The number of generated files must be the smallest number
that correctly satisfies the user's request.

Requested files:
{requested_files_text or "None"}

Estimated files:
{getattr(task, "requested_files", None) and len(requested_files) or "Use the minimum necessary"}

If the request can be solved with ONE file, generate ONE file.

If the request requires THREE files, generate THREE files.

Do NOT create additional files merely for completeness.

====================================================
QUALITY RULES
====================================================

Every generated source file must:

- contain complete real code,
- be syntactically valid,
- be internally consistent,
- use the requested technology,
- avoid unnecessary dependencies,
- avoid TODO placeholders,
- avoid FIXME placeholders,
- avoid pseudocode,
- avoid fake implementations,
- avoid hardcoded secrets.

====================================================
SECURITY
====================================================

Never generate:

- real API keys,
- passwords,
- access tokens,
- private keys,
- secret certificates,
- real credentials,
- .env files containing secrets.

====================================================
FINAL RULE
====================================================

The USER REQUEST is the source of truth.

Generate exactly what is needed.

Nothing more.

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
            file_blocks,
             task,
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
        task: Optional[Task] = None,
    ) -> None:
        """
        Validate project completeness according to the user's
        actual request.

        Minimal code requests must not be forced to contain
        README.md, .gitignore, tests, or dependency files.

        Explicitly requested files remain authoritative.
        """

        generated_paths = {
            path.replace("\\", "/").strip().lower()
            for path, _ in file_blocks
        }

        generated_filenames = {
            path.split("/")[-1]
            for path in generated_paths
        }

        requested_files = set()

        if task is not None:
            requested_files = {
                str(path).replace("\\", "/").strip().lower()
                for path in (
                    getattr(task, "requested_files", None)
                    or []
                )
                if str(path).strip()
            }

        generation_mode = (
            str(
                getattr(
                    task,
                    "generation_mode",
                    "",
                )
                or ""
            )
            .strip()
            .lower()
        )

        # ------------------------------------------------------
        # Explicit file requests
        # ------------------------------------------------------

        if requested_files:

            missing_requested = []

            for requested in requested_files:

                if requested not in generated_paths:

                    requested_filename = (
                        requested.split("/")[-1]
                    )

                    if (
                        requested_filename
                        not in generated_filenames
                    ):
                        missing_requested.append(
                            requested
                        )

            if missing_requested:

                raise RuntimeError(
                    "Generated project is missing explicitly "
                    "requested file(s): "
                    + ", ".join(
                        sorted(
                            missing_requested
                        )
                    )
                )

        # ------------------------------------------------------
        # Test detection
        # ------------------------------------------------------

        test_files = [
            path
            for path, _ in file_blocks
            if self._is_test_file(path)
        ]

        # ------------------------------------------------------
        # Documentation detection
        # ------------------------------------------------------

        documentation_files = [
            path
            for path, _ in file_blocks
            if path.lower().split("/")[-1]
            in self.DOCUMENTATION_FILES
        ]

        # ------------------------------------------------------
        # Dependency detection
        # ------------------------------------------------------

        dependency_files = [
            path
            for path, _ in file_blocks
            if path.lower().split("/")[-1]
            in {
                "requirements.txt",
                "pyproject.toml",
                "package.json",
                "pom.xml",
                "build.gradle",
                "cargo.toml",
            }
        ]

        # ------------------------------------------------------
        # Determine whether this is a minimal code request.
        # ------------------------------------------------------

        minimal_code_mode = generation_mode in {
            "code",
            "script",
        }

        # ------------------------------------------------------
        # Minimal code/script requests
        #
        # No README, .gitignore, tests, or dependency files are
        # required unless explicitly requested.
        # ------------------------------------------------------

        if minimal_code_mode:

            logger.info(
                "Minimal code/script generation detected. "
                "Optional project files are not required."
            )

            logger.info(
                "Generated files: %d | tests=%d | "
                "documentation=%d | dependencies=%d",
                len(file_blocks),
                len(test_files),
                len(documentation_files),
                len(dependency_files),
            )

            return

        # ------------------------------------------------------
        # Website/frontend projects
        #
        # Do not force README/.gitignore/tests here either.
        # The technology validator handles the actual required
        # frontend source files.
        # ------------------------------------------------------

        project_type = str(
            getattr(
                task,
                "project_type",
                "",
            )
            or ""
        ).strip().lower()

        if project_type in {
            "web",
            "website",
            "frontend",
            "static_web",
        }:

            logger.info(
                "Frontend/web project detected. "
                "Optional documentation, gitignore and tests "
                "are not mandatory."
            )

            return

        # ------------------------------------------------------
        # Full project/application mode
        #
        # Only require README/.gitignore when the user explicitly
        # requested a full project or the planner selected a
        # project-oriented generation mode.
        # ------------------------------------------------------

        full_project_mode = generation_mode in {
            "project",
            "application",
        }

        if full_project_mode:

            if not documentation_files:

                logger.warning(
                    "Full project has no README/documentation."
                )

            if ".gitignore" not in generated_filenames:

                logger.warning(
                    "Full project has no .gitignore."
                )

            if not test_files:

                logger.info(
                    "No automated test files detected. "
                    "Tests are optional unless explicitly required."
                )

        logger.info(
            "Project completeness validation passed. "
            "Files=%d, tests=%d, documentation=%d, "
            "dependencies=%d",
            len(file_blocks),
            len(test_files),
            len(documentation_files),
            len(dependency_files),
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