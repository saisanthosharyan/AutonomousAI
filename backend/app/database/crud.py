from sqlalchemy.orm import Session

import json
from datetime import datetime, UTC
from .models import Project, Run

# --------------------------------------------------
# Create
# --------------------------------------------------


def create_project(
    db: Session,
    session_id: str,
    title: str,
    prompt: str,
    project_path: str,
    zip_path: str,
):

    project = Project(
        session_id=session_id,
        title=title,
        prompt=prompt,
        project_path=project_path,
        zip_path=zip_path,
    )

    try:

        db.add(project)
        db.commit()
        db.refresh(project)

        return project

    except Exception:

        db.rollback()
        raise


# --------------------------------------------------
# Read All
# --------------------------------------------------


def get_projects(db: Session):

    return (
        db.query(Project)
        .order_by(Project.created_at.desc())
        .all()
    )


# --------------------------------------------------
# Read One
# --------------------------------------------------


def get_project(
    db: Session,
    project_id: int,
):

    return (
        db.query(Project)
        .filter(Project.id == project_id)
        .first()
    )


# --------------------------------------------------
# Read By Session
# --------------------------------------------------


def get_projects_by_session(
    db: Session,
    session_id: str,
):

    return (
        db.query(Project)
        .filter(Project.session_id == session_id)
        .order_by(Project.created_at.desc())
        .all()
    )


# --------------------------------------------------
# Delete
# --------------------------------------------------


def delete_project(
    db: Session,
    project_id: int,
):

    project = get_project(db, project_id)

    if project is None:
        return None

    try:

        db.delete(project)
        db.commit()

        return project

    except Exception:

        db.rollback()
        raise
# --------------------------------------------------
# Runs
# --------------------------------------------------


def create_run(
    db: Session,
    run_id: str,
    session_id: str,
    prompt: str,
):
    run = Run(
        id=run_id,
        session_id=session_id,
        prompt=prompt,
        status="queued",
        current_step="queued",
        progress=0,
        message="Run queued.",
    )

    try:
        db.add(run)
        db.commit()
        db.refresh(run)

        return run

    except Exception:
        db.rollback()
        raise


def get_run(
    db: Session,
    run_id: str,
):
    return (
        db.query(Run)
        .filter(Run.id == run_id)
        .first()
    )


def get_runs_by_session(
    db: Session,
    session_id: str,
):
    return (
        db.query(Run)
        .filter(Run.session_id == session_id)
        .order_by(Run.created_at.desc())
        .all()
    )


def update_run(
    db: Session,
    run_id: str,
    *,
    status: str | None = None,
    current_step: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    result: dict | None = None,
    error: str | None = None,
    started: bool = False,
    completed: bool = False,
):
    run = get_run(db, run_id)

    if run is None:
        return None

    if status is not None:
        run.status = status

    if current_step is not None:
        run.current_step = current_step

    if progress is not None:
        run.progress = max(0, min(100, progress))

    if message is not None:
        run.message = message

    if result is not None:
        run.result = json.dumps(
            result,
            default=str,
        )

    if error is not None:
        run.error = error

    if started and run.started_at is None:
        run.started_at = datetime.now(UTC).replace(tzinfo=None)

    if completed:
        run.completed_at = datetime.now(UTC).replace(tzinfo=None)

    run.updated_at = datetime.now(UTC).replace(tzinfo=None)

    try:
        db.commit()
        db.refresh(run)

        return run

    except Exception:
        db.rollback()
        raise