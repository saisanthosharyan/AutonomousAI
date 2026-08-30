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
        Execution / Retry Manager (repairs internally via FixerAgent)
            ↓
        Validation / Testing / Review   (run concurrently)
            ↓
        Database Save
            ↓
        Final Result

    NOTE: FixManager (app/services/fixer/fix_manager.py) is
    intentionally NOT used here. RetryManager already performs the
    full self-healing loop (execute -> debug -> FixerAgent ->
    ProjectBuilder.rebuild() -> re-execute). Running FixManager on
    top of that would be a second, overlapping repair engine, and
    its repair_project() return shape (a dict) doesn't match what
    this orchestrator expects from a repair step, so wiring it in
    here would silently no-op at best. If you want to replace
    RetryManager's repair loop with FixManager's patch-based one
    later, do it as a single swap, not an addition.
    """

    TOTAL_STEPS = 9

    def __init__(self) -> None:
        # One shared MemoryManager, created here and passed down to
        # every agent that reads/writes memory. If each agent
        # creates its own MemoryManager() instance instead, memory
        # never persists across the pipeline.
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
    ) -> None:
        """
        Send websocket progress safely.

        Failure to update the UI should never crash the
        AutoDev AI pipeline.
        """

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
    ) -> dict[str, Any]:
        return {
            "success": False,
            "error": error,
        }

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
        Await `coro`, recording its wall-clock duration under
        stage_times[label]. Safe to run several of these concurrently
        via asyncio.gather since each writes a distinct dict key and
        the event loop is single-threaded.
        """

        start = time.monotonic()

        result = await coro

        stage_times[label] = time.monotonic() - start

        return result

    # ==========================================================
    # CONCURRENT STAGE WORKERS (validation / testing / review)
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

    async def _run_review(
        self,
        code: str,
    ) -> dict[str, Any]:

        try:
            # ReviewerAgent.run() accepts (code, memory=...).
            # Passing the orchestrator's shared MemoryManager here
            # is what makes reviews persist and build on prior
            # runs instead of starting from a blank memory store.
            review = await self.reviewer.run(
                code,
                memory=self.memory,
            )

            review = review or {}

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
    ) -> dict[str, Any]:

        logger.info("=" * 60)
        logger.info("Starting AutoDev AI Pipeline")
        logger.info("=" * 60)

        if not task or not task.strip():
            raise ValueError(
                "Task cannot be empty."
            )

        pipeline_start = time.monotonic()
        stage_times: dict[str, float] = {}

        plan: Task | None = None
        code: str = ""
        project: dict[str, Any] = {}

        execution_result: dict[str, Any] = {}
        evaluation: dict[str, Any] = {}
        validation: dict[str, Any] = {}
        test_result: dict[str, Any] = {}
        review: dict[str, Any] = {}
        debug_report: dict[str, Any] = {}

        # retry_stats must exist even if RetryManager raises before
        # returning, otherwise the final "return" below would hit a
        # NameError instead of just reporting an empty stats dict.
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
        )

        _stage_start = time.monotonic()

        try:
            plan = await self.planner.run(
                task,
                history,
            )

        except Exception:
            logger.exception(
                "Planner Agent failed."
            )
            raise

        stage_times["planner"] = time.monotonic() - _stage_start

        if plan is None:
            raise RuntimeError(
                "Planner failed to generate a task."
            )

        logger.info(
            f"Planning completed: {plan.title}"
        )

        await self._progress(
            session_id,
            "Planning",
            20,
            "Planning completed.",
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
        )

        _stage_start = time.monotonic()

        try:
            code = await self.coder.run(
                plan,
                memory=self.memory,
            )

        except Exception:
            logger.exception(
                "Coder Agent failed."
            )
            raise

        stage_times["coder"] = time.monotonic() - _stage_start

        if not code or not code.strip():
            raise RuntimeError(
                "Coder failed to generate source code."
            )

        logger.info(
            f"Generated {len(code)} characters of source code."
        )

        await self._progress(
            session_id,
            "Coding",
            35,
            "Source code generated.",
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
        )

        _stage_start = time.monotonic()

        try:
            project = self.builder.build(
                project_name=plan.title,
                llm_output=code,
            )

        except Exception:
            logger.exception(
                "Project Builder failed."
            )
            raise

        stage_times["builder"] = time.monotonic() - _stage_start

        if not project:
            raise RuntimeError(
                "Project Builder returned no result."
            )

        if not project.get("project_path"):
            raise RuntimeError(
                "Project Builder did not return project_path."
            )

        if not project.get("zip_path"):
            raise RuntimeError(
                "Project Builder did not return zip_path."
            )

        logger.info(
            f"Project created at: "
            f"{project['project_path']}"
        )

        await self._progress(
            session_id,
            "Building",
            50,
            "Project built successfully.",
        )

        # ======================================================
        # STEP 4 - EXECUTION (+ REPAIR VIA RETRY MANAGER)
        # ======================================================

        logger.info(
            "Step 4/9 - Executing project..."
        )

        await self._progress(
            session_id,
            "Execution",
            55,
            "Executing generated project...",
        )

        _stage_start = time.monotonic()

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

        stage_times["execution"] = time.monotonic() - _stage_start

        if retry_result is not None:

            # RetryManager.execute_with_retry() now returns a 5-tuple:
            # (execution_result, project, code, debug_report, retry_stats)
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
                execution_result
                or {}
            )

            debug_report = (
                debug_report
                or {}
            )

            retry_stats = (
                retry_stats
                or {}
            )

        logger.info(
            "Execution stage completed."
        )

        await self._progress(
            session_id,
            "Execution",
            65,
            "Execution completed.",
        )

        # ======================================================
        # STEPS 5-7 - VALIDATION / TESTING / REVIEW (concurrent)
        # ======================================================
        #
        # None of these three depend on each other's output: validation
        # only needs project_path, testing only needs execution_result,
        # and review only needs the generated code. Running them with
        # asyncio.gather instead of sequentially removes dead time
        # where the pipeline is waiting on one blocking I/O-bound call
        # (e.g. the reviewer's LLM round-trip) while the others sit
        # idle. Each worker keeps its own try/except so one stage
        # failing doesn't cancel the others.

        logger.info(
            "Steps 5-7/9 - Validating, testing, and reviewing "
            "(concurrently)..."
        )

        await self._progress(
            session_id,
            "Validation",
            70,
            "Validating, testing, and reviewing project...",
        )

        validation, test_result, review = await asyncio.gather(
            self._timed(
                self._run_validation(project["project_path"]),
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
                self._run_review(code),
                "review",
                stage_times,
            ),
        )

        validation = validation or {}
        test_result = test_result or {}
        review = review or {}

        await self._progress(
            session_id,
            "Review",
            95,
            "Validation, testing, and review completed.",
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
            90,
            "Evaluating final project...",
        )

        _stage_start = time.monotonic()

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
            time.monotonic() - _stage_start
        )

        logger.info(
            "Project evaluation completed."
        )

        # ======================================================
        # STEP 8 - SAVE PROJECT
        # ======================================================

        logger.info(
            "Step 9/9 - Saving project..."
        )

        await self._progress(
            session_id,
            "Saving",
            95,
            "Saving project information...",
        )

        _stage_start = time.monotonic()

        db = SessionLocal()

        try:

            # NOTE: review / validation / retry_stats / execution are
            # not persisted here yet -- create_project()'s current
            # signature only accepts the fields below. Storing the
            # rest requires extending the project DB schema/CRUD layer
            # first (new columns or a JSON blob column), which is out
            # of scope for this file. Once that's done, pass them
            # through here the same way project_path/zip_path are.
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

            # Database failure should not destroy
            # the generated project.
            logger.exception(
                "Failed to save project to database."
            )

        finally:

            db.close()

        stage_times["save"] = time.monotonic() - _stage_start

        # ======================================================
        # COMPLETED
        # ======================================================

        await self._progress(
            session_id,
            "Completed",
            100,
            "Project generation completed.",
        )

        pipeline_time = time.monotonic() - pipeline_start

        logger.info("=" * 60)
        logger.info(
            f"AutoDev AI Pipeline Finished in {pipeline_time:.2f}s"
        )
        logger.info("=" * 60)

        # ------------------------------------------------------
        # Normalize results
        # ------------------------------------------------------

        execution_result = (
            execution_result
            or {}
        )

        validation = (
            validation
            or {}
        )

        test_result = (
            test_result
            or {}
        )

        review = (
            review
            or {}
        )

        debug_report = (
            debug_report
            or {}
        )
        evaluation = (
            evaluation
            or {}
        )

        retry_stats = (
            retry_stats
            or {}
        )

        # ------------------------------------------------------
        # Final result
        # ------------------------------------------------------

        return {
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
                and review.get(
                    "success",
                    True,
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