from pathlib import Path

from app.core.logger import logger


class DocumentationChecker:
    """
    Evaluates project documentation quality.

    Documentation requirements are adapted to the detected
    project type so minimal valid projects are not penalized
    for irrelevant documentation requirements.
    """

    def check(
        self,
        project_path: str,
        project_type: str | None = None,
    ) -> dict:

        logger.info(
            "Checking project documentation..."
        )

        project = Path(project_path).resolve()

        if not project.exists():

            return {
                "score": 0,
                "found": [],
                "missing": [
                    "Project directory not found."
                ],
            }

        found = []
        missing = []

        readme = project / "README.md"

        if readme.exists():

            found.append("README.md")

        licenses = [
            "LICENSE",
            "LICENSE.txt",
            "LICENSE.md",
        ]

        for name in licenses:

            if (project / name).is_file():

                found.append(name)

                break

        if project_type == "static_web":

            html_files = list(
                project.rglob("*.html")
            )

            if html_files:

                found.append(
                    f"HTML documentation ({len(html_files)} files)"
                )

            else:

                missing.append(
                    "No HTML files found."
                )

            score = 100 if html_files else 0

            logger.info(
                f"Documentation score: {score}"
            )

            return {
                "score": score,
                "found": found,
                "missing": missing,
            }

        extensions = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".cpp",
            ".c",
        }

        ignored_dirs = {
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            "node_modules",
            "build",
            "dist",
        }

        source_files = []

        for file in project.rglob("*"):

            if not file.is_file():
                continue

            if any(
                part in ignored_dirs
                for part in file.parts
            ):
                continue

            if file.suffix.lower() in extensions:

                source_files.append(file)

        comment_files = 0
        docstring_files = 0

        for file in source_files:

            try:

                content = file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )

            except Exception:

                continue

            if (
                "#" in content
                or "//" in content
                or "/*" in content
            ):

                comment_files += 1

            if file.suffix == ".py":

                if (
                    '"""' in content
                    or "'''" in content
                ):

                    docstring_files += 1

        if readme.exists():

            try:

                text = readme.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )

                if len(text.strip()) < 100:

                    missing.append(
                        "README is too small."
                    )

            except Exception:

                missing.append(
                    "Unable to read README."
                )

        else:

            missing.append("README.md")

        if not any(
            (project / name).is_file()
            for name in licenses
        ):

            missing.append("LICENSE")

        if comment_files > 0:

            found.append(
                f"Comments ({comment_files} files)"
            )

        elif source_files:

            missing.append(
                "No code comments found."
            )

        if docstring_files > 0:

            found.append(
                f"Python docstrings ({docstring_files} files)"
            )

        elif any(
            f.suffix == ".py"
            for f in source_files
        ):

            missing.append(
                "Python docstrings missing."
            )

        if not source_files:

            score = 100

        else:

            total_checks = len(found) + len(missing)

            score = (
                round(
                    (len(found) / total_checks) * 100
                )
                if total_checks
                else 100
            )

        logger.info(
            f"Documentation score: {score}"
        )

        return {
            "score": score,
            "found": found,
            "missing": missing,
        }