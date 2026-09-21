from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

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
        AI Review
            ↓
        Review Self-Healing
            ↓
        Rebuild
            ↓
        AI Review Again
            ↓
        Final Validation
            ↓
        Evaluation
            ↓
        Database Save
            ↓
        Final Result
    """

    TOTAL_STEPS = 9

    def __init__(self, llm=None) -> None:
        self.memory = MemoryManager()
        self.llm = llm

        self.planner = PlannerAgent(
            llm=llm
        )

        self.coder = CoderAgent(
            llm=llm
        )

        self.reviewer = ReviewerAgent(
            llm=llm
        )

        self.builder = ProjectBuilder()
        self.validator = ProjectValidator()

        self.retry_manager = RetryManager(
            memory=self.memory,
            llm=llm,
        )

        self.evaluator = Evaluator()

    async def _progress(
        self,
        session_id: str | None,
        step: str,
        progress: int,
        message: str,
        run_id: str | None = None,
        user_id: int | None = None,
    ) -> None:
        if run_id:
            try:
                await asyncio.to_thread(
                    RunManager.update,
                    run_id,
                    user_id=user_id,
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

    async def _update_run(
        self,
        run_id: str | None,
        user_id: int | None = None,
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
        if not run_id:
            return

        try:
            await asyncio.to_thread(
                RunManager.update,
                run_id,
                user_id=user_id,
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
        user_id: int | None,
        error: str,
    ) -> None:
        await self._update_run(
            run_id,
            user_id,
            status="failed",
            current_step="Failed",
            progress=100,
            message="AutoDev-AI pipeline failed.",
            error=error,
            completed=True,
        )

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
        error = str(error).strip()

        if error.startswith("Reviewer Agent failed:"):
            return error

        return f"Reviewer Agent failed: {error}"

    @staticmethod
    def _review_succeeded(
        review: str,
    ) -> bool:
        if not isinstance(review, str):
            return False

        review = review.strip()

        if not review:
            return False

        if review.startswith(
            "Reviewer Agent failed:"
        ):
            return False

        required_sections = (
            "Overall Summary",
            "Strengths",
            "Problems Found",
            "Final Score",
        )

        return all(
            section.lower() in review.lower()
            for section in required_sections
        )

    @staticmethod
    def _failed_validation(
        error: str,
    ) -> dict[str, Any]:
        return {
            "valid": False,
            "errors": [error],
            "warnings": [],
        }

    async def _run_validation(
        self,
        project_path: str,
        task: Optional[Task] = None,
    ) -> dict[str, Any]:
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
                self.validator.validate,
                project_path,
                generation_mode,
                requested_files,
            )

            validation = validation or {}

            logger.info(
                "Final project validation completed."
            )

            logger.info(
                "Validation generation mode: %s",
                generation_mode,
            )

            logger.info(
                "Validation requested files: %s",
                requested_files or [],
            )

            return validation

        except Exception as exc:
            logger.exception(
                "Project validation failed."
            )

            return self._failed_validation(
                str(exc)
            )

    async def _run_review(
        self,
        code: str,
        project_path: str,
        original_request: str | Task,
    ) -> str:
        try:
            if isinstance(
                original_request,
                Task,
            ):
                request_parts = [
                    original_request.description,
                ]

                if original_request.features:
                    request_parts.append(
                        "Required features: "
                        + ", ".join(
                            original_request.features
                        )
                    )

                if original_request.requested_files:
                    request_parts.append(
                        "Required files: "
                        + ", ".join(
                            original_request.requested_files
                        )
                    )

                original_request = "\n".join(
                    part
                    for part in request_parts
                    if part
                )

            if not isinstance(
                original_request,
                str,
            ):
                raise TypeError(
                    "Reviewer original_request must be a string."
                )

            original_request = (
                original_request.strip()
            )

            if not original_request:
                raise ValueError(
                    "Reviewer original_request cannot be empty."
                )

            review = await self.reviewer.run(
                code,
                project_directory=project_path,
                original_request=original_request,
                memory=self.memory,
            )

            review = review or ""

            if not review.strip():
                raise RuntimeError(
                    "Reviewer Agent returned an empty review."
                )

            logger.info(
                "AI review completed."
            )

            return review

        except Exception as exc:
            logger.exception(
                "Reviewer Agent failed."
            )

            raise RuntimeError(
                f"Reviewer Agent failed: {exc}"
            ) from exc

    async def execute(
        self,
        task: str,
        history: list | None = None,
        session_id: str | None = None,
        run_id: str | None = None,
        user_id: int | None = None,
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
            user_id,
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
        review_retry_stats: dict[str, Any] = {}
        review_debug_report: dict[str, Any] = {}

        logger.info(
            "Step 1/9 - Planning..."
        )

        await self._progress(
            session_id,
            "Planning",
            10,
            "Generating implementation plan...",
            run_id,
            user_id,
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
                user_id,
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
                user_id,
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
            user_id,
        )

        logger.info(
            "Step 2/9 - Generating code..."
        )

        await self._progress(
            session_id,
            "Coding",
            25,
            "Generating source code...",
            run_id,
            user_id,
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
                user_id,
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
                user_id,
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
            user_id,
        )

        logger.info(
            "Step 3/9 - Building project..."
        )

        await self._progress(
            session_id,
            "Building",
            40,
            "Creating project structure...",
            run_id,
            user_id,
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
                user_id,
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
                user_id,
                error,
            )

            raise RuntimeError(error)

        if not project.get("project_path"):
            error = (
                "Project Builder did not return project_path."
            )

            await self._fail_run(
                run_id,
                user_id,
                error,
            )

            raise RuntimeError(error)

        if not project.get("zip_path"):
            error = (
                "Project Builder did not return zip_path."
            )

            await self._fail_run(
                run_id,
                user_id,
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
            user_id,
        )

        logger.info(
            "Step 4/9 - Executing project..."
        )

        await self._progress(
            session_id,
            "Execution",
            55,
            "Executing generated project...",
            run_id,
            user_id,
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
                    "RetryManager returned an invalid execution result."
                )

                await self._fail_run(
                    run_id,
                    user_id,
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
                "Execution succeeded. Starting automated test verification."
                if execution_result.get("success")
                else
                "Execution failed. Automated tests cannot verify the project."
            ),
            run_id,
            user_id,
        )

        logger.info(
            "Step 5/9 - Testing + test self-healing..."
        )

        await self._progress(
            session_id,
            "Testing",
            70,
            "Running automated tests and self-healing failures...",
            run_id,
            user_id,
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
                "Execution did not succeed. Skipping test execution."
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
                    "reason": "Execution failed.",
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
            user_id,
        )

        logger.info(
            "Step 6/9 - AI review + review self-healing..."
        )

        await self._progress(
            session_id,
            "Review",
            80,
            "Reviewing final source and repairing review findings...",
            run_id,
            user_id,
        )

        stage_start = time.monotonic()

        try:
            initial_review = await self._run_review(
                code,
                project["project_path"],
                plan,
            )

            if not self._review_succeeded(
                initial_review
            ):
                logger.warning(
                    "Initial AI review did not contain all required review sections."
                )

            review_result = (
                await self.retry_manager.review_with_retry(
                    project=project,
                    code=code,
                    review=initial_review,
                    reviewer=self._run_review,
                    validator=self.validator,
                    task=plan,
                    max_review_retries=2,
                )
            )

            if not isinstance(
                review_result,
                dict,
            ):
                raise RuntimeError(
                    "RetryManager returned an invalid review result."
                )

            project = review_result.get(
                "project",
                project,
            )

            code = review_result.get(
                "code",
                code,
            )

            review = review_result.get(
                "review",
                "",
            )

            review_debug_report = (
                review_result.get(
                    "repair_history",
                    [],
                )
            )

            review_retry_stats = (
                review_result.get(
                    "review_stats",
                    {},
                )
            )

            review = (
                review or ""
            )

            review_debug_report = (
                review_debug_report or []
            )

            review_retry_stats = (
                review_retry_stats or {}
            )

            if not review_retry_stats.get(
                "successful",
                False,
            ):
                error = review_result.get(
                    "error",
                    "Review self-healing failed.",
                )

                raise RuntimeError(
                    str(error)
                )

            if not self._review_succeeded(
                review
            ):
                raise RuntimeError(
                    "Reviewer Agent returned an incomplete review."
                )

        except Exception as exc:
            logger.exception(
                "Review self-healing pipeline failed."
            )

            review = self._failed_review(
                str(exc)
            )

            review_debug_report = {
                "success": False,
                "error": str(exc),
            }

            review_retry_stats = {
                "attempts": 0,
                "repairs": 0,
                "review_failures": 1,
                "repeated_errors_detected": 0,
                "successful": False,
            }

        stage_times["review"] = (
            time.monotonic() - stage_start
        )

        debug_report = {
            "execution": debug_report.get(
                "execution",
                {},
            ),
            "testing": debug_report.get(
                "testing",
                {},
            ),
            "review": review_debug_report,
        }

        logger.info(
            "Review self-healing stage completed."
        )

        await self._progress(
            session_id,
            "Review",
            88,
            (
                "Review completed with all detected issues repaired."
                if review_retry_stats.get(
                    "successful"
                )
                else
                "Review completed with unresolved findings."
            ),
            run_id,
            user_id,
        )

        logger.info(
            "Step 7/9 - Final project validation..."
        )

        await self._progress(
            session_id,
            "Validation",
            90,
            "Validating the final reviewed and repaired project...",
            run_id,
            user_id,
        )

        stage_start = time.monotonic()

        validation = await self._run_validation(
            project["project_path"],
            plan,
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
            92,
            (
                "Final project validation passed."
                if validation.get("valid")
                else
                "Final project validation reported issues."
            ),
            run_id,
            user_id,
        )

        logger.info(
            "Step 8/9 - Evaluating final project..."
        )

        await self._progress(
            session_id,
            "Evaluation",
            94,
            "Evaluating final repaired project state...",
            run_id,
            user_id,
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

        evaluation = (
            evaluation or {}
        )

        logger.info(
            "Final project evaluation completed."
        )

        await self._progress(
            session_id,
            "Evaluation",
            96,
            "Final evaluation completed.",
            run_id,
            user_id,
        )

        logger.info(
            "Step 9/9 - Saving project..."
        )

        await self._progress(
            session_id,
            "Saving",
            97,
            "Saving final project information...",
            run_id,
            user_id,
        )

        stage_start = time.monotonic()

        db = SessionLocal()

        try:
            create_project(
                db=db,
                user_id=user_id,
                session_id=session_id or "default",
                title=plan.title,
                prompt=task,
                project_path=project["project_path"],
                zip_path=project["zip_path"],
            )

            logger.info(
                "Project saved successfully."
            )

        except Exception:
            logger.exception(
                "Failed to save project to database."
            )

        finally:
            db.close()

        stage_times["save"] = (
            time.monotonic() - stage_start
        )

        await self._progress(
            session_id,
            "Completed",
            99,
            "Finalizing project result...",
            run_id,
            user_id,
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

        review_retry_stats = (
            review_retry_stats or {}
        )

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
            and review_retry_stats.get(
                "successful",
                False,
            )
        )

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
            "review_retry_stats": review_retry_stats,
            "review": review,
            "evaluation": evaluation,
            "improved_code": code,
            "metrics": {
                "pipeline_time": pipeline_time,
                "stage_times": stage_times,
                "retry_stats": retry_stats,
                "test_retry_stats": test_retry_stats,
                "review_retry_stats": review_retry_stats,
            },
        }

        await self._update_run(
            run_id,
            user_id,
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
