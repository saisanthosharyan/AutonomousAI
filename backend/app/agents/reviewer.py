from __future__ import annotations

import re

from app.agents.base_agent import BaseAgent
from app.core.logger import logger
from app.services.llm.router import LLMRouter
from app.memory.memory_manager import MemoryManager
from app.project.project_context import ProjectContext


class ReviewerAgent(BaseAgent):
    """
    Reviews the generated project and provides actionable
    production-grade feedback.
    """

    MIN_REVIEW_LENGTH = 100

    REQUIRED_SECTIONS = [
        "Overall Summary",
        "Strengths",
        "Problems Found",
        "Final Score",
    ]

    def __init__(self, llm=None):
        # Optional constructor injection, mirrors PlannerAgent.
        super().__init__()
        self.llm = llm
        self.project_context = ProjectContext()

    async def run(
        self,
        code: str,
        project_directory: str | None = None,
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

        prompt = f"""
You are a Principal Software Architect performing a production-grade code review.

Your objective is to review the ENTIRE generated project and identify every issue
that could affect quality, correctness, security, scalability or deployment.

==================================================
PROJECT SOURCE CODE
==================================================

{code}

==================================================
PREVIOUS SUCCESSFUL REVIEWS
==================================================

{memory_context}

==================================================
REVIEW CHECKLIST
==================================================

Review the project for:

• Architecture
• Folder structure
• Naming conventions
• Readability
• Maintainability
• Code duplication
• Runtime bugs
• Syntax issues
• Missing files
• Missing dependencies
• Import problems
• API correctness
• Database design
• Authentication
• Authorization
• Logging
• Exception handling
• Configuration
• Environment variables
• Docker support
• Test coverage
• Security vulnerabilities
• Performance bottlenecks
• Scalability

==================================================
OUTPUT FORMAT
==================================================

## Overall Summary

Provide a short summary.

---

## Strengths

List the project's strengths.

---

## Problems Found

For every issue include:

- File
- Problem
- Reason
- Severity (Low / Medium / High)

---

## Possible Runtime Errors

List all possible runtime failures.

---

## Security Review

Check for:

- Hardcoded secrets
- SQL Injection
- XSS
- CSRF
- Command Injection
- Unsafe subprocess usage
- File upload vulnerabilities
- Authentication issues
- Authorization issues
- Sensitive data exposure
---

## Performance Review

Mention:

- Slow algorithms
- Duplicate processing
- Memory issues
- Blocking operations
- Expensive API calls

---

## Code Quality

Review:

- SOLID principles
- DRY principles
- Clean Architecture
- Modularization
- Naming
- Documentation

---

## Missing Files

Mention missing files such as:

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

---

## Final Suggestions

Provide concrete improvements that can be applied automatically.

---

## Final Score

Give a score out of 10.

==================================================
RULES
==================================================

- Do NOT rewrite the project.
- Do NOT generate source code.
- Be specific.
- Focus on actionable improvements.
- Mention both strengths and weaknesses.
- Prefer production-readiness over style opinions.
- Prioritize only the most important issues.
- Do NOT invent problems that do not exist.
- If something looks correct, say it is correct.
"""

        logger.info(
            "Reviewing generated project..."
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
            f"Review length: {len(review)} characters."
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

    @staticmethod
    def _extract_score(review: str) -> float | None:
        """
        Attempts to parse a numeric score (e.g. "9.6/10" or "Final Score: 9/10")
        out of the review text so it can be stored/searched separately.
        Returns None if no score could be confidently parsed.
        """

        match = re.search(
            r"Final Score[^\d]{0,20}(\d+(?:\.\d+)?)\s*/\s*10",
            review,
            re.IGNORECASE,
        )

        if not match:
            return None

        try:
            return float(match.group(1))
        except ValueError:
            return None