import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.database.crud import (
    get_run,
    get_runs_by_session,
)
from app.database.database import get_db


router = APIRouter(
    prefix="/runs",
    tags=["Runs"],
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