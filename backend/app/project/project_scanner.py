from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ScannedFile:
    """
    Represents one file discovered inside a project.
    """

    path: str
    relative_path: str
    name: str
    extension: str
    language: str
    is_config: bool


class ProjectScanner:
    """
    Scans an existing software project and produces
    structured information about its files.

    Responsibilities:
        - Traverse project directories
        - Ignore unnecessary directories
        - Ignore unnecessary files
        - Detect programming languages
        - Detect configuration files
        - Return ScannedFile objects
    """

    # ======================================================
    # DIRECTORIES TO IGNORE
    # ======================================================

    IGNORED_DIRECTORIES = {
        # Git / IDE
        ".git",
        ".github",
        ".idea",
        ".vscode",

        # Python
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",

        # Node / frontend
        "node_modules",
        "dist",
        "build",
        ".next",
        "coverage",

        # Other build directories
        "out",
        "target",

        # AutoDev generated data
        ".autodev",
        ".autodev_debug",

        # Execution / temporary data
        "execution",
        "logs",
        "tmp",
        "temp",
    }

    # ======================================================
    # FILE EXTENSIONS TO IGNORE
    # ======================================================

    IGNORED_EXTENSIONS = {
        ".pyc",
        ".pyo",
        ".log",
        ".tmp",
        ".cache",
        ".bak",
        ".swp",
    }

    # ======================================================
    # CONFIGURATION FILES
    # ======================================================

    CONFIG_FILES = {
        "requirements.txt",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "pyproject.toml",
        "poetry.lock",

        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",

        "Cargo.toml",
        "Cargo.lock",

        "go.mod",
        "go.sum",

        "pom.xml",

        "composer.json",

        ".env",
        ".env.example",

        "README.md",
        "README.txt",
        "README",
    }

    # ======================================================
    # LANGUAGE MAP
    # ======================================================

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

    # ======================================================
    # PUBLIC SCAN METHOD
    # ======================================================

    def scan(
        self,
        project_path: str | Path,
    ) -> list[ScannedFile]:

        root = Path(project_path).resolve()

        if not root.exists():
            raise FileNotFoundError(root)

        if not root.is_dir():
            raise NotADirectoryError(root)

        results: list[ScannedFile] = []

        for current_root, dirnames, filenames in os.walk(root):

            # Remove ignored directories in-place.
            dirnames[:] = [
                directory
                for directory in dirnames
                if not self._ignore_directory(directory)
            ]

            current_path = Path(current_root)

            for filename in filenames:

                file_path = current_path / filename

                if self._ignore_file(file_path):
                    continue

                relative_path = file_path.relative_to(root)

                language = self._detect_language(file_path)

                is_config = self._is_config_file(file_path)

                results.append(
                    ScannedFile(
                        path=str(file_path),
                        relative_path=str(relative_path),
                        name=file_path.name,
                        extension=file_path.suffix.lower(),
                        language=language or "unknown",
                        is_config=is_config,
                    )
                )

        results.sort(
            key=lambda item: item.relative_path.lower()
        )

        return results

    # ======================================================
    # IGNORE DIRECTORY
    # ======================================================

    def _ignore_directory(
        self,
        name: str,
    ) -> bool:

        return name in self.IGNORED_DIRECTORIES

    # ======================================================
    # IGNORE FILE
    # ======================================================

    def _ignore_file(
        self,
        path: Path,
    ) -> bool:

        # Ignore known extensions.
        if path.suffix.lower() in self.IGNORED_EXTENSIONS:
            return True

        # Ignore common generated files.
        if path.name.startswith("~"):
            return True

        return False

    # ======================================================
    # CONFIG FILE
    # ======================================================

    def _is_config_file(
        self,
        path: Path,
    ) -> bool:

        return path.name in self.CONFIG_FILES

    # ======================================================
    # LANGUAGE DETECTION
    # ======================================================

    def _detect_language(
        self,
        path: Path,
    ) -> str | None:

        return self.LANGUAGE_MAP.get(
            path.suffix.lower()
        )