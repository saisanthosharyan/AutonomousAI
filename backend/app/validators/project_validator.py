from pathlib import Path

from app.core.logger import logger


class ProjectValidator:
    """
    Validates the generated project structure before returning
    it to the user.

    The validator supports projects where the actual application
    is either:

    1. Directly inside project_path
    2. Inside a single nested folder such as:
       project_path/calculator_app/
    """

    REQUIRED_FILES = [
        "README.md",
        ".gitignore",
    ]

    REQUIRED_ANY = [
        [
            "requirements.txt",
            "package.json",
            "pyproject.toml",
        ]
    ]

    SOURCE_PATTERNS = [
        "*.py",
        "*.js",
        "*.ts",
        "*.java",
        "*.cpp",
    ]

    def _has_required_files(self, path: Path) -> bool:
        """
        Check whether a directory contains the basic required files.
        """

        return all(
            (path / file).exists()
            for file in self.REQUIRED_FILES
        )

    def _has_dependency_file(self, path: Path) -> bool:
        """
        Check whether a supported dependency file exists.
        """

        return any(
            (path / item).exists()
            for group in self.REQUIRED_ANY
            for item in group
        )

    def _has_source_files(self, path: Path) -> bool:
        """
        Check whether the project contains at least one source file.
        """

        return any(
            any(path.rglob(pattern))
            for pattern in self.SOURCE_PATTERNS
        )

    def _detect_project_root(self, project: Path) -> Path:
        """
        Detect the actual project root.

        Handles both structures:

        project/
        ├── README.md
        ├── .gitignore
        ├── requirements.txt
        └── src/

        OR:

        project/
        └── calculator_app/
            ├── README.md
            ├── .gitignore
            ├── requirements.txt
            ├── src/
            └── tests/
        """

        # --------------------------------------------------
        # Case 1:
        # Project files are directly inside project_path
        # --------------------------------------------------

        if (
            self._has_required_files(project)
            or self._has_dependency_file(project)
            or self._has_source_files(project)
        ):
            logger.info(
                f"Project files found directly in: {project}"
            )

            return project

        # --------------------------------------------------
        # Case 2:
        # Project is inside a nested directory
        # --------------------------------------------------

        try:
            subdirectories = [
                item
                for item in project.iterdir()
                if item.is_dir()
                if (
                    item.is_dir()
                    and not item.name.startswith(".")
                    and item.name not in {
                        "__pycache__",
                        "venv",
                        "node_modules",
                    }
                )
            ]

        except OSError as e:

            logger.warning(
                f"Unable to inspect project directory: {e}"
            )

            return project

        # --------------------------------------------------
        # Look for the actual project directory
        # --------------------------------------------------

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

            if (
                has_required
                or has_dependency
                or has_source
            ):

                logger.info(
                    f"Detected nested project root: "
                    f"{subdirectory}"
                )

                return subdirectory

        # --------------------------------------------------
        # If nothing specific is found, keep original root
        # --------------------------------------------------

        logger.warning(
            "Could not detect nested project root. "
            "Using provided project path."
        )

        return project

    def validate(
        self,
        project_path: str,
    ) -> dict:
        """
        Validate a generated project.

        Args:
            project_path: Path to the generated project.

        Returns:
            Dictionary containing validation status,
            score, missing files, and warnings.
        """

        project = Path(project_path).resolve()

        logger.info("=" * 60)
        logger.info("Project Validation Started")
        logger.info("=" * 60)

        logger.info(
            f"Project: {project}"
        )

        report = {
            "valid": True,
            "score": 100,
            "missing_files": [],
            "warnings": [],
        }

        try:

            # ==================================================
            # Check project directory
            # ==================================================

            if not project.exists():

                logger.error(
                    "Project directory does not exist."
                )

                return {
                    "valid": False,
                    "score": 0,
                    "missing_files": [],
                    "warnings": [
                        f"Project folder does not exist: "
                        f"{project}"
                    ],
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
                        f"Project path is not a directory: "
                        f"{project}"
                    ],
                }

            # ==================================================
            # Detect actual project root
            # ==================================================

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
                }

            logger.info(
                f"Using validation root: {project_root}"
            )

            # ==================================================
            # Required Files
            # ==================================================

            for file in self.REQUIRED_FILES:

                file_path = project_root / file

                if not file_path.exists():

                    logger.warning(
                        f"Missing file: {file}"
                    )

                    report["missing_files"].append(
                        file
                    )

                    report["score"] -= 10

            # ==================================================
            # Dependency File
            # ==================================================

            for group in self.REQUIRED_ANY:

                dependency_exists = any(
                    (
                        project_root / item
                    ).exists()
                    for item in group
                )

                if not dependency_exists:

                    dependency_message = (
                        " OR ".join(group)
                    )

                    logger.warning(
                        "Missing dependency file: "
                        f"{dependency_message}"
                    )

                    report["missing_files"].append(
                        dependency_message
                    )

                    report["score"] -= 10

            # ==================================================
            # Source Files
            # ==================================================

            source_exists = self._has_source_files(
                project_root
            )

            if not source_exists:

                logger.warning(
                    "No source files found."
                )

                report["warnings"].append(
                    "No source files found."
                )

                report["score"] -= 20

            else:

                logger.info(
                    "Source files detected successfully."
                )

            # ==================================================
            # Additional Project Information
            # ==================================================

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

            except OSError as e:

                logger.warning(
                    f"Unable to count project files: {e}"
                )

            # ==================================================
            # Finalize Score
            # ==================================================

            report["score"] = max(
                report["score"],
                0
            )

            # A project with missing required files
            # should not be considered valid.

            if report["missing_files"]:

                report["valid"] = False

            else:

                report["valid"] = True

            # ==================================================
            # Final Logging
            # ==================================================

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
            }

        finally:

            logger.info("=" * 60)
            logger.info(
                "Project Validation Finished"
            )
            logger.info("=" * 60)