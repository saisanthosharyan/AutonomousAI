from __future__ import annotations

import re
from pathlib import Path

from app.agents.base_agent import BaseAgent
from app.core.logger import logger
from app.services.llm.router import LLMRouter
from app.memory.memory_manager import MemoryManager
from app.project.project_context import ProjectContext


class ReviewerAgent(BaseAgent):
    """
    Reviews the final generated project using the actual files on disk.
    """

    MIN_REVIEW_LENGTH = 100

    REQUIRED_SECTIONS = [
        "Overall Summary",
        "Strengths",
        "Problems Found",
        "Final Score",
    ]

    MAX_FILE_CHARS = 20000
    MAX_TOTAL_PROJECT_CHARS = 60000

    def __init__(self, llm=None):
        super().__init__()
        self.llm = llm
        self.project_context = ProjectContext()

    async def run(
        self,
        code: str,
        project_directory: str | None = None,
        original_request: str | None = None,
        memory: MemoryManager | None = None,
    ) -> str:

        logger.info("=" * 60)
        logger.info("Reviewer Agent Started")
        logger.info("=" * 60)

        if not code or not code.strip():
            raise ValueError(
                "ReviewerAgent received empty project code."
            )

        llm = self.llm or LLMRouter.get_llm()
        memory = memory or MemoryManager()

        memory_items = memory.retrieve(
            prompt=code[:4000],
            limit=5,
        )

        memory_context = memory.build_context(
            memory_items
        )

        project_context_text = self._build_project_context(
            project_directory,
            code,
        )

        original_request = (
            original_request.strip()
            if original_request
            else "Original user request was not provided."
        )

        prompt = f"""
You are a Principal Software Architect performing a factual code review
of a generated software project.

Your most important rule is:

ONLY report facts that are supported by the actual project files provided
in this prompt.

Do not invent files, APIs, dependencies, secrets, implementation details,
runtime behavior, or configuration.

If the source code shows that something is implemented correctly, explicitly
recognize that.

The generated project may intentionally be small. Do not penalize a project
for omitting production infrastructure, files, dependencies, tests, Docker,
CI/CD, authentication, databases, APIs, or other features unless those
things are actually required by the project scope or necessary for something
the project claims to implement.

A missing optional production enhancement is NOT a defect.

==================================================
ORIGINAL USER REQUEST
==================================================

{original_request}

==================================================
ACTUAL PROJECT CONTEXT
==================================================

{project_context_text}

==================================================
GENERATOR OUTPUT
==================================================

{code}

==================================================
PREVIOUS SUCCESSFUL REVIEWS
==================================================

{memory_context}

==================================================
REVIEW METHOD
==================================================

1. Inspect the actual project files first.
2. Identify the files that actually exist.
3. Verify claims against the source code.
4. Check HTML, CSS, JavaScript, Python, APIs, configuration,
   dependencies, tests, or other technologies only when they exist.
5. Do not assume an external API is used unless the source code actually
   calls that API.
6. Do not claim an API key exists unless an actual secret/key is visible
   in the source.
7. Do not claim a missing security control is a defect when the project
   does not expose the corresponding attack surface.
8. Do not require README.md, package.json, requirements.txt, Docker,
   CI/CD, tests, LICENSE, or similar files unless they are necessary for
   the requested project or explicitly part of its scope.
9. For static websites, inspect the actual HTML, CSS, and JavaScript.
10. For frontend projects, verify referenced local assets and scripts.
11. For backend projects, inspect routes, dependencies, configuration,
    error handling, and actual runtime-related code.
12. Distinguish actual defects from optional improvements.
13. Never downgrade the project because of a feature that was explicitly
    excluded by the project scope.
14. If the project is correct for its stated scope, say so.

==================================================
REVIEW CHECKLIST
==================================================

Review only applicable areas:

- Architecture
- Folder structure
- Naming conventions
- Readability
- Maintainability
- Code duplication
- Runtime bugs
- Syntax issues
- Missing required files
- Missing required dependencies
- Import problems
- API correctness
- Database design when a database exists
- Authentication when authentication exists
- Authorization when authorization exists
- Logging when applicable
- Exception handling when applicable
- Configuration
- Environment variables
- Security vulnerabilities
- Performance bottlenecks
- Scalability when relevant
- User-requested functionality
- Responsive behavior when relevant
- Accessibility when relevant

==================================================
OUTPUT FORMAT
==================================================

## Overall Summary

Provide a short factual summary of the final project.

---

## Strengths

List the functionality and implementation that is demonstrably correct.

---

## Problems Found

For every actual issue include:

- File
- Problem
- Reason
- Severity (Low / Medium / High)

Do not list optional enhancements as defects.

If there are no significant defects, say that clearly.

---

## Possible Runtime Errors

List only runtime failures supported by the actual source.

If none are evident, say:

"No concrete runtime errors identified from the reviewed source."

---

## Security Review

Check only applicable security risks.

Do not report SQL Injection, CSRF, authentication flaws, authorization flaws,
command injection, file upload vulnerabilities, or similar issues when the
project does not contain the corresponding functionality.

Do not claim a hardcoded secret unless an actual secret is present.

---

## Performance Review

Identify only evidence-based performance concerns.

If no significant performance concern is visible, say so.

---

## Code Quality

Review:

- Readability
- Maintainability
- Modularity
- Naming
- Duplication
- Documentation where relevant

Do not demand enterprise architecture from a deliberately small project.

---

## Missing Required Files

List only files that are actually required by the project scope but missing.

Do NOT automatically list:

README.md
requirements.txt
package.json
Dockerfile
docker-compose.yml
.env.example
tests
GitHub Actions
CI/CD
LICENSE

unless the project actually requires them.

---

## Final Suggestions

Provide concrete, relevant improvements.

Clearly distinguish optional improvements from actual defects.

---

## Final Score

Give a score out of 10 based on:

- Correctness
- Requested functionality
- Code quality
- Reliability
- Security where applicable
- Completeness relative to the actual project scope

Do not reduce the score merely because optional production infrastructure
is absent.

==================================================
STRICT FACTUAL RULES
==================================================

- Do NOT rewrite the project.
- Do NOT generate source code.
- Do NOT invent problems.
- Do NOT invent files.
- Do NOT invent APIs.
- Do NOT invent dependencies.
- Do NOT invent secrets.
- Do NOT assume external services.
- Do NOT assume requirements that were not stated or technically required.
- Verify every reported problem against actual source.
- Mention both strengths and weaknesses.
- Prefer correctness over generic production checklists.
- Prioritize actual issues.
- If something is correct, say it is correct.
"""

        logger.info(
            "Reviewing final generated project..."
        )

        try:
            review = await llm.generate(
                prompt
            )

        except Exception as exc:
            logger.exception(
                "Reviewer Agent generation failed."
            )

            raise RuntimeError(
                f"Failed to review project: {exc}"
            ) from exc

        if review is None:
            raise RuntimeError(
                "Reviewer Agent received None from LLM."
            )

        if not isinstance(review, str):
            review = str(review)

        review = review.strip()

        if not review:
            raise RuntimeError(
                "Reviewer Agent returned an empty review."
            )

        if len(review) < self.MIN_REVIEW_LENGTH:
            logger.warning(
                "Reviewer response appears unusually short."
            )

        missing_sections = [
            section
            for section in self.REQUIRED_SECTIONS
            if section not in review
        ]

        if missing_sections:
            logger.warning(
                "Reviewer response is missing expected sections: %s",
                missing_sections,
            )

        logger.info(
            "Review length: %s characters.",
            len(review),
        )

        logger.info(
            "Review completed successfully."
        )

        logger.info("=" * 60)
        logger.info("Reviewer Agent Finished")
        logger.info("=" * 60)

        score = self._extract_score(review)

        try:
            memory.save(
                memory_type="review",
                prompt=code[:4000],
                review=review,
                success=True,
                score=score,
            )

        except Exception:
            logger.exception(
                "Failed to save review memory."
            )

        return review

    def _build_project_context(
        self,
        project_directory: str | None,
        fallback_code: str,
    ) -> str:
        """
        Build a factual snapshot from the actual generated project.
        """

        if not project_directory:
            return (
                "Project directory was not provided. "
                "Use the generator output below as the available source."
            )

        try:
            root = Path(
                project_directory
            ).resolve()

            if not root.exists():
                logger.warning(
                    "Reviewer project directory does not exist: %s",
                    root,
                )

                return (
                    "The supplied project directory does not exist. "
                    "Use the generator output below as the available source."
                )

            if not root.is_dir():
                logger.warning(
                    "Reviewer project path is not a directory: %s",
                    root,
                )

                return (
                    "The supplied project path is not a directory. "
                    "Use the generator output below as the available source."
                )

            context = self.project_context.build(
                root
            )

            files = self.project_context.get_files()

            sections: list[str] = []

            sections.append(
                f"PROJECT ROOT: {root}"
            )

            sections.append(
                "FILES ACTUALLY PRESENT:"
            )

            for scanned_file in files:
                sections.append(
                    f"- {scanned_file.relative_path}"
                )

            sections.append(
                "\nACTUAL FILE CONTENTS:"
            )

            total_chars = 0

            for scanned_file in files:
                if total_chars >= self.MAX_TOTAL_PROJECT_CHARS:
                    sections.append(
                        "\n[Project content limit reached.]"
                    )
                    break

                file_path = Path(
                    scanned_file.path
                )

                try:
                    content = file_path.read_text(
                        encoding="utf-8"
                    )
                except UnicodeDecodeError:
                    try:
                        content = file_path.read_text(
                            encoding="utf-8",
                            errors="replace",
                        )
                    except Exception as exc:
                        logger.warning(
                            "Could not read project file %s: %s",
                            file_path,
                            exc,
                        )
                        continue
                except Exception as exc:
                    logger.warning(
                        "Could not read project file %s: %s",
                        file_path,
                        exc,
                    )
                    continue

                if len(content) > self.MAX_FILE_CHARS:
                    content = (
                        content[:self.MAX_FILE_CHARS]
                        + "\n[File content truncated.]"
                    )

                remaining = (
                    self.MAX_TOTAL_PROJECT_CHARS
                    - total_chars
                )

                if len(content) > remaining:
                    content = (
                        content[:remaining]
                        + "\n[Project content truncated.]"
                    )

                sections.append(
                    "\n"
                    f"--- FILE: {scanned_file.relative_path} ---\n"
                    f"{content}"
                )

                total_chars += len(content)

            summary = context.summary

            sections.append(
                "\nPROJECT SUMMARY:"
            )

            sections.append(
                str(summary)
            )

            return "\n".join(
                sections
            )

        except Exception as exc:
            logger.exception(
                "Failed to build reviewer project context."
            )

            return (
                "Failed to scan the project directory safely. "
                "Use the generator output below as the available source.\n"
                f"Scanner error: {exc}"
            )

    @staticmethod
    def _extract_score(
        review: str,
    ) -> float | None:
        """
        Attempts to parse a numeric score such as 9.6/10.
        """

        match = re.search(
            r"Final Score[^\d]{0,20}(\d+(?:\.\d+)?)\s*/\s*10",
            review,
            re.IGNORECASE,
        )

        if not match:
            return None

        try:
            return float(
                match.group(1)
            )
        except ValueError:
            return None
