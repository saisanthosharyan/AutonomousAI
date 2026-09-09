import asyncio

from app.agents.orchestrator import AgentOrchestrator
from app.core.logger import logger
from app.database.crud import update_run
from app.database.database import SessionLocal
from app.memory.conversation_cache import add_message
from app.services.llm.router import LLMRouter


class RunJobManager:
    """
    Manages background AutoDev-AI run execution.

    The in-memory task registry tracks currently running asyncio
    tasks, while SQLite remains the source of truth for persistent
    run state.
    """

    _tasks: dict[str, asyncio.Task] = {}

    @classmethod
    def start(
        cls,
        *,
        run_id: str,
        session_id: str,
        prompt: str,
        history: list,
        provider: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> asyncio.Task:

        task = asyncio.create_task(
            cls._execute(
                run_id=run_id,
                session_id=session_id,
                prompt=prompt,
                history=history,
                provider=provider,
                api_key=api_key,
                model=model,
            )
        )

        cls._tasks[run_id] = task

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
    def _task_done(
        cls,
        run_id: str,
        task: asyncio.Task,
    ) -> None:

        cls._tasks.pop(run_id, None)

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

    @classmethod
    async def _execute(
        cls,
        *,
        run_id: str,
        session_id: str,
        prompt: str,
        history: list,
        provider: str | None,
        api_key: str | None,
        model: str | None,
    ) -> None:

        try:
            llm = LLMRouter.get_llm(
                provider=provider,
                api_key=api_key,
                model=model,
            )

            orchestrator = AgentOrchestrator(
                llm=llm,
            )

            result = await orchestrator.execute(
                task=prompt,
                history=history,
                session_id=session_id,
                run_id=run_id,
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
        return len(cls._tasks)

    @classmethod
    def is_running(
        cls,
        run_id: str,
    ) -> bool:

        task = cls._tasks.get(run_id)

        if task is None:
            return False

        return not task.done()
