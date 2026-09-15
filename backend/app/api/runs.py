import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.database.crud import (
    create_run,
    get_run,
    get_runs,
    get_runs_by_session,
    update_run,
)
from app.database.database import SessionLocal, get_db
from app.database.models import User
from app.memory.conversation_cache import (
    add_message,
    get_history,
)
from app.services.auth.dependencies import get_current_user
from app.services.run.job_manager import RunJobManager


router = APIRouter(
    prefix="/runs",
    tags=["Runs"],
)


class CreateRunRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    provider: str | None = None
    api_key: str | None = Field(
        default=None,
        min_length=1,
    )
    model: str | None = Field(
        default=None,
        min_length=1,
    )


def serialize_run(run):
    return {
        "run_id": run.id,
        "session_id": run.session_id,
        "prompt": run.prompt,
        "status": run.status,
        "current_step": run.current_step,
        "progress": run.progress,
        "message": run.message,
        "result": (
            json.loads(run.result)
            if run.result
            else None
        ),
        "error": run.error,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "updated_at": run.updated_at,
    }


def get_active_run_for_session(
    db: Session,
    session_id: str,
    user_id: int,
):
    runs = get_runs_by_session(
        db,
        session_id,
        user_id,
    )

    active_statuses = {
        "queued",
        "running",
    }

    for run in runs:
        if run.status in active_statuses:
            return run

    return None


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_background_run(
    request: CreateRunRequest,
    current_user: User = Depends(get_current_user),
):
    db = SessionLocal()

    try:
        active_run = get_active_run_for_session(
            db,
            request.session_id,
            current_user.id,
        )

        if active_run is not None:
            logger.warning(
                "Rejected duplicate active run for user %s "
                "and session %s. Existing run: %s",
                current_user.id,
                request.session_id,
                active_run.id,
            )

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "An active run already exists for this session."
                ),
            )

        run_id = str(uuid.uuid4())

        history = get_history(
            request.session_id,
        )

        add_message(
            request.session_id,
            "user",
            request.message,
        )

        try:
            create_run(
                db=db,
                user_id=current_user.id,
                run_id=run_id,
                session_id=request.session_id,
                prompt=request.message,
            )

        except Exception:
            db.rollback()

            logger.exception(
                "Failed to create run: %s",
                run_id,
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to create run.",
            )

    finally:
        db.close()

    try:
        RunJobManager.start(
            run_id=run_id,
            user_id=current_user.id,
            session_id=request.session_id,
            prompt=request.message,
            history=history,
            provider=request.provider,
            api_key=request.api_key,
            model=request.model,
        )

    except Exception as exc:
        logger.exception(
            "Failed to schedule run: %s",
            run_id,
        )

        db = SessionLocal()

        try:
            update_run(
                db,
                run_id,
                user_id=current_user.id,
                status="failed",
                current_step="Failed",
                progress=100,
                message="Failed to schedule run.",
                error=str(exc),
                completed=True,
            )

        finally:
            db.close()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to schedule run.",
        )

    logger.info(
        "Created background AutoDev-AI run %s for user %s",
        run_id,
        current_user.id,
    )

    return {
        "success": True,
        "run_id": run_id,
        "session_id": request.session_id,
        "status": "queued",
        "message": "Run queued successfully.",
    }


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
):
    db = SessionLocal()

    try:
        run = get_run(
            db,
            run_id,
            current_user.id,
        )

        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found.",
            )

        if run.status in {
            "completed",
            "failed",
            "cancelled",
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Run cannot be cancelled because "
                    f"it is already {run.status}."
                ),
            )

        cancelled = RunJobManager.cancel(
            run_id,
            current_user.id,
        )

        if not cancelled:
            current_run = get_run(
                db,
                run_id,
                current_user.id,
            )

            if (
                current_run is not None
                and current_run.status
                in {
                    "completed",
                    "failed",
                    "cancelled",
                }
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Run finished before cancellation "
                        "could be applied."
                    ),
                )

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Run is not currently active.",
            )

        return {
            "success": True,
            "run_id": run_id,
            "status": "cancelled",
            "message": "Run cancelled successfully.",
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Failed to cancel run: %s",
            run_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to cancel run.",
        )

    finally:
        db.close()


@router.get("/")
def list_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        runs = get_runs(
            db,
            current_user.id,
        )

        return {
            "success": True,
            "count": len(runs),
            "runs": [
                serialize_run(run)
                for run in runs
            ],
        }

    except Exception:
        logger.exception(
            "Failed to fetch runs for user %s.",
            current_user.id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve runs.",
        )


@router.get("/session/{session_id}")
def session_runs(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        runs = get_runs_by_session(
            db,
            session_id,
            current_user.id,
        )

        return {
            "success": True,
            "count": len(runs),
            "runs": [
                serialize_run(run)
                for run in runs
            ],
        }

    except Exception:
        logger.exception(
            "Failed to retrieve runs for user %s.",
            current_user.id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve runs.",
        )


@router.get("/{run_id}")
def run_details(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        run = get_run(
            db,
            run_id,
            current_user.id,
        )

        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found.",
            )

        return {
            "success": True,
            "run": serialize_run(run),
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Failed to retrieve run."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve run.",
        )
