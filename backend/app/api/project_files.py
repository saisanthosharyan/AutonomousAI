from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from app.core.config import settings
from app.core.logger import logger
from app.services.auth.dependencies import get_current_user
from app.database.models import User


router = APIRouter(
    prefix="/project-files",
    tags=["Project Files"],
)


TEXT_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".html": "html",
    ".css": "css",
    ".json": "json",
    ".md": "markdown",
    ".txt": "text",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "text",
    ".sh": "shell",
    ".bat": "batch",
    ".ps1": "powershell",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".sql": "sql",
    ".env.example": "text",
}


IGNORED_NAMES = {
    ".git",
    ".github",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".DS_Store",
    "__MACOSX",
    "execution",
}


MAX_FILE_SIZE = 2 * 1024 * 1024


def _get_project_root() -> Path:
    return Path(
        settings.GENERATED_PROJECTS_DIR
    ).resolve()


def _resolve_project(project_name: str) -> Path:
    root = _get_project_root()

    safe_name = Path(
        project_name
    ).name

    if not safe_name or safe_name != project_name:
        raise HTTPException(
            status_code=400,
            detail="Invalid project name.",
        )

    project = (
        root / safe_name
    ).resolve()

    try:
        project.relative_to(root)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid project path.",
        )

    if not project.exists():
        raise HTTPException(
            status_code=404,
            detail="Project not found.",
        )

    if not project.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Project path is not a directory.",
        )

    return project


def _language_for_file(
    file_path: Path,
) -> str:
    name = file_path.name.lower()

    if name == ".gitignore":
        return "text"

    if name == "dockerfile":
        return "dockerfile"

    if name == "makefile":
        return "makefile"

    suffix = file_path.suffix.lower()

    return TEXT_EXTENSIONS.get(
        suffix,
        "text",
    )


def _is_ignored(
    path: Path,
    project_root: Path,
) -> bool:
    try:
        relative = path.relative_to(
            project_root
        )
    except ValueError:
        return True

    return any(
        part in IGNORED_NAMES
        for part in relative.parts
    )


def _collect_files(
    project_root: Path,
) -> list[dict]:
    files: list[dict] = []

    for path in sorted(
        project_root.rglob("*")
    ):
        if not path.is_file():
            continue

        if _is_ignored(
            path,
            project_root,
        ):
            continue

        try:
            relative = path.relative_to(
                project_root
            )
        except ValueError:
            continue

        if path.stat().st_size > MAX_FILE_SIZE:
            files.append(
                {
                    "path": relative.as_posix(),
                    "language": _language_for_file(
                        path
                    ),
                    "content": None,
                    "size": path.stat().st_size,
                    "readable": False,
                    "reason": (
                        "File is larger than "
                        "the allowed preview size."
                    ),
                }
            )
            continue

        try:
            content = path.read_text(
                encoding="utf-8"
            )
        except UnicodeDecodeError:
            files.append(
                {
                    "path": relative.as_posix(),
                    "language": "binary",
                    "content": None,
                    "size": path.stat().st_size,
                    "readable": False,
                    "reason": "Binary file.",
                }
            )
            continue
        except Exception as exc:
            logger.warning(
                "Unable to read project file %s: %s",
                path,
                exc,
            )
            continue

        files.append(
            {
                "path": relative.as_posix(),
                "language": _language_for_file(
                    path
                ),
                "content": content,
                "size": path.stat().st_size,
                "readable": True,
            }
        )

    return files


@router.get("/{project_name}")
def get_project_files(
    project_name: str,
    current_user: User = Depends(
        get_current_user
    ),
):
    try:
        project_root = _resolve_project(
            project_name
        )

        files = _collect_files(
            project_root
        )

        return {
            "success": True,
            "project_name": project_root.name,
            "file_count": len(files),
            "files": files,
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Failed to read project files: %s",
            project_name,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to read project files.",
        )