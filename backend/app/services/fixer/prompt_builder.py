from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from app.core.logger import logger


class PromptBuilder:
    """
    Builds a structured repair prompt for the LLM.

    The prompt contains:

    - Original user request
    - Project structure
    - Existing project files
    - Execution result
    - Debug report

    The LLM must only repair the project and return
    corrected files.
    """

    MAX_FILE_SIZE = 20000

    def build(
        self,
        user_request: str,
        project_path: str,
        execution_result: Dict,
        debug_report: Dict,
    ) -> str:

        logger.info("=" * 60)
        logger.info("Building repair prompt")
        logger.info("=" * 60)

        project = Path(project_path).resolve()

        structure = self._project_structure(project)

        files = self._collect_files(project)

        prompt = f"""
You are an expert software engineer.

The generated project failed during execution.

====================================================
ORIGINAL USER REQUEST
====================================================

{user_request}

====================================================
PROJECT STRUCTURE
====================================================

{structure}

====================================================
EXECUTION RESULT
====================================================

Success:
{execution_result.get("success")}

Return Code:
{execution_result.get("return_code")}

STDOUT

{execution_result.get("stdout","")}

STDERR

{execution_result.get("stderr","")}

====================================================
DEBUG REPORT
====================================================

Category:
{debug_report.get("category","")}

Summary:
{debug_report.get("summary","")}

Recommendation:
{debug_report.get("recommendation","")}

====================================================
CURRENT PROJECT FILES
====================================================

{files}

====================================================
YOUR TASK
====================================================
Repair ONLY the broken application files.

IMPORTANT FILE PROTECTION RULES:

- NEVER modify files inside tests/ or test/.
- NEVER modify files matching test_*.py.
- NEVER modify files matching *_test.py.
- NEVER delete tests.
- NEVER weaken, remove, rewrite, or bypass tests.
- Tests are authoritative and must remain unchanged.
- If a test is failing, fix the application code instead.
- Only return application files that actually require changes.

Do NOT remove working functionality.

Do NOT rewrite the entire project.

Only modify what is necessary.

Prefer the smallest possible repair.

Return your response EXACTLY using this format:

FILE: relative/path/to/file.py
<complete file contents>
END FILE

FILE: another/file.txt
<complete file contents>
END FILE

Do not include explanations.

Return only FILE blocks.
"""

        logger.info("Repair prompt built successfully.")

        return prompt.strip()

    # =======================================================
    # PROJECT STRUCTURE
    # =======================================================

    def _project_structure(
        self,
        project: Path,
    ) -> str:

        paths = []

        for path in sorted(project.rglob("*")):

            if any(part in self.IGNORE_DIRS for part in path.parts):
                continue

            if path.is_file():

                paths.append(
                    str(path.relative_to(project))
                )

        return "\n".join(paths)

    # =======================================================
    # COLLECT FILES
    # =======================================================

    def _collect_files(
        self,
        project: Path,
    ) -> str:

        sections: List[str] = []

        for file in sorted(project.rglob("*")):

            if not file.is_file():
                continue

            if any(part in self.IGNORE_DIRS for part in file.parts):
                continue

            if file.suffix.lower() in self.IGNORE_SUFFIXES:
                continue

            try:

                text = file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )

            except Exception:

                continue

            if len(text) > self.MAX_FILE_SIZE:

                text = (
                    text[: self.MAX_FILE_SIZE]
                    + "\n\n...TRUNCATED..."
                )

            sections.append(
                f"""
====================================================
FILE: {file.relative_to(project)}
====================================================

{text}
"""
            )

        return "\n".join(sections)