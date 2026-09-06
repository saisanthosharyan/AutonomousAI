from __future__ import annotations

import asyncio
import time
from typing import Any

from app.agents.planner import PlannerAgent
from app.agents.coder import CoderAgent
from app.agents.reviewer import ReviewerAgent

from app.builders.project_builder import ProjectBuilder
from app.validators.project_validator import ProjectValidator

from app.models.task import Task
from app.core.logger import logger

from app.database.database import SessionLocal
from app.database.crud import create_project

from app.services.retry.retry_manager import RetryManager

from app.websocket.manager import manager
from app.memory.memory_manager import MemoryManager
from app.services.evaluator.evaluator import Evaluator
from app.services.run.run_manager import RunManager


class AgentOrchestrator:
    """
    Main autonomous workflow controller for AutoDev AI.

    Final pipeline:

        User Request
            ↓
        Planner Agent
            ↓
        Coder Agent
            ↓
        Project Builder
            ↓
        Execution
            ↓
        Execution Self-Healing
            ↓
        Automated Tests
            ↓
        Test Self-Healing
            ↓
        Final Validation
            ↓
        Final Review
            ↓
        Evaluation
            ↓
        Database Save
            ↓
        Final Result

    IMPORTANT:

        Validation and Review happen AFTER all repairs.

        This prevents the system from validating/reviewing an
        intermediate version of the project that may subsequently
        be changed by the FixerAgent.
    """

    TOTAL_STEPS = 9

    def __init__(self) -> None:
        # Shared memory across planner/coder/reviewer/repair stages.
        self.memory = MemoryManager()

        self.planner = PlannerAgent()
        self.coder = CoderAgent()
        self.reviewer = ReviewerAgent()

        self.builder = ProjectBuilder()
        self.validator = ProjectValidator()

        self.retry_manager = RetryManager(
            memory=self.memory
        )

        self.evaluator = Evaluator()

    # ==========================================================
    # PROGRESS HELPER
    # ==========================================================

    async def _progress(
        self,
        session_id: str | None,
        step: str,
        progress: int,
        message: str,
        run_id: str | None = None,
    ) -> None:
        """
        Persist and broadcast pipeline progress.

        Persistence/WebSocket failures must never crash the
        autonomous engineering pipeline.
        """

        # ------------------------------------------
        # Persist run state
        # ------------------------------------------

        if run_id:
            try:
                await asyncio.to_thread(
                    RunManager.update,
                    run_id,
                    status=(
                        "completed"
                        if progress >= 100
                        else "running"
                    ),
                    current_step=step,
                    progress=progress,
                    message=message,
                    started=True,
                    completed=progress >= 100,
                )

            except Exception:
                logger.exception(
                    "Failed to persist run progress."
                )

        # ------------------------------------------
        # WebSocket progress
        # ------------------------------------------

        if not session_id:
            return

        try:
            await manager.send_progress(
                session_id=session_id,
                step=step,
                progress=progress,
                message=message,
            )

        except Exception:
            logger.exception(
                "Failed to send websocket progress."
            )

    # ==========================================================
    # RUN LIFECYCLE
    # ==========================================================

    async def _update_run(
        self,
        run_id: str | None,
        *,
        status: str | None = None,
        current_step: str | None = None,
        progress: int | None = None,
        message: str | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        started: bool = False,
        completed: bool = False,
    ) -> None:
        """
        Safely persist run lifecycle state.
        """

        if not run_id:
            return

        try:
            await asyncio.to_thread(
                RunManager.update,
                run_id,
                status=status,
                current_step=current_step,
                progress=progress,
                message=message,
                result=result,
                error=error,
                started=started,
                completed=completed,
            )

        except Exception:
            logger.exception(
                "Failed to update run state."
            )

    async def _fail_run(
        self,
        run_id: str | None,
        error: str,
    ) -> None:
        """
        Mark a run as failed without allowing database
        persistence errors to affect the original failure.
        """

        await self._update_run(
            run_id,
            status="failed",
            current_step="Failed",
            progress=100,
            message="AutoDev-AI pipeline failed.",
            error=error,
            completed=True,
        )

    # ==========================================================
    # DEFAULT RESULT HELPERS
    # ==========================================================

    @staticmethod
    def _failed_test_result(
        message: str,
    ) -> dict[str, Any]:
        return {
            "success": False,
            "stdout": "",
            "stderr": message,
            "return_code": -1,
            "execution_time": 0,
        }

    @staticmethod
    def _failed_review(
        error: str,
    ) -> str:
        return f"Reviewer Agent failed: {error}"

    @staticmethod
    def _review_succeeded(
        review: str,
    ) -> bool:
        """
        ReviewerAgent returns a string.

        A non-empty reviewer failure message must not count
        as a successful review.
        """

        if not isinstance(review, str):
            return False

        review = review.strip()

        if not review:
            return False

        if review.startswith(
            "Reviewer Agent failed:"
        ):
            return False

        return True

    @staticmethod
    def _failed_validation(
        error: str,
    ) -> dict[str, Any]:
        return {
            "valid": False,
            "errors": [error],
            "warnings": [],
        }

    # ==========================================================
    # VALIDATION
    # ==========================================================

    async def _run_validation(
        self,
        project_path: str,
    ) -> dict[str, Any]:
        """
        Run final project validation.

        This is deliberately executed AFTER test repairs.
        """

        try:
            validation = await asyncio.to_thread(
                self.validator.validate,
                project_path,
            )

            validation = validation or {}

            logger.info(
                "Final project validation completed."
            )

            return validation

        except Exception as exc:
            logger.exception(
                "Project validation failed."
            )

            return self._failed_validation(
                str(exc)
            )

    # ==========================================================
    # REVIEW
    # ==========================================================

    async def _run_review(
        self,
        code: str,
    ) -> str:
        """
        Run final AI code review.

        This must happen after all execution/test repairs so
        the reviewer sees the final source.
        """

        try:
            review = await self.reviewer.run(
                code,
                memory=self.memory,
            )

            review = review or ""

            logger.info(
                "Final AI review completed."
            )

            return review

        except Exception as exc:
            logger.exception(
                "Reviewer Agent failed."
            )

            return self._failed_review(
                str(exc)
            )

    # ==========================================================
    # MAIN PIPELINE
    # ==========================================================

    async def execute(
        self,
        task: str,
        history: list | None = None,
        session_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:

        logger.info("=" * 60)
        logger.info("Starting AutoDev AI Pipeline")
        logger.info("=" * 60)

        if not task or not task.strip():
            raise ValueError(
                "Task cannot be empty."
            )

        pipeline_start = time.monotonic()

        await self._update_run(
            run_id,
            status="running",
            current_step="Starting",
            progress=0,
            message="AutoDev-AI pipeline started.",
            started=True,
        )

        stage_times: dict[str, float] = {}

        plan: Task | None = None
        code: str = ""
        project: dict[str, Any] = {}

        execution_result: dict[str, Any] = {}
        validation: dict[str, Any] = {}
        test_result: dict[str, Any] = {}
        review: str = ""
        evaluation: dict[str, Any] = {}

        debug_report: dict[str, Any] = {}
        retry_stats: dict[str, Any] = {}
        test_retry_stats: dict[str, Any] = {}

        # ======================================================
        # STEP 1 - PLANNING
        # ======================================================

        logger.info(
            "Step 1/9 - Planning..."
        )

        await self._progress(
            session_id,
            "Planning",
            10,
            "Generating implementation plan...",
            run_id,
        )

        stage_start = time.monotonic()

        try:
            plan = await self.planner.run(
                task,
                history,
            )

        except Exception as exc:
            logger.exception(
                "Planner Agent failed."
            )

            await self._fail_run(
                run_id,
                str(exc),
            )

            raise

        stage_times["planner"] = (
            time.monotonic() - stage_start
        )

        if plan is None:
            error = (
                "Planner failed to generate a task."
            )

            await self._fail_run(
                run_id,
                error,
            )

            raise RuntimeError(error)

        logger.info(
            "Planning completed: %s",
            plan.title,
        )

        await self._progress(
            session_id,
            "Planning",
            20,
            "Planning completed.",
            run_id,
        )

        # ======================================================
        # STEP 2 - CODING
        # ======================================================

        logger.info(
            "Step 2/9 - Generating code..."
        )

        await self._progress(
            session_id,
            "Coding",
            25,
            "Generating source code...",
            run_id,
        )

        stage_start = time.monotonic()

        try:
            code = await self.coder.run(
                plan,
                memory=self.memory,
            )

        except Exception as exc:
            logger.exception(
                "Coder Agent failed."
            )

            await self._fail_run(
                run_id,
                str(exc),
            )

            raise

        stage_times["coder"] = (
            time.monotonic() - stage_start
        )

        if not code or not code.strip():
            error = (
                "Coder failed to generate source code."
            )

            await self._fail_run(
                run_id,
                error,
            )

            raise RuntimeError(error)

        logger.info(
            "Generated %s characters of source code.",
            len(code),
        )

        await self._progress(
            session_id,
            "Coding",
            35,
            "Source code generated.",
            run_id,
        )

        # ======================================================
        # STEP 3 - BUILD PROJECT
        # ======================================================

        logger.info(
            "Step 3/9 - Building project..."
        )

        await self._progress(
            session_id,
            "Building",
            40,
            "Creating project structure...",
            run_id,
        )

        stage_start = time.monotonic()

        try:
            project = self.builder.build(
                project_name=plan.title,
                llm_output=code,
            )

        except Exception as exc:
            logger.exception(
                "Project Builder failed."
            )

            await self._fail_run(
                run_id,
                str(exc),
            )

            raise

        stage_times["builder"] = (
            time.monotonic() - stage_start
        )

        if not project:
            error = (
                "Project Builder returned no result."
            )

            await self._fail_run(
                run_id,
                error,
            )

            raise RuntimeError(error)

        if not project.get("project_path"):
            error = (
                "Project Builder did not return project_path."
            )

            await self._fail_run(
                run_id,
                error,
            )

            raise RuntimeError(error)

        if not project.get("zip_path"):
            error = (
                "Project Builder did not return zip_path."
            )

            await self._fail_run(
                run_id,
                error,
            )

            raise RuntimeError(error)

        logger.info(
            "Project created at: %s",
            project["project_path"],
        )

        await self._progress(
            session_id,
            "Building",
            50,
            "Project built successfully.",
            run_id,
        )

        # ======================================================
        # STEP 4 - EXECUTION + SELF-HEALING
        # ======================================================

        logger.info(
            "Step 4/9 - Executing project..."
        )

        await self._progress(
            session_id,
            "Execution",
            55,
            "Executing generated project...",
            run_id,
        )

        stage_start = time.monotonic()

        try:
            retry_result = (
                await self.retry_manager.execute_with_retry(
                    project=project,
                    code=code,
                )
            )

        except Exception as exc:
            logger.exception(
                "Project execution failed."
            )

            execution_result = {
                "success": False,
                "stdout": "",
                "stderr": str(exc),
                "return_code": -1,
                "execution_time": 0,
            }

            debug_report = {
                "success": False,
                "error": str(exc),
            }

            retry_result = None

        stage_times["execution"] = (
            time.monotonic() - stage_start
        )

        if retry_result is not None:

            if (
                not isinstance(
                    retry_result,
                    tuple,
                )
                or len(retry_result) != 5
            ):
                error = (
                    "RetryManager returned an invalid execution result. "
                    "Expected: "
                    "(execution_result, project, code, "
                    "debug_report, retry_stats)"
                )

                await self._fail_run(
                    run_id,
                    error,
                )

                raise RuntimeError(error)

            (
                execution_result,
                project,
                code,
                debug_report,
                retry_stats,
            ) = retry_result

            execution_result = (
                execution_result or {}
            )

            debug_report = (
                debug_report or {}
            )

            retry_stats = (
                retry_stats or {}
            )

        else:
            retry_stats = {
                "attempts": 0,
                "repairs": 0,
                "execution_failures": 1,
                "repeated_errors_detected": 0,
                "successful": False,
            }

        execution_result = (
            execution_result or {}
        )

        logger.info(
            "Execution stage completed."
        )

        await self._progress(
            session_id,
            "Execution",
            65,
            (
                "Execution succeeded. "
                "Starting automated test verification."
                if execution_result.get("success")
                else
                "Execution failed. "
                "Automated tests cannot verify the project."
            ),
            run_id,
        )

        # ======================================================
        # STEP 5 - TESTING + TEST SELF-HEALING
        # ======================================================
        #
        # IMPORTANT:
        #
        # We do NOT run validation/review concurrently with tests.
        #
        # Test repair can modify the project.
        #
        # Therefore:
        #
        #     Execute
        #        ↓
        #     Tests
        #        ↓
        #     Repair if necessary
        #        ↓
        #     Final validation
        #        ↓
        #     Final review
        #
        # This guarantees validation/review see the final code.

        logger.info(
            "Step 5/9 - Testing + test self-healing..."
        )

        await self._progress(
            session_id,
            "Testing",
            70,
            "Running automated tests and self-healing failures...",
            run_id,
        )

        stage_start = time.monotonic()

        if execution_result.get("success"):

            try:
                (
                    test_result,
                    project,
                    code,
                    test_debug_report,
                    test_retry_stats,
                ) = await self.retry_manager.test_with_retry(
                    project=project,
                    code=code,
                )

                test_result = (
                    test_result or {}
                )

                test_debug_report = (
                    test_debug_report or {}
                )

                test_retry_stats = (
                    test_retry_stats or {}
                )

                # Preserve both execution and test debugging
                # information in the final report.
                debug_report = {
                    "execution": debug_report,
                    "testing": test_debug_report,
                }

            except Exception as exc:
                logger.exception(
                    "Test self-healing pipeline failed."
                )

                test_result = (
                    self._failed_test_result(
                        str(exc)
                    )
                )

                test_retry_stats = {
                    "attempts": 0,
                    "repairs": 0,
                    "test_failures": 1,
                    "repeated_errors_detected": 0,
                    "successful": False,
                }

                debug_report = {
                    "execution": debug_report,
                    "testing": {
                        "error": str(exc),
                    },
                }

        else:
            logger.warning(
                "Execution did not succeed. "
                "Skipping test execution."
            )

            test_result = (
                self._failed_test_result(
                    "Execution failed. Tests skipped."
                )
            )

            test_retry_stats = {
                "attempts": 0,
                "repairs": 0,
                "test_failures": 0,
                "repeated_errors_detected": 0,
                "successful": False,
            }

            debug_report = {
                "execution": debug_report,
                "testing": {
                    "skipped": True,
                    "reason": (
                        "Execution failed."
                    ),
                },
            }

        stage_times["testing"] = (
            time.monotonic() - stage_start
        )

        test_result = (
            test_result or {}
        )

        test_retry_stats = (
            test_retry_stats or {}
        )

        logger.info(
            "Testing/self-healing stage completed."
        )

        await self._progress(
            session_id,
            "Testing",
            78,
            (
                "Automated tests passed."
                if test_result.get("success")
                else
                "Automated tests failed or were skipped."
            ),
            run_id,
        )

        # ======================================================
        # STEP 6 - FINAL VALIDATION
        # ======================================================
        #
        # Validation happens AFTER all test repairs.
        #
        # This is critical.
        #
        # The validator now sees the final project state.

        logger.info(
            "Step 6/9 - Final project validation..."
        )

        await self._progress(
            session_id,
            "Validation",
            82,
            "Validating final repaired project...",
            run_id,
        )

        stage_start = time.monotonic()

        validation = await self._run_validation(
            project["project_path"]
        )

        stage_times["validation"] = (
            time.monotonic() - stage_start
        )

        validation = (
            validation or {}
        )

        await self._progress(
            session_id,
            "Validation",
            85,
            (
                "Final project validation passed."
                if validation.get("valid")
                else
                "Final project validation reported issues."
            ),
            run_id,
        )

        # ======================================================
        # STEP 7 - FINAL REVIEW
        # ======================================================
        #
        # Reviewer sees the FINAL source code, including any
        # changes made by test self-healing.

        logger.info(
            "Step 7/9 - Final AI review..."
        )

        await self._progress(
            session_id,
            "Review",
            88,
            "Reviewing final repaired source code...",
            run_id,
        )

        stage_start = time.monotonic()

        review = await self._run_review(
            code
        )

        stage_times["review"] = (
            time.monotonic() - stage_start
        )

        review = (
            review or ""
        )

        await self._progress(
            session_id,
            "Review",
            90,
            "Final AI review completed.",
            run_id,
        )

        # ======================================================
        # STEP 8 - EVALUATION
        # ======================================================

        logger.info(
            "Step 8/9 - Evaluating final project..."
        )

        await self._progress(
            session_id,
            "Evaluation",
            92,
            "Evaluating final project state...",
            run_id,
        )

        stage_start = time.monotonic()

        try:
            evaluation = await asyncio.to_thread(
                self.evaluator.evaluate,
                project["project_path"],
            )

        except Exception as exc:
            logger.exception(
                "Project evaluation failed."
            )

            evaluation = {
                "overall_score": 0,
                "recommendation": (
                    "Evaluation failed."
                ),
                "error": str(exc),
            }

        stage_times["evaluation"] = (
            time.monotonic() - stage_start
        )

        evaluation = (
            evaluation or {}
        )

        logger.info(
            "Final project evaluation completed."
        )

        await self._progress(
            session_id,
            "Evaluation",
            95,
            "Final evaluation completed.",
            run_id,
        )

        # ======================================================
        # STEP 9 - SAVE PROJECT
        # ======================================================

        logger.info(
            "Step 9/9 - Saving project..."
        )

        await self._progress(
            session_id,
            "Saving",
            97,
            "Saving final project information...",
            run_id,
        )

        stage_start = time.monotonic()

        db = SessionLocal()

        try:
            create_project(
                db=db,
                session_id=session_id or "default",
                title=plan.title,
                prompt=task,
                project_path=project[
                    "project_path"
                ],
                zip_path=project[
                    "zip_path"
                ],
            )

            logger.info(
                "Project saved successfully."
            )

        except Exception:
            # Database failure must not destroy the generated project.
            logger.exception(
                "Failed to save project to database."
            )

        finally:
            db.close()

        stage_times["save"] = (
            time.monotonic() - stage_start
        )

        # ======================================================
        # FINALIZATION
        # ======================================================

        await self._progress(
            session_id,
            "Completed",
            99,
            "Finalizing project result...",
            run_id,
        )

        pipeline_time = (
            time.monotonic() - pipeline_start
        )

        logger.info("=" * 60)
        logger.info(
            "AutoDev AI Pipeline Finished in %.2fs",
            pipeline_time,
        )
        logger.info("=" * 60)

        # ======================================================
        # NORMALIZE RESULTS
        # ======================================================

        execution_result = (
            execution_result or {}
        )

        validation = (
            validation or {}
        )

        test_result = (
            test_result or {}
        )

        review = (
            review or ""
        )

        debug_report = (
            debug_report or {}
        )

        evaluation = (
            evaluation or {}
        )

        retry_stats = (
            retry_stats or {}
        )

        test_retry_stats = (
            test_retry_stats or {}
        )

        # ======================================================
        # FINAL SUCCESS
        # ======================================================
        #
        # A project is successful ONLY when:
        #
        # 1. It executes successfully.
        # 2. Tests pass.
        # 3. Validation passes.
        # 4. Reviewer produces a valid review.
        #
        # Evaluation score is reported but is not allowed to
        # override deterministic execution/test/validation gates.

        final_success = bool(
            execution_result.get(
                "success",
                False,
            )
            and test_result.get(
                "success",
                False,
            )
            and validation.get(
                "valid",
                False,
            )
            and self._review_succeeded(
                review
            )
        )

        # ======================================================
        # FINAL RESULT
        # ======================================================

        final_result = {
            "success": final_success,

            "plan": plan.model_dump(),

            "project": project,

            "execution": execution_result,

            "validation": validation,

            "tests": test_result,

            "debug_report": debug_report,

            "retry_stats": retry_stats,

            "test_retry_stats": test_retry_stats,

            "review": review,

            "evaluation": evaluation,

            # IMPORTANT:
            # This is the final code after all repairs.
            "improved_code": code,

            "metrics": {
                "pipeline_time": pipeline_time,
                "stage_times": stage_times,
                "retry_stats": retry_stats,
                "test_retry_stats": test_retry_stats,
            },
        }

        # ======================================================
        # FINAL RUN STATE
        # ======================================================

        await self._update_run(
            run_id,
            status=(
                "completed"
                if final_success
                else "failed"
            ),
            current_step="Completed",
            progress=100,
            message=(
                "Project generation completed successfully."
                if final_success
                else
                "Project generation completed with failures."
            ),
            result=final_result,
            completed=True,
        )

        return final_result