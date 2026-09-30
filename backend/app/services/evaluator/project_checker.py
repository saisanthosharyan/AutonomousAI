from pathlib import Path

from app.core.logger import logger


class ProjectChecker:
    """
    Validates the generated project's structure.

    When requested_files are provided, they are treated as the
    authoritative structural requirements for the project.
    """

    def check(
        self,
        project_path: str,
        project_type: str,
        requested_files: list[str] | None = None,
    ) -> dict:

        logger.info(
            "Checking generated project structure..."
        )

        project = Path(project_path).resolve()

        if not project.exists():
            return {
                "score": 0,
                "passed": [],
                "missing": [
                    "Project directory does not exist."
                ],
            }

        if not project.is_dir():
            return {
                "score": 0,
                "passed": [],
                "missing": [
                    "Project path is not a directory."
                ],
            }

        passed = []
        missing = []

        if requested_files:
            return self._check_requested_files(
                project,
                requested_files,
            )

        if project_type == "python":
            self._check_file(
                project / "requirements.txt",
                "requirements.txt",
                passed,
                missing,
            )

            self._check_file(
                project / "README.md",
                "README.md",
                passed,
                missing,
            )

            self._check_python_entry(
                project,
                passed,
                missing,
            )

            self._check_optional_dir(
                project / "tests",
                "tests/",
                passed,
            )

        elif project_type == "node":
            self._check_file(
                project / "package.json",
                "package.json",
                passed,
                missing,
            )

            self._check_file(
                project / "README.md",
                "README.md",
                passed,
                missing,
            )

            self._check_optional_dir(
                project / "src",
                "src/",
                passed,
            )

        elif project_type == "static_web":
            logger.info(
                "Checking static web project structure..."
            )

            self._check_file(
                project / "index.html",
                "index.html",
                passed,
                missing,
            )

            optional_files = [
                ("style.css", project / "style.css"),
                ("script.js", project / "script.js"),
                ("README.md", project / "README.md"),
                (".gitignore", project / ".gitignore"),
            ]

            for display_name, file_path in optional_files:
                if file_path.is_file():
                    passed.append(display_name)

        elif project_type == "java":
            java_files = list(project.rglob("*.java"))

            if java_files:
                passed.append(".java files")
            else:
                missing.append(".java files")

            if (project / "pom.xml").exists():
                passed.append("pom.xml")
            elif (project / "build.gradle").exists():
                passed.append("build.gradle")
            else:
                missing.append("pom.xml/build.gradle")

        elif project_type == "cpp":
            cpp_files = list(project.rglob("*.cpp"))

            if cpp_files:
                passed.append(".cpp files")
            else:
                missing.append(".cpp files")

        elif project_type == "docker":
            self._check_file(
                project / "Dockerfile",
                "Dockerfile",
                passed,
                missing,
            )

        else:
            missing.append(
                f"Unknown project type: {project_type}"
            )

        return self._build_result(
            passed,
            missing,
        )

    def _check_requested_files(
        self,
        project: Path,
        requested_files: list[str],
    ) -> dict:
        """
        Validate files explicitly requested by the user/planner.
        """

        passed = []
        missing = []

        for requested_file in requested_files:
            relative_path = Path(requested_file)

            if relative_path.is_absolute():
                relative_path = Path(
                    relative_path.name
                )

            file_path = project / relative_path

            if file_path.is_file():
                passed.append(
                    requested_file
                )
            else:
                missing.append(
                    requested_file
                )

        return self._build_result(
            passed,
            missing,
        )

    @staticmethod
    def _build_result(
        passed: list[str],
        missing: list[str],
    ) -> dict:
        total = len(passed) + len(missing)

        if total == 0:
            score = 0
        else:
            score = round(
                (len(passed) / total) * 100
            )

        return {
            "score": score,
            "passed": passed,
            "missing": missing,
        }

    @staticmethod
    def _check_file(
        file_path: Path,
        display_name: str,
        passed: list[str],
        missing: list[str],
    ) -> None:
        if file_path.is_file():
            passed.append(display_name)
        else:
            missing.append(display_name)

    @staticmethod
    def _check_optional_dir(
        directory: Path,
        display_name: str,
        passed: list[str],
    ) -> None:
        if directory.is_dir():
            passed.append(display_name)

    @staticmethod
    def _check_python_entry(
        project: Path,
        passed: list[str],
        missing: list[str],
    ) -> None:
        entry_candidates = [
            "main.py",
            "app.py",
            "run.py",
            "src/main.py",
            "src/app.py",
            "src/run.py",
        ]

        for candidate in entry_candidates:
            if (project / candidate).is_file():
                passed.append(candidate)
                return

        python_files = list(project.rglob("*.py"))

        ignored_dirs = {
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
        }

        python_files = [
            file
            for file in python_files
            if not any(
                part in ignored_dirs
                for part in file.parts
            )
        ]

        if python_files:
            passed.append(".py entry file")
        else:
            missing.append(".py entry file")
