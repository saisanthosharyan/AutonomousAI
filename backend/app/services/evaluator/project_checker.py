from pathlib import Path

from app.core.logger import logger


class ProjectChecker:
    """
    Validates the generated project's structure.

    Checks whether important files/folders exist
    based on the detected project type.

    Returns a structure report with:

    - score
    - passed checks
    - missing items
    """

    def check(
        self,
        project_path: str,
        project_type: str,
    ) -> dict:

        logger.info(
            "Checking generated project structure..."
        )

        project = Path(project_path).resolve()

        if not project.exists():

            logger.error(
                "Project directory does not exist."
            )

            return {
                "score": 0,
                "passed": [],
                "missing": [
                    "Project directory does not exist."
                ],
            }

        if not project.is_dir():

            logger.error(
                "Project path is not a directory."
            )

            return {
                "score": 0,
                "passed": [],
                "missing": [
                    "Project path is not a directory."
                ],
            }

        passed = []
        missing = []

        # -----------------------------------------
        # Python Project
        # -----------------------------------------

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

        # -----------------------------------------
        # Node Project
        # -----------------------------------------

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

        # -----------------------------------------
        # Static Web Project
        # -----------------------------------------

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

            self._check_file(
                project / "style.css",
                "style.css",
                passed,
                missing,
            )

            self._check_file(
                project / "script.js",
                "script.js",
                passed,
                missing,
            )

            self._check_file(
                project / "README.md",
                "README.md",
                passed,
                missing,
            )

            self._check_file(
                project / ".gitignore",
                ".gitignore",
                passed,
                missing,
            )

        # -----------------------------------------
        # Java
        # -----------------------------------------

        elif project_type == "java":

            java_files = list(
                project.rglob("*.java")
            )

            if java_files:

                passed.append(".java files")

            else:

                missing.append(".java files")

            if (
                project / "pom.xml"
            ).exists():

                passed.append("pom.xml")

            elif (
                project / "build.gradle"
            ).exists():

                passed.append("build.gradle")

            else:

                missing.append(
                    "pom.xml/build.gradle"
                )

        # -----------------------------------------
        # C++
        # -----------------------------------------

        elif project_type == "cpp":

            cpp_files = list(
                project.rglob("*.cpp")
            )

            if cpp_files:

                passed.append(".cpp files")

            else:

                missing.append(".cpp files")

        # -----------------------------------------
        # Docker
        # -----------------------------------------

        elif project_type == "docker":

            self._check_file(
                project / "Dockerfile",
                "Dockerfile",
                passed,
                missing,
            )

        # -----------------------------------------
        # Unknown
        # -----------------------------------------

        else:

            logger.warning(
                f"Unknown project type: {project_type}"
            )

            missing.append(
                f"Unknown project type: {project_type}"
            )

        # -----------------------------------------
        # Calculate Score
        # -----------------------------------------

        total = len(passed) + len(missing)

        if total == 0:

            score = 0

        else:

            score = round(
                (len(passed) / total) * 100
            )

        logger.info(
            f"Project structure score: {score}%"
        )

        return {
            "score": score,
            "passed": passed,
            "missing": missing,
        }

    # -------------------------------------------------

    def _check_file(
        self,
        file_path: Path,
        display_name: str,
        passed: list,
        missing: list,
    ):

        if file_path.is_file():

            passed.append(display_name)

        else:

            missing.append(display_name)

    # -------------------------------------------------

    def _check_optional_dir(
        self,
        directory: Path,
        display_name: str,
        passed: list,
    ):

        if directory.is_dir():

            passed.append(display_name)

    # -------------------------------------------------

    def _check_python_entry(
        self,
        project: Path,
        passed: list,
        missing: list,
    ):

        priority = [

            project / "main.py",
            project / "app.py",
            project / "run.py",

            project / "src" / "main.py",
            project / "src" / "app.py",
            project / "src" / "run.py",

        ]

        for file in priority:

            if file.is_file():

                passed.append(file.name)

                return

        py_files = list(
            project.rglob("*.py")
        )

        if py_files:

            passed.append(
                "Python source files"
            )

        else:

            missing.append(
                "No Python entry file"
            )