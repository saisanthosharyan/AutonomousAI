from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.database.crud import (
    delete_project,
    get_project,
    get_projects,
    get_projects_by_session,
)
from app.database.database import get_db
from app.database.models import User
from app.services.auth.dependencies import get_current_user


router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)


@router.get("/")
def list_projects(
    session_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        if session_id:
            logger.info(
                "Fetching projects for user %s and session: %s",
                current_user.id,
                session_id,
            )

            projects = get_projects_by_session(
                db,
                session_id,
                current_user.id,
            )

        else:
            logger.info(
                "Fetching all projects for user: %s",
                current_user.id,
            )

            projects = get_projects(
                db,
                current_user.id,
            )

        return {
            "success": True,
            "count": len(projects),
            "projects": projects,
        }

    except Exception:
        logger.exception(
            "Failed to fetch projects."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve projects.",
        )


@router.get("/{project_id}")
def project_details(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        project = get_project(
            db,
            project_id,
            current_user.id,
        )

        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )

        return {
            "success": True,
            "project": project,
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Failed to retrieve project."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve project.",
        )


@router.delete("/{project_id}")
def remove_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        project = delete_project(
            db,
            project_id,
            current_user.id,
        )

        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )

        logger.info(
            "Project %s deleted successfully by user %s",
            project_id,
            current_user.id,
        )

        return {
            "success": True,
            "message": "Project deleted successfully.",
            "project_id": project_id,
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Failed to delete project: %s",
            project_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to delete project.",
        )