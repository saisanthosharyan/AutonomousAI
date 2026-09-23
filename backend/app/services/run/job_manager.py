import asyncio

from app.agents.orchestrator import AgentOrchestrator
from app.core.config import settings
from app.core.logger import logger
from app.database.crud import get_run, update_run
from app.database.database import SessionLocal
from app.memory.conversation_cache import add_message
from app.services.llm.router import LLMRouter


class RunJobManager:
    """
    Manages background AutoDev-AI run execution.

    The in-memory task registry tracks currently running asyncio
    tasks, while SQLite remains the source of truth for persistent
    run state.

    A semaphore limits the number of runs that can execute the
    actual AI workflow concurrently.
    """

    _tasks: dict[str, asyncio.Task] = {}
    _semaphore: asyncio.Semaphore | None = None

    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        """
        Return the shared concurrency semaphore.
        """

        if cls._semaphore is None:
            cls._semaphore = asyncio.Semaphore(
                settings.MAX_CONCURRENT_RUNS
            )

        return cls._semaphore

    @classmethod
    def start(
        cls,
        *,
        run_id: str,
        user_id: int | None = None,
        session_id: str,
        prompt: str,
        history: list,
        provider: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> asyncio.Task:
        """
        Schedule a background AutoDev-AI run.
        """

        logger.info(
            "DEBUG: RunJobManager.start() ENTERED: %s",
            run_id,
        )

        existing_task = cls._tasks.get(run_id)

        if existing_task is not None and not existing_task.done():
            logger.warning(
                "Run %s is already active.",
                run_id,
            )
            raise RuntimeError(
                f"Run {run_id} is already active."
            )

        task = asyncio.create_task(
            cls._execute(
                run_id=run_id,
                user_id=user_id,
                session_id=session_id,
                prompt=prompt,
                history=history,
                provider=provider,
                api_key=api_key,
                model=model,
            )
        )

        cls._tasks[run_id] = task

        logger.info(
            "DEBUG: Background asyncio task CREATED: %s | done=%s",
            run_id,
            task.done(),
        )

        task.add_done_callback(
            lambda completed_task: cls._task_done(
                run_id,
                completed_task,
            )
        )

        logger.info(
            "Background run job scheduled: %s",
            run_id,
        )

        return task

    @classmethod
    def cancel(
        cls,
        run_id: str,
        user_id: int | None = None,
    ) -> bool:
        """
        Cancel an active background run.
        """

        task = cls._tasks.get(run_id)

        if task is None or task.done():
            logger.info(
                "No active background task found to cancel: %s",
                run_id,
            )
            return False

        cancelled = task.cancel()

        if not cancelled:
            logger.warning(
                "Failed to cancel background task: %s",
                run_id,
            )
            return False

        db = SessionLocal()

        try:
            run = get_run(
                db,
                run_id,
                user_id,
            )

            if run is None:
                logger.warning(
                    "Run not found while cancelling: %s",
                    run_id,
                )
                return True

            update_run(
                db,
                run_id,
                user_id=user_id,
                status="cancelled",
                current_step="Cancelled",
                progress=100,
                message="Run cancelled by user.",
                error=None,
                completed=True,
            )

            logger.info(
                "Background run cancelled: %s",
                run_id,
            )

        except Exception:
            logger.exception(
                "Failed to persist cancellation for run: %s",
                run_id,
            )

        finally:
            db.close()

        return True

    @classmethod
    def _task_done(
        cls,
        run_id: str,
        task: asyncio.Task,
    ) -> None:
        """
        Remove a completed task from the registry and consume
        its exception.
        """

        cls._tasks.pop(run_id, None)

        logger.info(
            "DEBUG: Background task finished: %s | done=%s | cancelled=%s",
            run_id,
            task.done(),
            task.cancelled(),
        )

        try:
            task.result()

        except asyncio.CancelledError:
            logger.warning(
                "Background run job cancelled: %s",
                run_id,
            )

        except Exception:
            logger.exception(
                "Background run job failed unexpectedly: %s",
                run_id,
            )

        else:
            logger.info(
                "DEBUG: Background task completed without exception: %s",
                run_id,
            )

    @classmethod
    async def _execute(
        cls,
        *,
        run_id: str,
        user_id: int | None,
        session_id: str,
        prompt: str,
        history: list,
        provider: str | None,
        api_key: str | None,
        model: str | None,
    ) -> None:
        """
        Execute the actual AutoDev-AI workflow.
        """

        logger.info(
            "DEBUG: _execute() ENTERED: %s",
            run_id,
        )

        semaphore = cls._get_semaphore()

        try:
            logger.info(
                "Run waiting for execution slot: %s",
                run_id,
            )

            async with semaphore:
                logger.info(
                    "Run acquired execution slot: %s",
                    run_id,
                )

                logger.info(
                    "DEBUG: Creating LLM for run: %s | provider=%s | model=%s",
                    run_id,
                    provider,
                    model,
                )

                llm = LLMRouter.get_llm(
                    provider=provider,
                    api_key=api_key,
                    model=model,
                )

                logger.info(
                    "DEBUG: LLM created successfully: %s",
                    run_id,
                )

                orchestrator = AgentOrchestrator(
                    llm=llm,
                )

                logger.info(
                    "DEBUG: AgentOrchestrator created: %s",
                    run_id,
                )

                logger.info(
                    "DEBUG: Starting orchestrator.execute(): %s",
                    run_id,
                )

                result = await orchestrator.execute(
                    task=prompt,
                    history=history,
                    session_id=session_id,
                    run_id=run_id,
                    user_id=user_id,
                )

                logger.info(
                    "DEBUG: orchestrator.execute() returned: %s",
                    run_id,
                )

                add_message(
                    session_id,
                    "assistant",
                    result.get("review", ""),
                )

                logger.info(
                    "Background run job completed: %s",
                    run_id,
                )

        except asyncio.CancelledError:
            logger.warning(
                "Background run job cancelled: %s",
                run_id,
            )
            raise

        except Exception as exc:
            logger.exception(
                "Background run job failed: %s",
                run_id,
            )

            db = SessionLocal()

            try:
                update_run(
                    db,
                    run_id,
                    user_id=user_id,
                    status="failed",
                    current_step="Failed",
                    progress=100,
                    message="AutoDev-AI background job failed.",
                    error=str(exc),
                    completed=True,
                )

            except Exception:
                logger.exception(
                    "Failed to persist background job failure: %s",
                    run_id,
                )

            finally:
                db.close()

    @classmethod
    def active_count(cls) -> int:
        """
        Return the number of currently active background tasks.
        """

        return sum(
            1
            for task in cls._tasks.values()
            if not task.done()
        )

    @classmethod
    def max_concurrent_runs(cls) -> int:
        """
        Return the configured maximum number of simultaneously
        executing runs.
        """

        return settings.MAX_CONCURRENT_RUNS

    @classmethod
    def is_running(
        cls,
        run_id: str,
    ) -> bool:
        """
        Return True when a run has an active asyncio task.
        """

        task = cls._tasks.get(run_id)

        if task is None:
            return False

        return not task.done()
