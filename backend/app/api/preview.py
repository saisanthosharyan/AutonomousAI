from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.logger import logger


router = APIRouter(
    prefix="/preview",
    tags=["Preview"],
)


@router.get("/{project_name}/{file_path:path}")
async def preview_file(
    project_name: str,
    file_path: str,
):
    try:
        project_name = Path(project_name).name

        generated_root = Path(
            settings.GENERATED_PROJECTS_DIR
        ).resolve()

        project_dir = (
            generated_root / project_name
        ).resolve()

        try:
            project_dir.relative_to(
                generated_root
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid project name.",
            )

        if not project_dir.exists():
            raise HTTPException(
                status_code=404,
                detail="Preview project not found.",
            )

        if not project_dir.is_dir():
            raise HTTPException(
                status_code=404,
                detail="Preview project is not a directory.",
            )

        requested_file = (
            project_dir / file_path
        ).resolve()

        try:
            requested_file.relative_to(
                project_dir
            )
        except ValueError:
            logger.warning(
                "Blocked preview path traversal: %s",
                file_path,
            )

            raise HTTPException(
                status_code=400,
                detail="Invalid preview file path.",
            )

        if not requested_file.exists():
            raise HTTPException(
                status_code=404,
                detail="Preview file not found.",
            )

        if not requested_file.is_file():
            raise HTTPException(
                status_code=404,
                detail="Preview target is not a file.",
            )

        return FileResponse(
            path=requested_file,
        )

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Preview file serving failed."
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to serve preview file.",
        )