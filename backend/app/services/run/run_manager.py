from typing import Any

from app.database.crud import update_run
from app.database.database import SessionLocal


class RunManager:
    @staticmethod
    def update(
        run_id: str,
        *,
        user_id: int | None = None,
        status: str | None = None,
        current_step: str | None = None,
        progress: int | None = None,
        message: str | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        started: bool = False,
        completed: bool = False,
    ) -> None:
        db = SessionLocal()

        try:
            update_run(
                db,
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
        finally:
            db.close()