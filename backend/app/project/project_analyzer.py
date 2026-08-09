from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Set

from app.core.logger import logger


class ProjectAnalyzer:
    """
    Analyzes generated projects and provides a single source of
    truth for execution project-type detection.

    Responsibilities:

    - Scan project files
    - Count files and folders
    - Detect programming language
    - Detect framework
    - Detect dependencies
    - Detect entry point
    - Detect execution type
    - Provide project metadata to ExecutionManager,
      TestManager, Reviewer and Memory systems
    """

    SOURCE_EXTENSIONS = {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".java",
        ".cpp",
        ".c",
        ".cs",
        ".go",
        ".rs",
        ".php",
        ".html",
        ".css",
        ".json",
        ".yml",
        ".yaml",
    }

    IGNORED_DIRS = {
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".git",
        "node_modules",
        "dist",
        "build",
        ".mypy_cache",
        ".idea",
        ".vscode",
        ".next",
        "coverage",
    }

    IGNORED_FILES = {
        "__init__.py",
        "setup.py",
        "conftest.py",
    }

    _DETECTION_ORDER = (
        "docker",
        "node",
        "python",
        "java",
        "cpp",
    )

    # ==========================================================
    # METADATA ANALYSIS
    # ==========================================================

    def analyze(
        self,
        project_path: str,
    ) -> Dict:

        logger.info(
            "Analyzing project: %s",
            project_path,
        )

        root = Path(
            project_path
        ).resolve()

        if not root.exists():
            raise FileNotFoundError(
                project_path
            )

        if not root.is_dir():
            raise NotADirectoryError(
                project_path
            )

        files = []
        folders = []

        total_lines = 0

        for item in root.rglob("*"):

            if self._is_ignored_path(
                item,
                root,
            ):
                continue

            if item.is_dir():

                folders.append(
                    str(
                        item.relative_to(root)
                    )
                )

                continue

            files.append(item)

            if item.suffix.lower() in self.SOURCE_EXTENSIONS:

                try:

                    total_lines += len(
                        item.read_text(
                            encoding="utf-8",
                            errors="ignore",
                        ).splitlines()
                    )

                except Exception:
                    pass

        language = self.detect_language(
            root
        )

        framework = self.detect_framework(
            root
        )

        dependencies = self.detect_dependencies(
            root
        )

        entry_point = self.detect_entry_point(
            root
        )

        execution_type = self.detect(
            root
        )

        summary = {
            "project_name": root.name,
            "project_path": str(root),
            "language": language,
            "framework": framework,
            "entry_point": entry_point,
            "execution_type": execution_type,
            "dependencies": dependencies,
            "file_count": len(files),
            "folder_count": len(folders),
            "total_lines": total_lines,
            "files": [
                str(
                    f.relative_to(root)
                )
                for f in files
            ],
        }

        logger.info(
            "Project analyzed successfully."
        )

        return summary

    # ==========================================================
    # EXECUTION TYPE
    # ==========================================================

    def detect(
        self,
        project_path: str,
        exclude: Optional[Set[str]] = None,
    ) -> str:

        exclude = exclude or set()

        root = Path(
            project_path
        ).resolve()

        if not root.exists():
            raise FileNotFoundError(
                f"Project directory does not exist: {root}"
            )

        if not root.is_dir():
            raise NotADirectoryError(
                f"Project path is not a directory: {root}"
            )

        logger.info(
            "Detecting execution project type: %s "
            "(exclude=%s)",
            root,
            sorted(exclude) or "none",
        )

        checks = {
            "docker": lambda: self._has_dockerfile(
                root
            ),

            "node": lambda: self._contains_node(
                root
            ),

            "python": lambda: self._contains_python(
                root
            ),

            "java": lambda: self._contains_java(
                root
            ),

            "cpp": lambda: self._contains_cpp(
                root
            ),
        }

        for project_type in self._DETECTION_ORDER:

            if project_type in exclude:
                continue

            try:

                detected = checks[
                    project_type
                ]()

            except Exception as exc:

                logger.warning(
                    "Detection check failed for %s: %s",
                    project_type,
                    exc,
                )

                detected = False

            if detected:

                logger.info(
                    "Detected execution project type: %s",
                    project_type,
                )

                return project_type

        logger.warning(
            "Unable to determine execution project type: %s",
            root,
        )

        return "unknown"

    # ==========================================================
    # DOCKER
    # ==========================================================

    def _has_dockerfile(
        self,
        root: Path,
    ) -> bool:

        return (
            root / "Dockerfile"
        ).is_file()

    # ==========================================================
    # NODE
    # ==========================================================

    def _contains_node(
        self,
        root: Path,
    ) -> bool:

        if (
            root / "package.json"
        ).is_file():

            return True

        node_indicators = (
            "server.js",
            "server.ts",
            "index.js",
            "index.ts",
            "app.js",
            "app.ts",
            "main.js",
            "main.ts",
        )

        for filename in node_indicators:

            if (
                root / filename
            ).is_file():

                return True

        # Only treat JS/TS as Node when the project does not
        # clearly look like a browser-only static frontend.
        js_files = self._source_files(
            root,
            {
                ".js",
                ".ts",
                ".jsx",
                ".tsx",
            },
        )

        if not js_files:
            return False

        for file in js_files:

            try:

                text = file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                ).lower()

            except Exception:
                continue

            node_markers = (
                "require(",
                "module.exports",
                "process.env",
                "express(",
                "from 'express'",
                'from "express"',
                "from 'node:",
                'from "node:',
                "createServer(",
                "http.createServer",
            )

            if any(
                marker in text
                for marker in node_markers
            ):

                return True

        return False

    # ==========================================================
    # PYTHON
    # ==========================================================

    def _contains_python(
        self,
        root: Path,
    ) -> bool:

        indicators = (
            "requirements.txt",
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "Pipfile",
            "poetry.lock",
            "uv.lock",
        )

        for filename in indicators:

            if (
                root / filename
            ).is_file():

                return True

        return bool(
            self._source_files(
                root,
                {".py"},
            )
        )

    # ==========================================================
    # JAVA
    # ==========================================================

    def _contains_java(
        self,
        root: Path,
    ) -> bool:

        return bool(
            self._source_files(
                root,
                {".java"},
            )
        )

    # ==========================================================
    # C++
    # ==========================================================

    def _contains_cpp(
        self,
        root: Path,
    ) -> bool:

        return bool(
            self._source_files(
                root,
                {
                    ".cpp",
                    ".cc",
                    ".cxx",
                    ".c",
                },
            )
        )

    # ==========================================================
    # SOURCE FILES
    # ==========================================================

    def _source_files(
        self,
        root: Path,
        extensions: Set[str],
    ) -> List[Path]:

        result = []

        for file in root.rglob("*"):

            if not file.is_file():
                continue

            if self._is_ignored_path(
                file,
                root,
            ):
                continue

            if file.suffix.lower() in extensions:

                result.append(file)

        return result

    # ==========================================================
    # LANGUAGE
    # ==========================================================

    def detect_language(
        self,
        root: Path,
    ) -> str:

        counts = {}

        mapping = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".jsx": "React",
            ".java": "Java",
            ".cpp": "C++",
            ".c": "C",
            ".cs": "C#",
            ".go": "Go",
            ".rs": "Rust",
            ".php": "PHP",
        }

        for file in root.rglob("*"):

            if not file.is_file():
                continue

            if self._is_ignored_path(
                file,
                root,
            ):
                continue

            language = mapping.get(
                file.suffix.lower()
            )

            if language:

                counts[language] = (
                    counts.get(language, 0) + 1
                )

        if not counts:
            return "Unknown"

        return max(
            counts,
            key=counts.get,
        )

    # ==========================================================
    # FRAMEWORK
    # ==========================================================

    def detect_framework(
        self,
        root: Path,
    ) -> str:

        package = root / "package.json"

        if package.exists():

            try:

                text = package.read_text(
                    encoding="utf-8",
                    errors="ignore",
                ).lower()

                if "next" in text:
                    return "Next.js"

                if "react" in text:
                    return "React"

                if "vue" in text:
                    return "Vue"

                if "express" in text:
                    return "Express"

            except Exception:
                pass

        requirements = (
            root / "requirements.txt"
        )

        if requirements.exists():

            try:

                text = requirements.read_text(
                    encoding="utf-8",
                    errors="ignore",
                ).lower()

                if "fastapi" in text:
                    return "FastAPI"

                if "django" in text:
                    return "Django"

                if "flask" in text:
                    return "Flask"

                if "streamlit" in text:
                    return "Streamlit"

                if "gradio" in text:
                    return "Gradio"

            except Exception:
                pass

        return "Unknown"

    # ==========================================================
    # DEPENDENCIES
    # ==========================================================

    def detect_dependencies(
        self,
        root: Path,
    ) -> List[str]:

        deps = []

        req = root / "requirements.txt"

        if req.exists():

            try:

                for line in req.read_text(
                    encoding="utf-8",
                    errors="ignore",
                ).splitlines():

                    line = line.strip()

                    if (
                        line
                        and not line.startswith("#")
                    ):

                        deps.append(line)

            except Exception:
                pass

        package = root / "package.json"

        if package.exists():

            deps.append(
                "package.json"
            )

        return deps

    # ==========================================================
    # ENTRY POINT
    # ==========================================================

    def detect_entry_point(
        self,
        root: Path,
    ) -> str:

        candidates = [
            "main.py",
            "app.py",
            "server.py",
            "run.py",
            "cli.py",
            "index.js",
            "server.js",
            "main.js",
            "index.ts",
            "server.ts",
            "main.ts",
        ]

        for name in candidates:

            file = root / name

            if file.is_file():

                return name

        # Search one level deeper for common entry points.
        for name in candidates:

            matches = [
                file
                for file in root.rglob(name)
                if not self._is_ignored_path(
                    file,
                    root,
                )
            ]

            if matches:

                matches.sort(
                    key=lambda p: (
                        len(
                            p.relative_to(root).parts
                        ),
                        str(p).lower(),
                    )
                )

                return str(
                    matches[0].relative_to(root)
                )

        return ""

    # ==========================================================
    # IGNORE PATH
    # ==========================================================

    def _is_ignored_path(
        self,
        item: Path,
        root: Path,
    ) -> bool:

        try:

            relative = item.relative_to(
                root
            )

        except ValueError:

            return True

        return any(
            part in self.IGNORED_DIRS
            for part in relative.parts
        )