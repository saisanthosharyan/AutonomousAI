from pathlib import Path
from typing import Optional

from app.core.logger import logger
from app.project.project_analyzer import ProjectAnalyzer


class ProjectValidator:
    """
    Validates generated projects according to the user's
    requested generation mode and detected project type.

    The user's request is the source of truth.

    Minimal code/script requests must not be forced to contain
    README.md, .gitignore, tests, or dependency manifests.
    """

    REQUIRED_FILES = [
        "README.md",
        ".gitignore",
    ]

    DEPENDENCY_FILES = [
        "requirements.txt",
        "package.json",
        "pyproject.toml",
    ]

    SOURCE_PATTERNS = [
        "*.py",
        "*.js",
        "*.ts",
        "*.java",
        "*.cpp",
        "*.c",
        "*.go",
        "*.rs",
        "*.php",
        "*.rb",
    ]

    def __init__(self):
        self.project_analyzer = ProjectAnalyzer()

    def _has_required_files(self, path: Path) -> bool:
        return all(
            (path / file).exists()
            for file in self.REQUIRED_FILES
        )

    def _has_dependency_file(self, path: Path) -> bool:
        return any(
            (path / item).exists()
            for item in self.DEPENDENCY_FILES
        )

    def _has_source_files(self, path: Path) -> bool:
        return any(
            any(path.rglob(pattern))
            for pattern in self.SOURCE_PATTERNS
        )

    def _is_static_web_project(self, path: Path) -> bool:
        return (
            (path / "index.html").exists()
            and any(path.rglob("*.html"))
        )

    def _detect_project_type(self, path: Path) -> str:
        try:
            detected = self.project_analyzer.detect(str(path))

            if detected:
                return str(detected).lower()

        except Exception as exc:
            logger.warning(
                f"Project type detection failed: {exc}"
            )

        if self._is_static_web_project(path):
            return "static_web"

        return "unknown"

    def _detect_project_root(self, project: Path) -> Path:
        """
        Detect the actual generated project root.

        Supports both direct and nested project structures.
        """

        if (
            self._has_required_files(project)
            or self._has_dependency_file(project)
            or self._has_source_files(project)
            or self._is_static_web_project(project)
        ):
            logger.info(
                f"Project files found directly in: {project}"
            )

            return project

        try:
            subdirectories = [
                item
                for item in project.iterdir()
                if item.is_dir()
                and not item.name.startswith(".")
                and item.name not in {
                    "__pycache__",
                    "venv",
                    ".venv",
                    "node_modules",
                }
            ]

        except OSError as exc:
            logger.warning(
                f"Unable to inspect project directory: {exc}"
            )

            return project

        for subdirectory in subdirectories:
            has_required = self._has_required_files(
                subdirectory
            )

            has_dependency = self._has_dependency_file(
                subdirectory
            )

            has_source = self._has_source_files(
                subdirectory
            )

            is_static_web = self._is_static_web_project(
                subdirectory
            )

            if (
                has_required
                or has_dependency
                or has_source
                or is_static_web
            ):
                logger.info(
                    f"Detected nested project root: "
                    f"{subdirectory}"
                )

                return subdirectory

        logger.warning(
            "Could not detect nested project root. "
            "Using provided project path."
        )

        return project

    def _validate_dependency_file(
        self,
        project_root: Path,
        project_type: str,
        report: dict,
    ) -> None:
        """
        Validate dependency configuration only when the
        detected technology actually requires it.
        """

        if project_type == "static_web":
            logger.info(
                "Static web project detected. "
                "Dependency file requirement skipped."
            )
            return

        if project_type == "node":
            required_files = ["package.json"]

        elif project_type == "python":
            logger.info(
                "Python project detected. "
                "Dependency manifest is optional."
            )
            return

        elif project_type in {"java", "cpp"}:
            logger.info(
                f"{project_type} project detected. "
                "Dependency manifest is optional."
            )
            return

        else:
            logger.info(
                f"{project_type} project detected. "
                "Dependency manifest requirement skipped."
            )
            return

        dependency_exists = any(
            (project_root / item).exists()
            for item in required_files
        )

        if dependency_exists:
            logger.info(
                "Required dependency configuration "
                "detected successfully."
            )
            return

        dependency_message = " OR ".join(
            required_files
        )

        logger.warning(
            "Missing dependency file: "
            f"{dependency_message}"
        )

        report["missing_files"].append(
            dependency_message
        )

        report["score"] -= 10

    def _is_minimal_generation(
        self,
        generation_mode: Optional[str],
    ) -> bool:
        return str(
            generation_mode or ""
        ).strip().lower() in {
            "code",
            "script",
        }

    def _validate_optional_project_files(
        self,
        project_root: Path,
        project_type: str,
        generation_mode: Optional[str],
        report: dict,
    ) -> None:
        """
        README.md and .gitignore are optional unless the user
        requested a full project/application structure.

        They are never required for simple code/script requests.
        """

        if self._is_minimal_generation(
            generation_mode
        ):
            logger.info(
                "Minimal code/script generation detected. "
                "README.md and .gitignore are optional."
            )
            return

        if project_type in {
            "static_web",
            "web",
            "website",
            "frontend",
        }:
            logger.info(
                "Frontend project detected. "
                "README.md and .gitignore are optional."
            )
            return

        if str(
            generation_mode or ""
        ).strip().lower() in {
            "project",
            "application",
        }:
            if not (
                project_root / "README.md"
            ).exists():
                logger.info(
                    "README.md not present. "
                    "Documentation is optional."
                )

            if not (
                project_root / ".gitignore"
            ).exists():
                logger.info(
                    ".gitignore not present. "
                    "Git configuration is optional."
                )

        else:
            logger.info(
                "Optional project metadata files are not required."
            )

    def _validate_requested_files(
        self,
        project_root: Path,
        requested_files: Optional[list],
        report: dict,
    ) -> None:
        """
        Explicitly requested files are authoritative.
        """

        if not requested_files:
            return

        generated_paths = {
            str(
                file.relative_to(project_root)
            ).replace("\\", "/").lower()
            for file in project_root.rglob("*")
            if file.is_file()
        }

        generated_filenames = {
            path.split("/")[-1]
            for path in generated_paths
        }

        for requested in requested_files:
            requested_path = str(
                requested
            ).replace("\\", "/").strip().lower()

            if not requested_path:
                continue

            if requested_path in generated_paths:
                continue

            requested_filename = (
                requested_path.split("/")[-1]
            )

            if requested_filename in generated_filenames:
                continue

            logger.warning(
                f"Missing explicitly requested file: "
                f"{requested}"
            )

            report["missing_files"].append(
                requested
            )

            report["score"] -= 10

    def validate(
        self,
        project_path: str,
        generation_mode: Optional[str] = None,
        requested_files: Optional[list] = None,
    ) -> dict:
        """
        Validate a generated project.

        generation_mode:
            code
            script
            website
            application
            api
            library
            project

        requested_files:
            Files explicitly requested by the user.
        """

        project = Path(project_path).resolve()

        logger.info("=" * 60)
        logger.info("Project Validation Started")
        logger.info("=" * 60)

        logger.info(
            f"Project: {project}"
        )

        logger.info(
            f"Generation mode: "
            f"{generation_mode or 'not provided'}"
        )

        logger.info(
            f"Requested files: "
            f"{requested_files or []}"
        )

        report = {
            "valid": True,
            "score": 100,
            "missing_files": [],
            "warnings": [],
            "project_type": "unknown",
            "generation_mode": generation_mode,
        }

        try:
            if not project.exists():
                logger.error(
                    "Project directory does not exist."
                )

                return {
                    "valid": False,
                    "score": 0,
                    "missing_files": [],
                    "warnings": [
                        f"Project folder does not exist: {project}"
                    ],
                    "project_type": "unknown",
                    "generation_mode": generation_mode,
                }

            if not project.is_dir():
                logger.error(
                    "Provided project path is not a directory."
                )

                return {
                    "valid": False,
                    "score": 0,
                    "missing_files": [],
                    "warnings": [
                        f"Project path is not a directory: {project}"
                    ],
                    "project_type": "unknown",
                    "generation_mode": generation_mode,
                }

            project_root = self._detect_project_root(
                project
            )

            if not any(project_root.iterdir()):
                logger.error(
                    "Project directory is empty."
                )

                return {
                    "valid": False,
                    "score": 0,
                    "missing_files": [],
                    "warnings": [
                        "Project directory is empty."
                    ],
                    "project_type": "unknown",
                    "generation_mode": generation_mode,
                }

            logger.info(
                f"Using validation root: {project_root}"
            )

            project_type = self._detect_project_type(
                project_root
            )

            report["project_type"] = project_type

            logger.info(
                f"Detected project type: {project_type}"
            )

            if project_type == "unknown":
                if self._is_static_web_project(
                    project_root
                ):
                    project_type = "static_web"
                    report["project_type"] = project_type

            self._validate_requested_files(
                project_root,
                requested_files,
                report,
            )

            self._validate_optional_project_files(
                project_root,
                project_type,
                generation_mode,
                report,
            )

            if project_type == "static_web":
                index_file = project_root / "index.html"

                if not index_file.exists():
                    logger.warning(
                        "Missing file: index.html"
                    )

                    report["missing_files"].append(
                        "index.html"
                    )

                    report["score"] -= 10

                else:
                    logger.info(
                        "Static web entry point detected: "
                        "index.html"
                    )

            self._validate_dependency_file(
                project_root,
                project_type,
                report,
            )

            source_exists = self._has_source_files(
                project_root
            )

            if project_type == "static_web":
                source_exists = (
                    project_root / "index.html"
                ).exists()

            if not source_exists:
                logger.warning(
                    "No source files found."
                )

                report["warnings"].append(
                    "No source files found."
                )

                report["score"] -= 20

                if self._is_minimal_generation(
                    generation_mode
                ):
                    report["missing_files"].append(
                        "source code"
                    )

            else:
                logger.info(
                    "Source files detected successfully."
                )

            try:
                generated_files = [
                    file
                    for file in project_root.rglob("*")
                    if file.is_file()
                    and "__pycache__" not in file.parts
                ]

                logger.info(
                    f"Detected {len(generated_files)} "
                    f"project files."
                )

            except OSError as exc:
                logger.warning(
                    f"Unable to count project files: {exc}"
                )

            report["score"] = max(
                report["score"],
                0,
            )

            report["valid"] = not bool(
                report["missing_files"]
            )

            logger.info(
                f"Validation completed. "
                f"Score: {report['score']}"
            )

            logger.info(
                f"Missing files: "
                f"{len(report['missing_files'])}"
            )

            logger.info(
                f"Warnings: "
                f"{len(report['warnings'])}"
            )

            logger.info(
                f"Validation status: "
                f"{'VALID' if report['valid'] else 'INVALID'}"
            )

            return report

        except Exception as exc:
            logger.exception(
                "Project validation failed."
            )

            return {
                "valid": False,
                "score": 0,
                "missing_files": [],
                "warnings": [
                    str(exc)
                ],
                "project_type": report.get(
                    "project_type",
                    "unknown",
                ),
                "generation_mode": generation_mode,
            }

        finally:
            logger.info("=" * 60)
            logger.info(
                "Project Validation Finished"
            )
            logger.info("=" * 60)