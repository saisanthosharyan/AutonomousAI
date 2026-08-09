from __future__ import annotations

import difflib
import re
import time
from typing import Optional

from app.agents.fixer import FixerAgent
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
    ("ImportError", re.compile(r"ImportError|ImportModuleError", re.I)),
    ("ModuleNotFoundError", re.compile(r"ModuleNotFoundError", re.I)),
    ("DatabaseError", re.compile(r"OperationalError|IntegrityError|DatabaseError|psycopg2|sqlite3\.", re.I)),
    ("PermissionError", re.compile(r"PermissionError|Permission denied", re.I)),
    ("APIError", re.compile(r"APIError|HTTPError|status code (4|5)\d\d", re.I)),
    ("DockerError", re.compile(r"docker|container", re.I)),
    ("DependencyError", re.compile(r"No matching distribution|pip install|version conflict", re.I)),
    ("TypeError", re.compile(r"TypeError", re.I)),
    ("ValueError", re.compile(r"ValueError", re.I)),
    ("AttributeError", re.compile(r"AttributeError", re.I)),
    ("KeyError", re.compile(r"KeyError", re.I)),
    ("TimeoutError", re.compile(r"TimeoutError|timed out", re.I)),
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
    Executes a generated project and automatically repairs it
    when execution fails.

    This is the ONLY repair engine used by the pipeline. FixManager
    (app/services/fixer/fix_manager.py) is intentionally not used
    here to avoid running two independent, overlapping repair
    systems against the same project.
    """

    # Fixer output that is >= this similar to the previous attempt is
    # treated as a no-op repair (cosmetic-only change) and stops the loop.
    SIMILARITY_THRESHOLD = 0.98

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

        # Use the shared MemoryManager passed in by the orchestrator so
        # repair memory persists across Coder / Reviewer / Fixer. Falls
        # back to a fresh instance if run standalone.
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

        # ------------------------------------------------------------
        # Tracking state (new)
        # ------------------------------------------------------------
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
                f"Execution Attempt {attempt}/{self.max_retries}"
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
                execution_result = execution_result.to_dict()

            elif not isinstance(execution_result, dict):
                logger.warning(
                    "ExecutionManager returned unexpected result type: %s",
                    type(execution_result).__name__,
                )

                execution_result = {
                    "success": False,
                    "stdout": "",
                    "stderr": (
                        f"Invalid execution result type: "
                        f"{type(execution_result).__name__}"
                    ),
                    "return_code": -1,
                    "execution_time": 0,
                }

            elapsed = time.monotonic() - attempt_start
            timeline.append(
                {
                    "attempt": attempt,
                    "execution_time": execution_result.get(
                        "execution_time", elapsed
                    ),
                }
            )

            # ------------------------------------------
            # SUCCESS
            # ------------------------------------------

            if execution_result.get("success"):

                logger.info(
                    f"Project executed successfully on attempt {attempt}."
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
                f"Execution failed on attempt {attempt}."
            )

            retry_stats["execution_failures"] += 1

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

            category = categorize_error(stderr)

            # ------------------------------------------
            # REPEATED ERROR DETECTION
            # ------------------------------------------

            if stderr and stderr in previous_errors:

                retry_stats["repeated_errors_detected"] += 1

                logger.warning(
                    f"Identical error seen again (category={category}); "
                    f"repair is not making progress. Stopping early."
                )

                debug_report = {
                    "category": category,
                    "summary": "Repeated identical error across attempts.",
                    "stdout": stdout,
                    "stderr": stderr,
                    "return_code": execution_result.get("return_code", -1),
                    "retry_stats": retry_stats,
                    "repair_history": repair_history,
                    "timeline": timeline,
                }

                break

            if stderr:
                previous_errors.append(stderr)

            # ------------------------------------------
            # DEBUG
            # ------------------------------------------

            try:

                debug_report = self.debugger.analyze(
                    execution_result
                )

                if not isinstance(
                    debug_report,
                    dict,
                ):
                    debug_report = {
                        "summary": str(debug_report),
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

            # Enrich debug report (new fields)
            debug_report.setdefault("category", category)
            debug_report["attempt"] = attempt

            # ------------------------------------------
            # SAVE FAILURE MEMORY
            # ------------------------------------------

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
                    "Maximum retry attempts reached."
                )

                break

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
                break

            fixed_code = fixed_code.strip()

            if fixed_code == old_code:

                logger.warning(
                    "Fixer returned identical code."
                )

                break

            # ------------------------------------------
            # SIMILARITY CHECK (prevents wasting retries
            # on near-cosmetic changes)
            # ------------------------------------------

            similarity = difflib.SequenceMatcher(
                None,
                old_code,
                fixed_code,
            ).ratio()

            if similarity > self.SIMILARITY_THRESHOLD:

                logger.warning(
                    f"Fixer returned a near-identical repair "
                    f"(similarity={similarity:.4f}); stopping to avoid "
                    f"wasting retries on cosmetic-only changes."
                )

                debug_report = {
                    **debug_report,
                    "repair_error": (
                        f"Repair too similar to previous code "
                        f"(similarity={similarity:.4f})."
                    ),
                }

                break

            logger.info(
                f"Old size: {len(old_code)}"
            )

            logger.info(
                f"New size: {len(fixed_code)}"
            )

            logger.info(
                f"Repair similarity to previous code: {similarity:.4f}"
            )

            repair_history.append(
                {
                    "attempt": attempt,
                    "category": category,
                    "error": stderr,
                    "similarity": round(similarity, 4),
                }
            )

            retry_stats["repairs"] += 1

            # ------------------------------------------
            # SAVE REPAIR MEMORY
            # ------------------------------------------

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

            try:

                updated_project = self.builder.rebuild(
                    current_project["project_path"],
                    fixed_code,
                )

                if not updated_project:
                    raise RuntimeError(
                        "Project rebuild failed."
                    )

                current_project = updated_project
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

            # ==================================================
            # SAVE REPAIR REPORT
            # ==================================================

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

            # ------------------------------------------
            # SAVE REPAIR-APPLIED MEMORY
            #
            # NOTE: renamed from "successful_repair" -> "repair_applied".
            # At this point we only know the rebuild succeeded, not that
            # the fix actually resolves the failure -- that's only known
            # once the next execution attempt runs. Calling this
            # "successful" was misleading; the true success memory is
            # still written above under "execution_success" once a
            # subsequent attempt passes.
            # ------------------------------------------

            try:

                self.memory.save(
                    memory_type="repair_applied",
                    prompt=current_project.get(
                        "title",
                        "Generated Project",
                    ),
                    error=stderr,
                    fix=fixed_code[:3000],
                    review="Automatic repair rebuilt; awaiting re-execution.",
                    success=False,
                    category=category,
                    attempt=attempt,
                )

            except Exception:

                logger.exception(
                    "Failed to save repair-applied memory."
                )

            logger.info(
                "Repaired project will now be executed again."
            )

        # ======================================================
        # FAILED AFTER ALL RETRIES
        # ======================================================

        logger.error(
            f"Project failed after "
            f"{self.max_retries} execution attempts."
        )

        if execution_result is None:

            execution_result = {
                "success": False,
                "stdout": "",
                "stderr": (
                    "Execution never started."
                ),
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