import uuid
import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.database.crud import (
    create_run,
    get_run,
    get_runs_by_session,
)
from app.database.database import SessionLocal, get_db
from app.memory.conversation_cache import (
    add_message,
    get_history,
)
from app.services.llm.router import LLMRouter
from app.services.run.job_manager import RunJobManager


router = APIRouter(
    prefix="/runs",
    tags=["Runs"],
)


# --------------------------------------------------
# Request Models
# --------------------------------------------------


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


# --------------------------------------------------
# Serialization
# --------------------------------------------------


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


# --------------------------------------------------
# Create Background Run
# --------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_background_run(
    request: CreateRunRequest,
):

    run_id = str(uuid.uuid4())

    history = get_history(
        request.session_id
    )

    add_message(
        request.session_id,
        "user",
        request.message,
    )

    db = SessionLocal()

    try:
        create_run(
            db=db,
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
            status_code=500,
            detail="Unable to create run.",
        )

    finally:
        db.close()

    try:
        RunJobManager.start(
            run_id=run_id,
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
            from app.database.crud import update_run

            update_run(
                db,
                run_id,
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
            status_code=500,
            detail="Unable to schedule run.",
        )

    logger.info(
        "Created background AutoDev-AI run: %s",
        run_id,
    )

    return {
        "success": True,
        "run_id": run_id,
        "session_id": request.session_id,
        "status": "queued",
        "message": "Run queued successfully.",
    }


# --------------------------------------------------
# Get Runs By Session
# --------------------------------------------------


@router.get("/session/{session_id}")
def session_runs(
    session_id: str,
    db: Session = Depends(get_db),
):
    try:
        runs = get_runs_by_session(
            db,
            session_id,
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
            "Failed to retrieve session runs."
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve runs.",
        )


# --------------------------------------------------
# Get Single Run
# --------------------------------------------------


@router.get("/{run_id}")
def run_details(
    run_id: str,
    db: Session = Depends(get_db),
):
    try:
        run = get_run(
            db,
            run_id,
        )

        if run is None:
            raise HTTPException(
                status_code=404,
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
            status_code=500,
            detail="Unable to retrieve run.",
        )
