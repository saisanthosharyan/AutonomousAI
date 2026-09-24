from __future__ import annotations

import asyncio
import difflib
import re
import time
from typing import Optional

from app.agents.fixer_agent import FixerAgent
from app.builders.project_builder import ProjectBuilder
from app.core.logger import logger

from app.services.execution.execution_manager import ExecutionManager
from app.services.testing.testing_manager import TestManager
from app.services.debugger.debug_manager import DebugManager
from app.services.repair.repair_report import RepairReporter
from app.memory.memory_manager import MemoryManager
from app.project.project_analyzer import ProjectAnalyzer


# ----------------------------------------------------------------------
# Error categorization
# ----------------------------------------------------------------------

_ERROR_PATTERNS = [
    ("SyntaxError", re.compile(r"SyntaxError", re.I)),
    ("NameError", re.compile(r"NameError", re.I)),
    (
        "ImportError",
        re.compile(r"ImportError|ImportModuleError", re.I),
    ),
    (
        "ModuleNotFoundError",
        re.compile(r"ModuleNotFoundError", re.I),
    ),
    (
        "DatabaseError",
        re.compile(
            r"OperationalError|IntegrityError|DatabaseError|"
            r"psycopg2|sqlite3\.",
            re.I,
        ),
    ),
    (
        "PermissionError",
        re.compile(r"PermissionError|Permission denied", re.I),
    ),
    (
        "APIError",
        re.compile(
            r"APIError|HTTPError|status code (4|5)\d\d",
            re.I,
        ),
    ),
    (
        "DockerError",
        re.compile(r"docker|container", re.I),
    ),
    (
        "DependencyError",
        re.compile(
            r"No matching distribution|pip install|version conflict",
            re.I,
        ),
    ),
    ("TypeError", re.compile(r"TypeError", re.I)),
    ("ValueError", re.compile(r"ValueError", re.I)),
    ("AttributeError", re.compile(r"AttributeError", re.I)),
    ("KeyError", re.compile(r"KeyError", re.I)),
    (
        "TimeoutError",
        re.compile(r"TimeoutError|timed out", re.I),
    ),
    (
        "AssertionError",
        re.compile(r"AssertionError", re.I),
    ),
]


def categorize_error(stderr: str) -> str:
    """
    Categorize an error using common Python/runtime error patterns.
    """

    if not stderr:
        return "Unknown"

    for category, pattern in _ERROR_PATTERNS:
        if pattern.search(stderr):
            return category

    return "RuntimeError"


class RetryManager:
    """
    Autonomous execution + repair manager.

    Responsibilities:

        1. Execute generated projects.
        2. Detect execution failures.
        3. Debug failures.
        4. Ask FixerAgent to repair the project.
        5. Rebuild the project.
        6. Re-execute the repaired project.
        7. Run tests after execution succeeds.
        8. Repair test failures automatically.
        9. Rebuild and retest repaired projects.
       10. Repair actionable reviewer findings.
       11. Rebuild, validate, and re-review repaired projects.

    Execution loop:

        Execute
          ↓
        failure?
          ↓ yes
        Debug
          ↓
        FixerAgent
          ↓
        Rebuild
          ↓
        Execute again

    Test loop:

        Tests
          ↓
        failure?
          ↓ yes
        Debug
          ↓
        FixerAgent
          ↓
        Rebuild
          ↓
        Tests again

    Review loop:

        Review
          ↓
        actionable problems?
          ↓ yes
        FixerAgent
          ↓
        Rebuild
          ↓
        Validate
          ↓
        Review again
    """

    SIMILARITY_THRESHOLD = 0.999

    def __init__(
        self,
        max_retries: int = 3,
        memory: Optional[MemoryManager] = None,
        llm=None,
    ):
        self.max_retries = max(1, max_retries)

        self.executor = ExecutionManager()
        self.tester = TestManager()
        self.debugger = DebugManager()
        self.builder = ProjectBuilder()

        self.llm = llm
        self.fixer = FixerAgent(llm=llm)

        self.memory = memory or MemoryManager()
        self.project_analyzer = ProjectAnalyzer()

    # ==================================================================
    # EXECUTION RETRY LOOP
    # ==================================================================

    async def execute_with_retry(
        self,
        project: dict,
        code: str,
        review=None,
    ):
        """
        Execute a project and automatically repair execution failures.
        """

        if not project:
            raise ValueError(
                "Project information cannot be empty."
            )

        if not project.get("project_path"):
            raise ValueError(
                "Project path is missing."
            )

        if not code or not code.strip():
            raise ValueError(
                "Generated project code cannot be empty."
            )

        current_project = project
        current_code = code

        execution_result = None
        debug_report = {}

        retry_stats = {
            "attempts": 0,
            "repairs": 0,
            "execution_failures": 0,
            "repeated_errors_detected": 0,
            "successful": False,
        }

        repair_history = []
        timeline = []
        previous_errors = []

        for attempt in range(
            1,
            self.max_retries + 1,
        ):
            logger.info("=" * 60)
            logger.info(
                "Execution Attempt %s/%s",
                attempt,
                self.max_retries,
            )
            logger.info("=" * 60)

            retry_stats["attempts"] += 1

            attempt_start = time.monotonic()

            try:
                execution_result = self.executor.run(
                    current_project["project_path"]
                )

            except Exception as exc:
                logger.exception(
                    "Execution crashed."
                )

                execution_result = {
                    "success": False,
                    "stdout": "",
                    "stderr": str(exc),
                    "return_code": -1,
                    "execution_time": 0,
                }

            if hasattr(execution_result, "to_dict"):
                execution_result = (
                    execution_result.to_dict()
                )

            elif not isinstance(
                execution_result,
                dict,
            ):
                logger.warning(
                    "ExecutionManager returned unexpected "
                    "result type: %s",
                    type(execution_result).__name__,
                )

                execution_result = {
                    "success": False,
                    "stdout": "",
                    "stderr": (
                        "Invalid execution result type: "
                        f"{type(execution_result).__name__}"
                    ),
                    "return_code": -1,
                    "execution_time": 0,
                }

            elapsed = (
                time.monotonic()
                - attempt_start
            )

            timeline.append(
                {
                    "attempt": attempt,
                    "execution_time": execution_result.get(
                        "execution_time",
                        elapsed,
                    ),
                }
            )

            if execution_result.get("success"):
                logger.info(
                    "Project executed successfully "
                    "on attempt %s.",
                    attempt,
                )

                retry_stats["successful"] = True

                try:
                    self.memory.save(
                        memory_type="execution_success",
                        prompt=current_project.get(
                            "title",
                            "Generated Project",
                        ),
                        success=True,
                    )
                except Exception:
                    logger.exception(
                        "Failed to save success memory."
                    )

                debug_report = {
                    **debug_report,
                    "retry_stats": retry_stats,
                    "repair_history": repair_history,
                    "timeline": timeline,
                }

                return (
                    execution_result,
                    current_project,
                    current_code,
                    debug_report,
                    retry_stats,
                )

            logger.warning(
                "Execution failed on attempt %s.",
                attempt,
            )

            retry_stats[
                "execution_failures"
            ] += 1

            stderr = execution_result.get(
                "stderr",
                "",
            )

            stdout = execution_result.get(
                "stdout",
                "",
            )

            if stderr:
                logger.error(stderr)

            if stdout:
                logger.info(stdout)

            combined_error = "\n".join(
                part
                for part in [
                    stderr,
                    stdout,
                ]
                if part
            )

            category = categorize_error(
                combined_error
            )

            if (
                combined_error
                and combined_error in previous_errors
            ):
                retry_stats[
                    "repeated_errors_detected"
                ] += 1

                logger.warning(
                    "Identical execution error seen again "
                    "(category=%s).",
                    category,
                )

                debug_report = {
                    "category": category,
                    "summary": (
                        "Repeated identical error "
                        "across execution attempts."
                    ),
                    "stdout": stdout,
                    "stderr": stderr,
                    "return_code": execution_result.get(
                        "return_code",
                        -1,
                    ),
                    "retry_stats": retry_stats,
                    "repair_history": repair_history,
                    "timeline": timeline,
                }

                break

            if combined_error:
                previous_errors.append(
                    combined_error
                )

            debug_report = self._analyze_error(
                execution_result,
                category,
            )

            debug_report["attempt"] = attempt

            try:
                self.memory.save(
                    memory_type="execution_failure",
                    prompt=current_project.get(
                        "title",
                        "Generated Project",
                    ),
                    error=stderr,
                    success=False,
                    category=category,
                    attempt=attempt,
                )
            except Exception:
                logger.exception(
                    "Failed to save execution failure."
                )

            if attempt >= self.max_retries:
                logger.error(
                    "Maximum execution retry attempts reached."
                )
                break

            repair_result = await self._repair_project(
                current_project=current_project,
                current_code=current_code,
                debug_report=debug_report,
                repair_history=repair_history,
                retry_count=attempt,
                category=category,
                error=stderr,
                review=review,
                repair_type="execution",
            )

            if not repair_result["success"]:
                debug_report = {
                    **debug_report,
                    "repair_error": repair_result.get(
                        "error",
                        "Unknown repair failure.",
                    ),
                }
                break

            current_project = repair_result[
                "project"
            ]

            current_code = repair_result[
                "code"
            ]

            repair_history.append(
                repair_result["history"]
            )

            retry_stats["repairs"] += 1

            logger.info(
                "Execution repair applied. "
                "Project will be executed again."
            )

        logger.error(
            "Project failed after %s execution attempt(s).",
            retry_stats["attempts"],
        )

        if execution_result is None:
            execution_result = {
                "success": False,
                "stdout": "",
                "stderr": "Execution never started.",
                "return_code": -1,
                "execution_time": 0,
            }

        try:
            self.memory.save(
                memory_type="retry_failed",
                prompt=current_project.get(
                    "title",
                    "Generated Project",
                ),
                error=execution_result.get(
                    "stderr",
                    "",
                ),
                success=False,
            )

        except Exception:
            logger.exception(
                "Failed to save retry failure memory."
            )

        retry_stats["successful"] = False

        debug_report = {
            **debug_report,
            "retry_stats": retry_stats,
            "repair_history": repair_history,
            "timeline": timeline,
        }

        return (
            execution_result,
            current_project,
            current_code,
            debug_report,
            retry_stats,
        )

    # ==================================================================
    # TEST + REPAIR LOOP
    # ==================================================================

    async def test_with_retry(
        self,
        project: dict,
        code: str,
        review=None,
    ):
        """
        Run project tests and automatically repair test failures.
        """

        if not project:
            raise ValueError(
                "Project information cannot be empty."
            )

        if not project.get("project_path"):
            raise ValueError(
                "Project path is missing."
            )

        if not code or not code.strip():
            raise ValueError(
                "Generated project code cannot be empty."
            )

        current_project = project
        current_code = code

        test_result = None
        debug_report = {}

        test_stats = {
            "attempts": 0,
            "repairs": 0,
            "test_failures": 0,
            "repeated_errors_detected": 0,
            "successful": False,
        }

        repair_history = []
        timeline = []
        previous_errors = []

        for attempt in range(
            1,
            self.max_retries + 1,
        ):
            logger.info("=" * 60)
            logger.info(
                "Test Attempt %s/%s",
                attempt,
                self.max_retries,
            )
            logger.info("=" * 60)

            test_stats["attempts"] += 1

            attempt_start = time.monotonic()

            try:
                test_result = await asyncio.to_thread(
                    self.tester.run,
                    current_project["project_path"],
                )

            except Exception as exc:
                logger.exception(
                    "Test execution crashed."
                )

                test_result = {
                    "success": False,
                    "stdout": "",
                    "stderr": str(exc),
                    "return_code": -1,
                    "execution_time": 0,
                }

            if hasattr(test_result, "to_dict"):
                test_result = (
                    test_result.to_dict()
                )

            elif not isinstance(
                test_result,
                dict,
            ):
                logger.warning(
                    "TestManager returned unexpected "
                    "result type: %s",
                    type(test_result).__name__,
                )

                test_result = {
                    "success": False,
                    "stdout": "",
                    "stderr": (
                        "Invalid test result type: "
                        f"{type(test_result).__name__}"
                    ),
                    "return_code": -1,
                    "execution_time": 0,
                }

            elapsed = (
                time.monotonic()
                - attempt_start
            )

            timeline.append(
                {
                    "attempt": attempt,
                    "execution_time": test_result.get(
                        "execution_time",
                        elapsed,
                    ),
                }
            )

            if test_result.get("success"):
                logger.info(
                    "All project tests passed "
                    "on attempt %s.",
                    attempt,
                )

                test_stats["successful"] = True

                try:
                    self.memory.save(
                        memory_type="test_success",
                        prompt=current_project.get(
                            "title",
                            "Generated Project",
                        ),
                        success=True,
                        attempt=attempt,
                    )
                except Exception:
                    logger.exception(
                        "Failed to save test success memory."
                    )

                return (
                    test_result,
                    current_project,
                    current_code,
                    {
                        **debug_report,
                        "test_stats": test_stats,
                        "repair_history": repair_history,
                        "timeline": timeline,
                    },
                    test_stats,
                )

            test_stats["test_failures"] += 1

            logger.warning(
                "Tests failed on attempt %s.",
                attempt,
            )

            stdout = test_result.get(
                "stdout",
                "",
            )

            stderr = test_result.get(
                "stderr",
                "",
            )

            combined_error = "\n".join(
                part
                for part in [
                    stderr,
                    stdout,
                ]
                if part
            )

            if stdout:
                logger.info(
                    "Test stdout:\n%s",
                    stdout,
                )

            if stderr:
                logger.error(
                    "Test stderr:\n%s",
                    stderr,
                )

            category = categorize_error(
                combined_error
            )

            if (
                combined_error
                and combined_error in previous_errors
            ):
                test_stats[
                    "repeated_errors_detected"
                ] += 1

                logger.warning(
                    "Identical test failure detected again "
                    "(category=%s).",
                    category,
                )

                debug_report = {
                    "category": category,
                    "summary": (
                        "Repeated identical test failure "
                        "across repair attempts."
                    ),
                    "stdout": stdout,
                    "stderr": stderr,
                    "return_code": test_result.get(
                        "return_code",
                        -1,
                    ),
                    "test_result": test_result,
                }

                break

            if combined_error:
                previous_errors.append(
                    combined_error
                )

            debug_report = self._analyze_error(
                test_result,
                category,
            )

            debug_report["attempt"] = attempt
            debug_report["failure_type"] = "test_failure"
            debug_report["test_result"] = test_result

            try:
                self.memory.save(
                    memory_type="test_failure",
                    prompt=current_project.get(
                        "title",
                        "Generated Project",
                    ),
                    error=combined_error[:5000],
                    success=False,
                    category=category,
                    attempt=attempt,
                )
            except Exception:
                logger.exception(
                    "Failed to save test failure memory."
                )

            if attempt >= self.max_retries:
                logger.error(
                    "Maximum test repair attempts reached."
                )
                break

            logger.info(
                "Tests failed. Requesting AI implementation repair..."
            )

            repair_result = await self._repair_project(
                current_project=current_project,
                current_code=current_code,
                debug_report=debug_report,
                repair_history=repair_history,
                retry_count=attempt,
                category=category,
                error=combined_error,
                review=review,
                tests=test_result,
                repair_type="test",
            )

            if not repair_result["success"]:
                debug_report = {
                    **debug_report,
                    "repair_error": repair_result.get(
                        "error",
                        "Unknown test repair failure.",
                    ),
                }
                break

            current_project = repair_result[
                "project"
            ]

            current_code = repair_result[
                "code"
            ]

            repair_history.append(
                repair_result["history"]
            )

            test_stats["repairs"] += 1

            logger.info(
                "Test repair applied successfully. "
                "Tests will run again."
            )

        logger.error(
            "Project tests failed after %s attempt(s).",
            test_stats["attempts"],
        )

        if test_result is None:
            test_result = {
                "success": False,
                "stdout": "",
                "stderr": "Tests never started.",
                "return_code": -1,
                "execution_time": 0,
            }

        test_stats["successful"] = False

        try:
            self.memory.save(
                memory_type="test_retry_failed",
                prompt=current_project.get(
                    "title",
                    "Generated Project",
                ),
                error=test_result.get(
                    "stderr",
                    "",
                ),
                success=False,
            )

        except Exception:
            logger.exception(
                "Failed to save test retry failure memory."
            )

        debug_report = {
            **debug_report,
            "test_stats": test_stats,
            "repair_history": repair_history,
            "timeline": timeline,
        }

        return (
            test_result,
            current_project,
            current_code,
            debug_report,
            test_stats,
        )

    # ==================================================================
    # REVIEW + REPAIR LOOP
    # ==================================================================

    async def review_with_retry(
        self,
        project: dict,
        code: str,
        review: str,
        reviewer,
        validator,
        task=None,
        max_review_retries: int = 2,
    ):
        """
        Repair actionable reviewer findings.

        Flow:

            Review
              ↓
            actionable problems?
              ↓ yes
            FixerAgent
              ↓
            Rebuild
              ↓
            Validate
              ↓
            Review again

        Review suggestions are not automatically treated as defects.
        The repair loop is triggered only when the Problems Found
        section contains an actual issue.
        """

        if not project:
            raise ValueError(
                "Project information cannot be empty."
            )

        if not project.get("project_path"):
            raise ValueError(
                "Project path is missing."
            )

        if not code or not code.strip():
            raise ValueError(
                "Generated project code cannot be empty."
            )

        current_project = project
        current_code = code
        current_review = review or ""

        repair_history = []

        review_stats = {
            "attempts": 0,
            "repairs": 0,
            "successful": True,
        }

        for attempt in range(
            1,
            max_review_retries + 1,
        ):
            problems = self._extract_review_problems(
                current_review
            )

            if not problems:
                logger.info(
                    "Review repair loop completed. "
                    "No actionable reviewer problems found."
                )

                return {
                    "project": current_project,
                    "code": current_code,
                    "review": current_review,
                    "repair_history": repair_history,
                    "review_stats": review_stats,
                }

            review_stats["attempts"] += 1

            logger.warning(
                "Reviewer found actionable problems. "
                "Starting review repair attempt %s/%s.",
                attempt,
                max_review_retries,
            )

            debug_report = {
                "type": "review",
                "category": "ReviewFinding",
                "summary": (
                    "Reviewer identified actionable problems "
                    "in the generated project."
                ),
                "review": current_review,
                "problems": problems,
            }

            repair_result = await self._repair_project(
                current_project=current_project,
                current_code=current_code,
                debug_report=debug_report,
                repair_history=repair_history,
                retry_count=attempt,
                category="ReviewFinding",
                error=problems[:10000],
                review=current_review,
                tests=None,
                repair_type="review",
            )

            if not repair_result.get("success"):
                logger.warning(
                    "Review repair attempt %s failed: %s",
                    attempt,
                    repair_result.get(
                        "error",
                        "Unknown repair failure.",
                    ),
                )

                review_stats["successful"] = False

                return {
                    "project": current_project,
                    "code": current_code,
                    "review": current_review,
                    "repair_history": repair_history,
                    "review_stats": review_stats,
                    "error": repair_result.get(
                        "error",
                        "Review repair failed.",
                    ),
                }

            current_project = repair_result[
                "project"
            ]

            current_code = repair_result[
                "code"
            ]

            repair_history.append(
                repair_result["history"]
            )

            review_stats["repairs"] += 1

            logger.info(
                "Review repair applied successfully."
            )

            # ----------------------------------------------------------
            # Validate repaired project
            # ----------------------------------------------------------

            try:
                generation_mode = (
                    getattr(
                        task,
                        "generation_mode",
                        None,
                    )
                    if task is not None
                    else None
                )

                requested_files = (
                    getattr(
                        task,
                        "requested_files",
                        None,
                    )
                    if task is not None
                    else None
                )

                validation = await asyncio.to_thread(
                    validator.validate,
                    current_project["project_path"],
                    generation_mode,
                    requested_files,
                )

            except Exception as exc:
                logger.exception(
                    "Validation failed after review repair."
                )

                review_stats["successful"] = False

                return {
                    "project": current_project,
                    "code": current_code,
                    "review": current_review,
                    "repair_history": repair_history,
                    "review_stats": review_stats,
                    "error": (
                        "Validation failed after review repair: "
                        f"{exc}"
                    ),
                }

            if not validation or not validation.get(
                "valid",
                False,
            ):
                logger.warning(
                    "Review repair produced an invalid project."
                )

                review_stats["successful"] = False

                return {
                    "project": current_project,
                    "code": current_code,
                    "review": current_review,
                    "repair_history": repair_history,
                    "review_stats": review_stats,
                    "validation": validation or {},
                    "error": (
                        "Review repair produced an "
                        "invalid project."
                    ),
                }

            logger.info(
                "Validation passed after review repair."
            )

            # ----------------------------------------------------------
            # Review repaired project
            # ----------------------------------------------------------

            try:
                current_review = await reviewer(
                    current_code,
                    current_project["project_path"],
                    task,
                )

            except Exception as exc:
                logger.exception(
                    "Reviewer failed after review repair."
                )

                review_stats["successful"] = False

                return {
                    "project": current_project,
                    "code": current_code,
                    "review": current_review,
                    "repair_history": repair_history,
                    "review_stats": review_stats,
                    "error": (
                        "Reviewer failed after review repair: "
                        f"{exc}"
                    ),
                }

            current_review = (
                current_review
                if isinstance(
                    current_review,
                    str,
                )
                else str(current_review)
            )

            current_review = current_review.strip()

            logger.info(
                "Re-review completed after repair attempt %s.",
                attempt,
            )

        # --------------------------------------------------------------
        # Maximum review repairs reached
        # --------------------------------------------------------------

        remaining_problems = (
            self._extract_review_problems(
                current_review
            )
        )

        if remaining_problems:
            review_stats["successful"] = False

            logger.warning(
                "Maximum review repair attempts reached "
                "with actionable problems remaining."
            )

        else:
            logger.info(
                "Review repair loop completed successfully."
            )

        return {
            "project": current_project,
            "code": current_code,
            "review": current_review,
            "repair_history": repair_history,
            "review_stats": review_stats,
        }

    # ==================================================================
    # REVIEW PARSING
    # ==================================================================

    @staticmethod
    def _extract_review_problems(
        review: str,
    ) -> str:
        """
        Extract the Problems Found section from a reviewer report.

        Optional suggestions are deliberately excluded.
        """

        if not review:
            return ""

        marker = "## Problems Found"

        if marker not in review:
            return ""

        problems = review.split(
            marker,
            1,
        )[1]

        next_sections = [
            "## Possible Runtime Errors",
            "## Security Review",
            "## Performance Review",
            "## Code Quality",
            "## Missing Required Files",
            "## Final Suggestions",
            "## Final Score",
        ]

        positions = [
            problems.find(section)
            for section in next_sections
            if problems.find(section) >= 0
        ]

        if positions:
            problems = problems[
                :min(positions)
            ]

        problems = problems.strip()

        if not problems:
            return ""

        problems = "\n".join(
            line.strip()
            for line in problems.splitlines()
            if line.strip() not in {"---", "***", "___"}
        ).strip()

        if not problems:
            return ""

        normalized = problems.lower()

        clean_values = {
            "none",
            "none.",
            "n/a",
            "n/a.",
            "no issues",
            "no issues.",
            "no problems",
            "no problems.",
            "no actionable problems",
            "no actionable problems.",
            "no significant defects",
            "no significant issues",
            "no significant problems",
            "no actual issues",
            "no problems found",
            "no problems found.",
            "no defects found",
            "there are no significant defects",
            "there are no significant issues",
        }

        if normalized in clean_values:
            return ""

        return problems

    # ==================================================================
    # SHARED ERROR ANALYSIS
    # ==================================================================

    def _analyze_error(
        self,
        result: dict,
        category: str,
    ) -> dict:
        """
        Safely run DebugManager against execution/test results.
        """

        stdout = result.get(
            "stdout",
            "",
        )

        stderr = result.get(
            "stderr",
            "",
        )

        try:
            debug_report = self.debugger.analyze(
                result
            )

            if not isinstance(
                debug_report,
                dict,
            ):
                debug_report = {
                    "summary": str(
                        debug_report
                    ),
                    "stdout": stdout,
                    "stderr": stderr,
                    "return_code": result.get(
                        "return_code",
                        -1,
                    ),
                }

        except Exception as exc:
            logger.exception(
                "Debug analysis failed."
            )

            debug_report = {
                "error": str(exc),
                "summary": (
                    "Debug analysis failed; "
                    "raw failure information preserved."
                ),
                "stdout": stdout,
                "stderr": stderr,
                "return_code": result.get(
                    "return_code",
                    -1,
                ),
            }

        debug_report.setdefault(
            "category",
            category,
        )

        return debug_report

    # ==================================================================
    # SHARED AI REPAIR
    # ==================================================================

    async def _repair_project(
        self,
        current_project: dict,
        current_code: str,
        debug_report: dict,
        repair_history: list,
        retry_count: int,
        category: str,
        error: str,
        review=None,
        tests=None,
        repair_type: str = "execution",
    ) -> dict:
        """
        Ask FixerAgent to repair the current project, validate the
        returned source, rebuild the project, and save repair metadata.

        IMPORTANT:

        When repair_type == "test", tests are passed to FixerAgent.

        FixerAgent is expected to repair the implementation rather than
        changing tests merely to make them pass.
        """

        old_code = current_code

        try:
            project_type = self.project_analyzer.detect(
                current_project["project_path"]
            )
        except Exception:
            logger.exception(
                "Project type detection failed."
            )
            project_type = None

        try:
            fixed_code = await self.fixer.run(
                code=current_code,
                review=review,
                tests=tests,
                execution_error=debug_report,
                retry_history=repair_history,
                retry_count=retry_count,
                memory=self.memory,
                project_directory=(
                    current_project[
                        "project_path"
                    ]
                ),
                project_type=project_type,
                save_debug=True,
            )

        except Exception as exc:
            logger.exception(
                "Fixer Agent failed during %s repair.",
                repair_type,
            )

            return {
                "success": False,
                "error": str(exc),
            }

        if not fixed_code:
            logger.error(
                "Fixer returned empty code."
            )

            return {
                "success": False,
                "error": (
                    "Fixer returned empty repair."
                ),
            }

        fixed_code = fixed_code.strip()

        if fixed_code == old_code.strip():
            logger.error(
                "Fixer returned code identical to "
                "the previous version."
            )

            return {
                "success": False,
                "error": (
                    "Fixer returned identical code."
                ),
            }

        similarity = difflib.SequenceMatcher(
            None,
            old_code,
            fixed_code,
        ).ratio()

        logger.info(
            "Repair type: %s",
            repair_type,
        )

        logger.info(
            "Old source size: %s",
            len(old_code),
        )

        logger.info(
            "New source size: %s",
            len(fixed_code),
        )

        logger.info(
            "Repair similarity: %.4f",
            similarity,
        )

        if similarity >= self.SIMILARITY_THRESHOLD:
            logger.warning(
                "Repair is extremely similar to "
                "the previous source."
            )

        history_entry = {
            "attempt": retry_count,
            "category": category,
            "error": error[:5000],
            "repair_type": repair_type,
            "similarity": round(
                similarity,
                4,
            ),
        }

        try:
            self.memory.save(
                memory_type=(
                    "test_repair"
                    if repair_type == "test"
                    else "repair"
                ),
                prompt=current_project.get(
                    "title",
                    "Generated Project",
                ),
                error=error[:5000],
                fix=fixed_code[:3000],
                success=False,
                category=category,
                attempt=retry_count,
            )
        except Exception:
            logger.exception(
                "Failed to save repair memory."
            )

        try:
            updated_project = (
                self.builder.rebuild(
                    current_project[
                        "project_path"
                    ],
                    fixed_code,
                )
            )

            if not updated_project:
                raise RuntimeError(
                    "Project rebuild returned no project."
                )

        except Exception as exc:
            logger.exception(
                "Project rebuild failed."
            )

            return {
                "success": False,
                "error": str(exc),
            }

        try:
            reporter = RepairReporter(
                updated_project[
                    "project_path"
                ]
            )

            reporter.save(
                old_code=old_code,
                new_code=fixed_code,
                debug_report={
                    **debug_report,
                    "repair_type": repair_type,
                    "similarity": round(
                        similarity,
                        4,
                    ),
                },
            )

            logger.info(
                "%s repair report saved.",
                repair_type.capitalize(),
            )

        except Exception:
            logger.exception(
                "Failed to save repair report."
            )

        try:
            self.memory.save(
                memory_type=(
                    "test_repair_applied"
                    if repair_type == "test"
                    else "repair_applied"
                ),
                prompt=updated_project.get(
                    "title",
                    "Generated Project",
                ),
                error=error[:5000],
                fix=fixed_code[:3000],
                review=(
                    "Automatic "
                    f"{repair_type} repair rebuilt; "
                    "awaiting verification."
                ),
                success=False,
                category=category,
                attempt=retry_count,
            )

        except Exception:
            logger.exception(
                "Failed to save repair-applied memory."
            )

        return {
            "success": True,
            "project": updated_project,
            "code": fixed_code,
            "history": history_entry,
        }
