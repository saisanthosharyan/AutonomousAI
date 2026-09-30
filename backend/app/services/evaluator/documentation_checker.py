from pathlib import Path

from app.core.logger import logger


class DocumentationChecker:
    """
    Evaluates project documentation quality.

    Documentation is only treated as required when the project
    explicitly requests documentation files. Otherwise, missing
    README/LICENSE files do not reduce the score.
    """

    def check(
        self,
        project_path: str,
        project_type: str | None = None,
        requested_files: list[str] | None = None,
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

        requested_files = requested_files or []

        documentation_files = {
            "README.md",
            "LICENSE",
            "LICENSE.txt",
            "LICENSE.md",
        }

        requested_documentation = [
            file
            for file in requested_files
            if Path(file).name in documentation_files
        ]

        if requested_files and not requested_documentation:
            return {
                "score": 100,
                "found": [],
                "missing": [],
            }

        if requested_documentation:
            for requested_file in requested_documentation:
                file_path = project / requested_file

                if file_path.is_file():
                    found.append(requested_file)
                else:
                    missing.append(requested_file)

            total = len(found) + len(missing)

            score = (
                round((len(found) / total) * 100)
                if total
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

        if project_type == "static_web":
            html_files = list(
                project.rglob("*.html")
            )

            if html_files:
                found.append(
                    f"HTML documentation ({len(html_files)} files)"
                )

                score = 100

            else:
                missing.append(
                    "No HTML files found."
                )

                score = 0

            logger.info(
                f"Documentation score: {score}"
            )

            return {
                "score": score,
                "found": found,
                "missing": missing,
            }

        readme = project / "README.md"

        if readme.is_file():
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
            ".pytest_cache",
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

        if readme.is_file():
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