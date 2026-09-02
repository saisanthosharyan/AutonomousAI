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
from app.services.testing.testing_manager import TestManager

from app.websocket.manager import manager
from app.memory.memory_manager import MemoryManager
from app.services.evaluator.evaluator import Evaluator
from app.services.run.run_manager import RunManager

class AgentOrchestrator:
    """
    Main autonomous workflow controller for AutoDev AI.

    Pipeline:

        User Request
            ↓
        Planner Agent
            ↓
        Coder Agent
            ↓
        Project Builder
            ↓
        Execution / Retry Manager
            ↓
        Validation / Testing / Review
            ↓
        Evaluation
            ↓
        Database Save
            ↓
        Final Result

    RetryManager already owns the self-healing loop:

        Execute
            ↓
        Debug
            ↓
        FixerAgent
            ↓
        ProjectBuilder.rebuild()
            ↓
        Re-execute
            ↓
        Retry / Success
    """

    TOTAL_STEPS = 9

    def __init__(self) -> None:
        # One shared MemoryManager is passed to components that need
        # shared project/review context.
        self.memory = MemoryManager()

        self.planner = PlannerAgent()
        self.coder = CoderAgent()
        self.reviewer = ReviewerAgent()

        self.builder = ProjectBuilder()
        self.validator = ProjectValidator()

        self.retry_manager = RetryManager(
            memory=self.memory
        )

        self.tester = TestManager()
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

        Run persistence must never crash the pipeline.
        WebSocket failures must also never crash the pipeline.
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
        # Send WebSocket progress
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
    # RUN LIFECYCLE HELPERS
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

        Run persistence must never crash the autonomous
        engineering pipeline.
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
        """
        Reviewer failures are represented as strings because
        ReviewerAgent.run() returns a review string.
        """

        return f"Reviewer Agent failed: {error}"

    @staticmethod
    def _review_succeeded(
        review: str,
    ) -> bool:
        """
        Determine whether the reviewer actually produced a
        successful review.

        Reviewer failures are represented as strings so the
        response schema remains consistent. However, an error
        string must not be considered a successful review merely
        because it is non-empty.
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
    # TIMING HELPER
    # ==========================================================

    @staticmethod
    async def _timed(
        coro,
        label: str,
        stage_times: dict[str, float],
    ):
        """
        Await a coroutine while recording its wall-clock duration.

        Safe for concurrent asyncio.gather() execution because
        each worker writes to a different stage_times key.
        """

        start = time.monotonic()

        result = await coro

        stage_times[label] = (
            time.monotonic() - start
        )

        return result

    # ==========================================================
    # VALIDATION
    # ==========================================================

    async def _run_validation(
        self,
        project_path: str,
    ) -> dict[str, Any]:

        try:
            validation = await asyncio.to_thread(
                self.validator.validate,
                project_path,
            )

            validation = validation or {}

            logger.info(
                "Project validation completed."
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
    # TESTING
    # ==========================================================

    async def _run_testing(
        self,
        execution_result: dict[str, Any],
        project_path: str,
    ) -> dict[str, Any]:

        if not (
            execution_result
            and execution_result.get("success")
        ):

            logger.warning(
                "Skipping automated tests because "
                "project execution failed."
            )

            return self._failed_test_result(
                "Execution failed. Tests skipped."
            )

        try:
            test_result = await asyncio.to_thread(
                self.tester.run,
                project_path,
            )

            test_result = (
                test_result
                or self._failed_test_result(
                    "Test manager returned no result."
                )
            )

            logger.info(
                "Automated testing completed."
            )

            return test_result

        except Exception as exc:

            logger.exception(
                "Automated testing failed."
            )

            return self._failed_test_result(
                str(exc)
            )

    # ==========================================================
    # REVIEW
    # ==========================================================

    async def _run_review(
        self,
        code: str,
    ) -> str:

        try:
            # ReviewerAgent.run() returns a string.
            # Use the shared MemoryManager so the reviewer can
            # use project/review context from the pipeline.
            review = await self.reviewer.run(
                code,
                memory=self.memory,
            )

            review = review or ""

            logger.info(
                "AI review completed."
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
        evaluation: dict[str, Any] = {}
        validation: dict[str, Any] = {}
        test_result: dict[str, Any] = {}
        review: str = ""
        debug_report: dict[str, Any] = {}
        retry_stats: dict[str, Any] = {}

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
            error = "Planner failed to generate a task."

            await self._fail_run(
                run_id,
                error,
            )

            raise RuntimeError(error)

        logger.info(
            f"Planning completed: {plan.title}"
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
            error = "Coder failed to generate source code."

            await self._fail_run(
                run_id,
                error,
            )

            raise RuntimeError(error)

        logger.info(
            f"Generated {len(code)} characters of source code."
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
            error = "Project Builder returned no result."

            await self._fail_run(
                run_id,
                error,
            )

            raise RuntimeError(error)

        if not project.get("project_path"):
            error = "Project Builder did not return project_path."

            await self._fail_run(
                run_id,
                error,
            )

            raise RuntimeError(error)

        if not project.get("zip_path"):
            error = "Project Builder did not return zip_path."

            await self._fail_run(
                run_id,
                error,
            )

            raise RuntimeError(error)

        logger.info(
            f"Project created at: "
            f"{project['project_path']}"
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

        except Exception:
            logger.exception(
                "Project execution failed."
            )

            execution_result = {
                "success": False,
                "stdout": "",
                "stderr": "Project execution failed.",
                "return_code": -1,
            }

            debug_report = {
                "success": False,
                "error": "Project execution failed.",
            }

            retry_result = None

        stage_times["execution"] = (
            time.monotonic() - stage_start
        )

        if retry_result is not None:

            if not isinstance(
                retry_result,
                tuple,
            ) or len(retry_result) != 5:

                raise RuntimeError(
                    "RetryManager returned an invalid result. "
                    "Expected: (execution_result, project, code, "
                    "debug_report, retry_stats)"
                )

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

        logger.info(
            "Execution stage completed."
        )

        await self._progress(
            session_id,
            "Execution",
            65,
            "Execution completed.",
            run_id,
        )

        # ======================================================
        # STEPS 5-7 - VALIDATION / TESTING / REVIEW
        # ======================================================
        #
        # These stages are independent:
        #
        # Validation → project path
        # Testing    → execution result + project path
        # Review     → generated code
        #
        # Therefore they can run concurrently.

        logger.info(
            "Steps 5-7/9 - Validating, testing, and reviewing "
            "(concurrently)..."
        )

        await self._progress(
            session_id,
            "Validation",
            70,
            "Validating, testing, and reviewing project...",
            run_id,
        )

        validation, test_result, review = await asyncio.gather(
            self._timed(
                self._run_validation(
                    project["project_path"]
                ),
                "validation",
                stage_times,
            ),
            self._timed(
                self._run_testing(
                    execution_result,
                    project["project_path"],
                ),
                "testing",
                stage_times,
            ),
            self._timed(
                self._run_review(
                    code
                ),
                "review",
                stage_times,
            ),
        )

        validation = validation or {}
        test_result = test_result or {}
        review = review or ""

        await self._progress(
            session_id,
            "Review",
            75,
            "Validation, testing, and review completed.",
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
            85,
            "Evaluating final project...",
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
                "recommendation": "Evaluation failed.",
                "error": str(exc),
            }

        stage_times["evaluation"] = (
            time.monotonic() - stage_start
        )

        logger.info(
            "Project evaluation completed."
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
            95,
            "Saving project information...",
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
        # COMPLETED
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
            f"AutoDev AI Pipeline Finished in "
            f"{pipeline_time:.2f}s"
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

        # ======================================================
        # FINAL RESULT
        # ======================================================

        final_result = {
            "success": bool(
                execution_result.get(
                    "success",
                    False,
                )
                and validation.get(
                    "valid",
                    False,
                )
                and test_result.get(
                    "success",
                    False,
                )
                and self._review_succeeded(
                    review
                )
            ),

            "plan": plan.model_dump(),

            "project": project,

            "execution": execution_result,

            "validation": validation,

            "tests": test_result,

            "debug_report": debug_report,

            "retry_stats": retry_stats,

            "review": review,

            "evaluation": evaluation,

            "improved_code": code,

            "metrics": {
                "pipeline_time": pipeline_time,
                "stage_times": stage_times,
                "retry_stats": retry_stats,
            },
        }

        # ------------------------------------------
        # Persist final run state
        # ------------------------------------------

        await self._update_run(
            run_id,
            status=(
                "completed"
                if final_result["success"]
                else "failed"
            ),
            current_step="Completed",
            progress=100,
            message=(
                "Project generation completed successfully."
                if final_result["success"]
                else "Project generation completed with failures."
            ),
            result=final_result,
            completed=True,
        )

        return final_result