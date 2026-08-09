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

    Expected LLM output format:

    FILE: app.py
    print("Hello")

    FILE: requirements.txt
    fastapi
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

        # Use the shared MemoryManager passed in by the orchestrator so
        # generations build on past learnings. Falls back to a fresh
        # instance if the agent is run standalone (no history in that
        # case).
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

        logger.info("Sending project generation request to LLM...")

        try:

            response = await llm.generate(prompt)

        except Exception as exc:

            logger.exception(
                f"Project generation failed: {exc}"
            )

            raise RuntimeError(
                "LLM project generation failed."
            ) from exc

        if response is None:
            raise RuntimeError(
                "LLM returned None."
            )

        response = str(response).strip()

        if not response:
            raise RuntimeError(
                "LLM returned an empty response."
            )

        logger.info(
            f"Raw response size: {len(response)} characters"
        )

        response = self._normalize_response(response)

        self._validate_response(response)

        logger.info("Project generation successful.")
        logger.info("=" * 70)
        logger.info("Coder Agent Finished")
        logger.info("=" * 70)

        try:
            memory.save(
                memory_type="generation",
                prompt=f"{task.title}\n{task.description}",
                language="Python",
                framework="FastAPI",
                review=(
                    f"Generated {len(self.get_file_blocks(response))} files."
                ),
                success=True,
            )
        except Exception:
            logger.exception("Failed to save generation memory.")

        return response

    # ==========================================================
    # TASK VALIDATION
    # ==========================================================

    def _validate_task(self, task: Task) -> None:

        if task is None:
            raise ValueError(
                "Task cannot be None."
            )

        if not task.title or not task.title.strip():
            raise ValueError(
                "Task title cannot be empty."
            )

        if not task.description or not task.description.strip():
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
        """
        Analyze an existing project directory (if given) and return
        a compact LLM-ready context string. Never raises — analysis
        failures fall back to an empty context so generation can
        still proceed.
        """

        if not project_directory:
            return ""

        logger.info(
            "Analyzing existing project..."
        )

        try:

            self.project_context.build(project_directory)

            return self.project_context.build_llm_context(
                max_chars=8000
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

        return f"""
You are AutoDev AI.

You are an elite autonomous software engineer.

Generate a COMPLETE executable software project.

====================================================
PROJECT
====================================================

Title:
{task.title}

Description:
{task.description}

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
RULES
====================================================

• Generate COMPLETE source code.

• Never generate partial implementations.

• Never generate TODO comments.

• Never generate FIXME comments.

• Never generate pseudocode.

• Never generate placeholder functions.

• Every import must exist.

• Every dependency must exist.

• Every source file must compile.

• Never create real secrets.

• Never create .env.

Use .env.example instead.

====================================================
EXISTING PROJECT RULES
====================================================

If an existing project is provided above:

• Modify existing files whenever possible.

• Reuse the existing architecture.

• Never recreate files that already exist unless a change is required.

• Preserve the existing coding style.

• Preserve existing APIs.

• Preserve existing naming conventions.

• Only generate new files when strictly necessary.

• Do not regenerate the entire project from scratch.

====================================================
PYTHON
====================================================

If using Python:

• Generate requirements.txt when needed.

• NEVER include built-in Python modules in requirements.txt
  (tkinter, sqlite3, json, os, sys, typing, pathlib, logging,
  asyncio, etc.) — these are part of the standard library and
  will fail to install via pip.

• Use pytest for testing.

• Entry point must execute correctly.

• No syntax errors.

====================================================
NODE
====================================================

If using Node:

• package.json must be valid.

• Imports must match dependencies.

• npm start must work.

====================================================
OUTPUT FORMAT
====================================================

Return ONLY project files.

Every file MUST begin exactly with:

FILE: relative/path

Example:

FILE: app.py

print("Hello")

FILE: requirements.txt

fastapi

====================================================
STRICT RULES
====================================================

Start immediately with FILE:

Do NOT use markdown.

Do NOT use code fences.

Do NOT explain anything.

Do NOT summarize.

Do NOT write analysis.

Do NOT output anything except FILE blocks.

Every imported package must exist.

Every dependency must be installed.

Every generated file must be executable.

Return ONLY FILE blocks.
"""

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

        # Remove opening markdown fence
        response = re.sub(
            r"^\s*```(?:\w+)?\s*",
            "",
            response,
            flags=re.IGNORECASE,
        )

        # Remove closing markdown fence
        response = re.sub(
            r"\s*```\s*$",
            "",
            response,
        )

        response = response.strip()

        # Remove any text before the first FILE:
        first_file = response.find("FILE:")

        if first_file == -1:
            raise RuntimeError(
                "LLM response contains no FILE blocks."
            )

        if first_file > 0:

            logger.warning(
                "Discarding text before first FILE block."
            )

            response = response[first_file:]

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
        Removes accidental language labels.

        Example:

        FILE: app.py
        python

        becomes

        FILE: app.py
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
        Splits a generated project into FILE blocks.

        Returns

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

    # ==========================================================
    # DEBUG HELPER
    # ==========================================================

    def get_file_blocks(
        self,
        response: str,
    ) -> List[Tuple[str, str]]:
        """
        Public helper for debugging/testing.
        """

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
        """
        Validate the generated project before returning it.
        """

        if not response:
            raise RuntimeError(
                "Generated project is empty."
            )

        if len(response) < self.MIN_RESPONSE_LENGTH:
            raise RuntimeError(
                "Generated project is too small."
            )

        if not response.startswith("FILE:"):
            raise RuntimeError(
                "Project must start with 'FILE:'."
            )

        file_blocks = self._extract_file_blocks(
            response
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

            self._validate_file_path(path)

            normalized = path.lower()

            if normalized in seen:
                raise RuntimeError(
                    f"Duplicate file detected: {path}"
                )

            seen.add(normalized)

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
                f"Path too long: {path}"
            )

        normalized = path.replace("\\", "/").strip()

        if normalized.startswith("/"):
            raise RuntimeError(
                f"Absolute Unix path not allowed: {path}"
            )

        if re.match(r"^[A-Za-z]:", normalized):
            raise RuntimeError(
                f"Absolute Windows path not allowed: {path}"
            )

        parts = normalized.split("/")

        if ".." in parts:
            raise RuntimeError(
                f"Directory traversal detected: {path}"
            )

        if any(part.strip() == "" for part in parts):
            raise RuntimeError(
                f"Invalid path: {path}"
            )

        filename = parts[-1]

        if "." not in filename:
            raise RuntimeError(
                f"Filename has no extension: {path}"
            )

        lower = normalized.lower()

        # Allow .env.example
        if lower == ".env.example":
            logger.debug("Allowed path: %s", path)
            return

        # Block only exact dangerous filenames
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

        # Block dangerous directories
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

        # Block dangerous extensions
        forbidden_extensions = {
            ".pem",
            ".key",
            ".pyc",
        }

        for ext in forbidden_extensions:
            if filename.lower().endswith(ext):
                raise RuntimeError(
                    f"Forbidden file generated: {path}"
                )

        logger.debug(
            "Validated path: %s",
            path,
        )