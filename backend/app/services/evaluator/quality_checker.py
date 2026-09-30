from pathlib import Path
import re

from app.core.logger import logger


class QualityChecker:
    """
    Analyzes generated source code and detects
    common quality problems.

    Normal application output such as Python print()
    in CLI applications is not treated as a debug issue.
    """

    def check(self, project_path: str) -> dict:

        logger.info("Running quality analysis...")

        project = Path(project_path).resolve()

        if not project.exists():
            return {
                "score": 0,
                "issues": [
                    "Project directory not found."
                ],
            }

        issues = []
        source_files = []

        extensions = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".html",
            ".css",
            ".java",
            ".cpp",
            ".hpp",
            ".c",
            ".h",
        }

        ignored_dirs = {
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            "node_modules",
            "dist",
            "build",
            ".pytest_cache",
        }

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

        if not source_files:
            return {
                "score": 0,
                "issues": [
                    "No source files found."
                ],
            }

        total_files = len(source_files)

        logger.info(
            f"Analyzing {total_files} source files."
        )

        for file in source_files:

            try:
                content = file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )

            except Exception:
                continue

            relative = file.relative_to(project)

            if "TODO" in content:
                issues.append(
                    f"{relative}: TODO found."
                )

            if "FIXME" in content:
                issues.append(
                    f"{relative}: FIXME found."
                )

            if "NotImplementedError" in content:
                issues.append(
                    f"{relative}: NotImplementedError detected."
                )

            if (
                file.suffix == ".py"
                and re.search(
                    r"^\s*pass\s*(?:#.*)?$",
                    content,
                    re.MULTILINE,
                )
            ):
                issues.append(
                    f"{relative}: pass statement detected."
                )

            if "raise Exception" in content:
                issues.append(
                    f"{relative}: Generic Exception used."
                )

            if self._has_debug_print(
                content,
                file.suffix.lower(),
            ):
                issues.append(
                    f"{relative}: Debug output statement found."
                )

            if (
                file.suffix.lower() in {
                    ".js",
                    ".ts",
                    ".jsx",
                    ".tsx",
                }
                and "console.log(" in content
            ):
                issues.append(
                    f"{relative}: console.log() found."
                )

            if "debugger;" in content:
                issues.append(
                    f"{relative}: debugger statement found."
                )

            placeholders = [
                "your code here",
                "placeholder",
                "coming soon",
                "implement me",
                "lorem ipsum",
            ]

            lower = content.lower()

            for placeholder in placeholders:
                if placeholder in lower:
                    issues.append(
                        f"{relative}: Placeholder text detected."
                    )

            empty_python = re.findall(
                r"def\s+\w+\(.*?\):\s+pass",
                content,
                re.DOTALL,
            )

            if empty_python:
                issues.append(
                    f"{relative}: Empty Python function."
                )

            empty_js = re.findall(
                r"function\s+\w+\(.*?\)\s*{\s*}",
                content,
                re.DOTALL,
            )

            if empty_js:
                issues.append(
                    f"{relative}: Empty JavaScript function."
                )

            if content.count("#") > 60:
                issues.append(
                    f"{relative}: Excessive comments."
                )

        max_penalty = 50

        penalty = min(
            len(issues) * 2,
            max_penalty,
        )

        score = max(
            100 - penalty,
            0,
        )

        logger.info(
            f"Quality score: {score}"
        )

        logger.info(
            f"Issues found: {len(issues)}"
        )

        return {
            "score": score,
            "issues": issues,
        }

    @staticmethod
    def _has_debug_print(
        content: str,
        extension: str,
    ) -> bool:
        """
        Detect obvious Python debug output without
        treating normal CLI application print() calls
        as quality problems.
        """

        if extension != ".py":
            return False

        debug_patterns = [
            r"print\(\s*['\"]debug",
            r"print\(\s*['\"]DEBUG",
            r"print\(\s*['\"]trace",
            r"print\(\s*['\"]TRACE",
            r"print\(\s*['\"]testing",
            r"print\(\s*['\"]TESTING",
        ]

        return any(
            re.search(
                pattern,
                content,
            )
            for pattern in debug_patterns
        )
