from __future__ import annotations

import difflib
import re
import time
from typing import Optional

from app.agents.fixer_agent import FixerAgent
from app.builders.project_builder import ProjectBuilder
from app.core.logger import logger

from app.services.execution.execution_manager import ExecutionManager
from app.services.debugger.debug_manager import DebugManager
from app.services.repair.repair_report import RepairReporter
from app.memory.memory_manager import MemoryManager


# ----------------------------------------------------------------------
# Error categorization
# ----------------------------------------------------------------------

_ERROR_PATTERNS = [
    ("SyntaxError", re.compile(r"SyntaxError", re.I)),
    (
        "NameError",
        re.compile(r"NameError", re.I),
    ),
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
    if not stderr:
        return "Unknown"

    for category, pattern in _ERROR_PATTERNS:
        if pattern.search(stderr):
            return category

    return "RuntimeError"


class RetryManager:
    """
    Executes a generated project and automatically repairs it.

    RetryManager is the main execution/repair orchestration layer.

    FixerAgent performs the actual AI repair.

    The important distinction is:

        RetryManager retry
            =
        execute repaired project again

    while:

        FixerAgent retry
            =
        ask the LLM again when the generated repair is unusable.
    """

    SIMILARITY_THRESHOLD = 0.999

    def __init__(
        self,
        max_retries: int = 3,
        memory: Optional[MemoryManager] = None,
    ):
        self.max_retries = max(
            1,
            max_retries,
        )

        self.executor = ExecutionManager()
        self.debugger = DebugManager()
        self.builder = ProjectBuilder()
        self.fixer = FixerAgent()

        self.memory = memory or MemoryManager()

    async def execute_with_retry(
        self,
        project: dict,
        code: str,
        review=None,
    ):
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

            # --------------------------------------------------
            # SUCCESS
            # --------------------------------------------------

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

            category = categorize_error(combined_error)

            # --------------------------------------------------
            # Repeated execution error detection
            # --------------------------------------------------

            if combined_error and combined_error in previous_errors:
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
                previous_errors.append(combined_error)

            # --------------------------------------------------
            # DEBUG
            # --------------------------------------------------

            try:
                debug_report = self.debugger.analyze(
                    execution_result
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
                        "return_code": execution_result.get(
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
                    "stdout": stdout,
                    "stderr": stderr,
                    "return_code": execution_result.get(
                        "return_code",
                        -1,
                    ),
                }

            debug_report.setdefault(
                "category",
                category,
            )

            debug_report["attempt"] = attempt

            # --------------------------------------------------
            # FAILURE MEMORY
            # --------------------------------------------------

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

            # --------------------------------------------------
            # No more execution retries
            # --------------------------------------------------

            if attempt >= self.max_retries:
                logger.error(
                    "Maximum retry attempts reached."
                )
                break

            # --------------------------------------------------
            # AI REPAIR
            # --------------------------------------------------

            logger.info(
                "Requesting AI repair..."
            )

            old_code = current_code

            try:
                fixed_code = await self.fixer.run(
                    code=current_code,
                    review=review,
                    execution_error=debug_report,
                    memory=self.memory,

                    # IMPORTANT:
                    # Give FixerAgent enough context to inspect
                    # the actual generated project.
                    project_directory=(
                        current_project[
                            "project_path"
                        ]
                    ),

                    # This test is Python.
                    # In the production pipeline this should come
                    # from the detected project type if available.
                    project_type="python",

                    retry_history=repair_history,

                    retry_count=attempt,

                    # Enable during development/debugging.
                    save_debug=True,
                )

            except Exception as exc:
                logger.exception(
                    "Fixer Agent failed."
                )

                debug_report = {
                    **debug_report,
                    "repair_error": str(exc),
                }

                break

            if not fixed_code:
                logger.error(
                    "Fixer returned empty repair."
                )
                break

            fixed_code = fixed_code.strip()

            if fixed_code == old_code.strip():
                logger.error(
                    "Fixer returned identical code "
                    "after its internal repair retries."
                )

                debug_report = {
                    **debug_report,
                    "repair_error": (
                        "Fixer returned identical "
                        "code."
                    ),
                }

                break

            # --------------------------------------------------
            # Similarity
            # --------------------------------------------------

            similarity = difflib.SequenceMatcher(
                None,
                old_code,
                fixed_code,
            ).ratio()

            logger.info(
                "Old size: %s",
                len(old_code),
            )

            logger.info(
                "New size: %s",
                len(fixed_code),
            )

            logger.info(
                "Repair similarity: %.4f",
                similarity,
            )

            if (
                similarity
                >= self.SIMILARITY_THRESHOLD
            ):
                logger.warning(
                    "Repair is extremely similar to "
                    "the previous source."
                )

            repair_history.append(
                {
                    "attempt": attempt,
                    "category": category,
                    "error": combined_error,
                    "similarity": round(
                        similarity,
                        4,
                    ),
                }
            )

            retry_stats["repairs"] += 1

            # --------------------------------------------------
            # Repair memory
            # --------------------------------------------------

            try:
                self.memory.save(
                    memory_type="repair",
                    prompt=current_project.get(
                        "title",
                        "Generated Project",
                    ),
                    error=stderr,
                    fix=fixed_code[:3000],
                    success=False,
                    category=category,
                    attempt=attempt,
                )
            except Exception:
                logger.exception(
                    "Failed to save repair memory."
                )

            # --------------------------------------------------
            # Rebuild project
            # --------------------------------------------------

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
                        "Project rebuild failed."
                    )

                current_project = (
                    updated_project
                )

                current_code = fixed_code

                logger.info(
                    "Project rebuilt successfully."
                )

            except Exception as exc:
                logger.exception(
                    "Project rebuild failed."
                )

                debug_report = {
                    **debug_report,
                    "repair_error": str(exc),
                }

                break

            # --------------------------------------------------
            # Repair report
            # --------------------------------------------------

            try:
                reporter = RepairReporter(
                    current_project[
                        "project_path"
                    ]
                )

                reporter.save(
                    old_code=old_code,
                    new_code=fixed_code,
                    debug_report=debug_report,
                )

                logger.info(
                    "Repair report saved successfully."
                )

            except Exception:
                logger.exception(
                    "Failed to save repair report."
                )

            # --------------------------------------------------
            # Repair applied memory
            # --------------------------------------------------

            try:
                self.memory.save(
                    memory_type="repair_applied",
                    prompt=current_project.get(
                        "title",
                        "Generated Project",
                    ),
                    error=stderr,
                    fix=fixed_code[:3000],
                    review=(
                        "Automatic repair rebuilt; "
                        "awaiting re-execution."
                    ),
                    success=False,
                    category=category,
                    attempt=attempt,
                )

            except Exception:
                logger.exception(
                    "Failed to save repair-applied memory."
                )

            logger.info(
                "Repaired project will now be "
                "executed again."
            )

        # ======================================================
        # FAILED
        # ======================================================

        logger.error(
            "Project failed after %s "
            "execution attempt(s).",
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