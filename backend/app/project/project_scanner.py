from __future__ import annotations

from pathlib import Path
from typing import Any


class ProjectScanner:
    """
    Scans an existing software project and produces a structured
    description of its contents.

    Responsibilities
    ----------------
    - Traverse project directories
    - Ignore unnecessary folders/files
    - Detect programming languages
    - Detect configuration files
    - Count files/directories
    - Produce metadata for downstream analyzers
    """

    # ---------------------------------------------------------
    # Directories ignored during traversal
    # ---------------------------------------------------------

    IGNORED_DIRECTORIES = {
        ".git",
        ".github",
        ".idea",
        ".vscode",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
        ".next",
        "coverage",
        "out",
        "target",
    }

    # ---------------------------------------------------------
    # File extensions ignored
    # ---------------------------------------------------------

    IGNORED_EXTENSIONS = {
        ".pyc",
        ".pyo",
        ".log",
        ".tmp",
        ".cache",
    }

    # ---------------------------------------------------------
    # Configuration files
    # ---------------------------------------------------------

    CONFIG_FILES = {
        "requirements.txt",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "pyproject.toml",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "Cargo.toml",
        "go.mod",
        "pom.xml",
        "composer.json",
        ".env",
        ".env.example",
        "README.md",
        "README.txt",
        "README",
    }

    # ---------------------------------------------------------
    # Extension → Language map
    # ---------------------------------------------------------

    LANGUAGE_MAP = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "React",
        ".ts": "TypeScript",
        ".tsx": "React TypeScript",
        ".java": "Java",
        ".kt": "Kotlin",
        ".cpp": "C++",
        ".cc": "C++",
        ".cxx": "C++",
        ".c": "C",
        ".cs": "C#",
        ".go": "Go",
        ".rs": "Rust",
        ".php": "PHP",
        ".swift": "Swift",
        ".rb": "Ruby",
        ".html": "HTML",
        ".css": "CSS",
        ".scss": "SCSS",
        ".sql": "SQL",
        ".sh": "Shell",
        ".ps1": "PowerShell",
    }

    # =========================================================
    # PUBLIC
    # =========================================================

    def scan(
        self,
        project_path: str | Path,
    ) -> dict[str, Any]:
        """
        Scan an entire software project.

        Returns
        -------
        Dictionary containing project metadata.
        """

        root = Path(project_path).resolve()

        if not root.exists():
            raise FileNotFoundError(root)

        if not root.is_dir():
            raise NotADirectoryError(root)

        files: list[str] = []
        directories: list[str] = []
        config_files: list[str] = []

        languages: set[str] = set()

        total_files = 0
        total_directories = 0

        for current_root, dirnames, filenames in self._walk(root):

            relative_dir = current_root.relative_to(root)

            directories.append(str(relative_dir))

            total_directories += 1

            for filename in filenames:

                file_path = current_root / filename

                if self._ignore_file(file_path):
                    continue

                total_files += 1

                relative = str(file_path.relative_to(root))

                files.append(relative)

                language = self._detect_language(file_path)

                if language:
                    languages.add(language)

                if self._is_config_file(file_path):
                    config_files.append(relative)

        return {
            "project_name": root.name,
            "root_path": str(root),
            "total_files": total_files,
            "total_directories": total_directories,
            "languages": sorted(languages),
            "config_files": sorted(config_files),
            "source_files": sorted(files),
            "directories": sorted(directories),
        }

    # =========================================================
    # WALK
    # =========================================================

    def _walk(
        self,
        root: Path,
    ):
        """
        Recursive directory traversal with ignored folders removed.
        """

        import os

        for current_root, dirnames, filenames in os.walk(root):

            dirnames[:] = [
                d
                for d in dirnames
                if not self._ignore_directory(d)
            ]

            yield Path(current_root), dirnames, filenames

    # =========================================================
    # HELPERS
    # =========================================================

    def _ignore_directory(
        self,
        name: str,
    ) -> bool:

        return name in self.IGNORED_DIRECTORIES

    def _ignore_file(
        self,
        path: Path,
    ) -> bool:

        return path.suffix.lower() in self.IGNORED_EXTENSIONS

    def _is_config_file(
        self,
        path: Path,
    ) -> bool:

        return path.name in self.CONFIG_FILES

    def _detect_language(
        self,
        path: Path,
    ) -> str | None:

        return self.LANGUAGE_MAP.get(
            path.suffix.lower()
        )