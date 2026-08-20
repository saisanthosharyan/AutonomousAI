from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

from app.core.logger import logger


class PythonExecutor:
    """
    Executes generated Python projects with controlled smoke tests.

    Execution strategy:

    1. Validate project.
    2. Install declared dependencies.
    3. Run pytest when tests exist.
    4. Locate a runnable entry point.
    5. Compile all Python files.
    6. Detect the application's execution style.
    7. Run a safe smoke test.
    8. Return structured execution information.

    Important:
    Generated projects may be:

        - CLI applications
        - argparse applications
        - simple scripts
        - web applications
        - GUI applications
        - interactive applications

    The executor must not blindly execute every application
    with zero arguments.

    Important pytest isolation rule:

    Generated projects are executed independently from the
    AutoDev-AI backend.

    This prevents imports such as:

        from app import add

    inside a generated project from accidentally importing:

        backend/app/

    instead of:

        generated_project/app.py
    """

    EXECUTION_TIMEOUT = 30
    INSTALL_TIMEOUT = 120

    ENTRY_FILES = (
        "main.py",
        "app.py",
        "run.py",
        "cli.py",
        "server.py",
        "manage.py",
    )

    IGNORED_DIRS = {
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".git",
        "node_modules",
        "tests",
        "dist",
        "build",
        ".mypy_cache",
        ".idea",
        ".vscode",
    }

    IGNORED_FILES = {
        "__init__.py",
        "setup.py",
        "conftest.py",
    }

    _MAIN_GUARD_MARKERS = (
        '__name__ == "__main__"',
        "__name__ == '__main__'",
    )

    # ==========================================================
    # MAIN
    # ==========================================================

    def run(
        self,
        project_path: str,
    ) -> dict:
        """
        Execute a generated Python project.

        If the project contains tests, pytest is executed first.

        The generated project's directory is explicitly isolated
        from the AutoDev-AI backend so imports resolve correctly.
        """

        start_time = time.perf_counter()

        project = Path(project_path).resolve()

        if not project.exists():
            return self._error(
                f"Project does not exist: {project}"
            )

        if not project.is_dir():
            return self._error(
                f"Project is not a directory: {project}"
            )

        logger.info(
            f"PythonExecutor running: {project}"
        )

        try:

            # --------------------------------------------------
            # Dependencies
            # --------------------------------------------------

            dependency_result = self._install_dependencies(
                project
            )

            if not dependency_result["success"]:
                return self._finish(
                    dependency_result,
                    start_time,
                )

            # --------------------------------------------------
            # Tests
            # --------------------------------------------------

            tests_dir = project / "tests"

            if tests_dir.exists() and tests_dir.is_dir():

                logger.info(
                    "Tests directory detected."
                )

                result = self._run_pytest(
                    project
                )

                return self._finish(
                    result,
                    start_time,
                )

            # --------------------------------------------------
            # Entry point
            # --------------------------------------------------

            entry = self.find_entry(project)

            if entry is None:

                return self._finish(
                    self._error(
                        "No runnable Python entry file found."
                    ),
                    start_time,
                )

            logger.info(
                "Python entry point: %s",
                entry.relative_to(project),
            )

            # --------------------------------------------------
            # Syntax validation
            # --------------------------------------------------

            syntax_result = self._compile_project(
                project
            )

            if not syntax_result["success"]:

                return self._finish(
                    syntax_result,
                    start_time,
                )

            # --------------------------------------------------
            # Read source
            # --------------------------------------------------

            try:

                content = entry.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )

            except Exception as exc:

                return self._finish(
                    self._error(
                        f"Unable to read entry point: {exc}"
                    ),
                    start_time,
                )

            # --------------------------------------------------
            # Detect application type
            # --------------------------------------------------

            execution_mode = self._detect_execution_mode(
                content
            )

            logger.info(
                "Detected Python execution mode: %s",
                execution_mode,
            )

            # --------------------------------------------------
            # Interactive applications
            # --------------------------------------------------

            if execution_mode == "interactive":

                logger.warning(
                    "Interactive application detected; "
                    "execution skipped."
                )

                return self._finish(
                    {
                        "success": True,
                        "stdout": "",
                        "stderr": (
                            "Interactive application detected; "
                            "execution skipped."
                        ),
                        "return_code": 0,
                    },
                    start_time,
                )

            # --------------------------------------------------
            # GUI / web applications
            # --------------------------------------------------

            if execution_mode in {
                "web",
                "gui",
            }:

                logger.warning(
                    "%s application detected; "
                    "startup execution skipped.",
                    execution_mode.capitalize(),
                )

                return self._finish(
                    {
                        "success": True,
                        "stdout": "",
                        "stderr": (
                            f"{execution_mode.capitalize()} "
                            "application detected; "
                            "startup execution skipped."
                        ),
                        "return_code": 0,
                    },
                    start_time,
                )

            # --------------------------------------------------
            # Determine smoke-test command
            # --------------------------------------------------

            command = self._build_execution_command(
                entry,
                content,
            )

            logger.info(
                "Execution command: %s",
                " ".join(command),
            )

            # --------------------------------------------------
            # Execute
            # --------------------------------------------------

            process = subprocess.run(
                command,
                cwd=project,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.EXECUTION_TIMEOUT,
                stdin=subprocess.DEVNULL,
                env=self._build_environment(project),
            )

            return self._finish(
                {
                    "success": process.returncode == 0,
                    "stdout": process.stdout or "",
                    "stderr": process.stderr or "",
                    "return_code": process.returncode,
                },
                start_time,
            )

        except subprocess.TimeoutExpired as exc:

            logger.error(
                "Python execution timed out."
            )

            return self._finish(
                {
                    "success": False,
                    "stdout": self._timeout_output(
                        exc.stdout
                    ),
                    "stderr": (
                        f"Execution timed out after "
                        f"{self.EXECUTION_TIMEOUT} seconds."
                    ),
                    "return_code": -1,
                },
                start_time,
            )

        except Exception as exc:

            logger.exception(
                "PythonExecutor failed."
            )

            return self._finish(
                self._error(str(exc)),
                start_time,
            )

    # ==========================================================
    # ENVIRONMENT
    # ==========================================================

    def _build_environment(
        self,
        project: Path,
    ) -> dict:
        """
        Build an isolated environment for the generated project.

        The generated project directory is placed FIRST in
        PYTHONPATH.

        This is critical for projects containing:

            app.py

        and tests containing:

            from app import ...

        Without this isolation, the AutoDev-AI backend's own
        `app` package can be imported accidentally.
        """

        env = os.environ.copy()

        project_string = str(project)

        existing_pythonpath = env.get(
            "PYTHONPATH",
            "",
        )

        if existing_pythonpath:

            env["PYTHONPATH"] = (
                project_string
                + os.pathsep
                + existing_pythonpath
            )

        else:

            env["PYTHONPATH"] = project_string

        return env

    # ==========================================================
    # DEPENDENCIES
    # ==========================================================

    def _install_dependencies(
        self,
        project: Path,
    ) -> dict:

        requirements = project / "requirements.txt"

        if not requirements.exists():

            logger.info(
                "No requirements.txt found; "
                "dependency installation skipped."
            )

            return {
                "success": True,
                "stdout": "",
                "stderr": "",
                "return_code": 0,
            }

        if requirements.stat().st_size == 0:

            logger.info(
                "requirements.txt is empty; "
                "dependency installation skipped."
            )

            return {
                "success": True,
                "stdout": "",
                "stderr": "",
                "return_code": 0,
            }

        logger.info(
            "Installing project dependencies..."
        )

        try:

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "-r",
                    str(requirements),
                ],
                cwd=project,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.INSTALL_TIMEOUT,
                env=self._build_environment(project),
            )

            if process.returncode != 0:

                return {
                    "success": False,
                    "stdout": process.stdout or "",
                    "stderr": (
                        process.stderr
                        or "Dependency installation failed."
                    ),
                    "return_code": process.returncode,
                }

            return {
                "success": True,
                "stdout": process.stdout or "",
                "stderr": process.stderr or "",
                "return_code": 0,
            }

        except subprocess.TimeoutExpired:

            return {
                "success": False,
                "stdout": "",
                "stderr": (
                    "Dependency installation timed out "
                    f"after {self.INSTALL_TIMEOUT} seconds."
                ),
                "return_code": -1,
            }

        except Exception as exc:

            return {
                "success": False,
                "stdout": "",
                "stderr": str(exc),
                "return_code": -1,
            }

    # ==========================================================
    # PYTEST
    # ==========================================================

    def _run_pytest(
        self,
        project: Path,
    ) -> dict:
        """
        Run tests inside the generated project.

        IMPORTANT:

        pytest is executed with:

            cwd=project

        and:

            PYTHONPATH=<generated project>

        This prevents the AutoDev-AI backend's own `app` package
        from being imported by generated tests.
        """

        logger.info(
            "Running pytest in generated project: %s",
            project,
        )

        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
        ]

        logger.info(
            "Pytest command: %s",
            " ".join(command),
        )

        try:

            process = subprocess.run(
                command,
                cwd=project,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.EXECUTION_TIMEOUT,
                stdin=subprocess.DEVNULL,
                env=self._build_environment(project),
            )

            # --------------------------------------------------
            # pytest return code 5 means no tests collected.
            # That is not considered a failure for generated
            # projects that simply don't contain runnable tests.
            # --------------------------------------------------

            if process.returncode == 5:

                return {
                    "success": True,
                    "stdout": (
                        process.stdout
                        or "No tests collected."
                    ),
                    "stderr": process.stderr or "",
                    "return_code": 0,
                }

            return {
                "success": process.returncode == 0,
                "stdout": process.stdout or "",
                "stderr": process.stderr or "",
                "return_code": process.returncode,
            }

        except subprocess.TimeoutExpired:

            return {
                "success": False,
                "stdout": "",
                "stderr": (
                    "pytest timed out after "
                    f"{self.EXECUTION_TIMEOUT} seconds."
                ),
                "return_code": -1,
            }

        except Exception as exc:

            return {
                "success": False,
                "stdout": "",
                "stderr": str(exc),
                "return_code": -1,
            }

    # ==========================================================
    # PYTHON SYNTAX VALIDATION
    # ==========================================================

    def _compile_project(
        self,
        project: Path,
    ) -> dict:

        logger.info(
            "Validating Python syntax..."
        )

        python_files = list(
            project.rglob("*.py")
        )

        python_files = [
            file
            for file in python_files
            if not self._is_ignored(
                file,
                project,
            )
        ]

        if not python_files:

            return self._error(
                "No Python source files found."
            )

        for file in python_files:

            try:

                process = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "py_compile",
                        str(file),
                    ],
                    cwd=project,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                    env=self._build_environment(project),
                )

                if process.returncode != 0:

                    return {
                        "success": False,
                        "stdout": process.stdout or "",
                        "stderr": (
                            process.stderr
                            or f"Syntax error in {file.name}"
                        ),
                        "return_code": process.returncode,
                    }

            except subprocess.TimeoutExpired:

                return self._error(
                    f"Syntax validation timed out: {file}"
                )

        return {
            "success": True,
            "stdout": (
                "Python syntax validation passed."
            ),
            "stderr": "",
            "return_code": 0,
        }

    # ==========================================================
    # ENTRY POINT
    # ==========================================================

    def find_entry(
        self,
        project: Path,
    ) -> Path | None:
        """
        Locate the best runnable Python entry point.

        Priority:

        1. Well-known entry filenames.
        2. Files containing __main__ guard.
        3. Shallowest Python source file.
        """

        for filename in self.ENTRY_FILES:

            candidate = project / filename

            if candidate.exists():

                return candidate

        candidates = []

        for file in project.rglob("*.py"):

            if self._is_ignored(
                file,
                project,
            ):
                continue

            if file.name in self.IGNORED_FILES:
                continue

            candidates.append(file)

        if not candidates:
            return None

        candidates.sort(
            key=lambda p: (
                len(
                    p.relative_to(project).parts
                ),
                str(p).lower(),
            )
        )

        guarded = [
            file
            for file in candidates
            if self._has_main_guard(file)
        ]

        if guarded:
            return guarded[0]

        return candidates[0]

    # ==========================================================
    # MAIN GUARD
    # ==========================================================

    def _has_main_guard(
        self,
        file: Path,
    ) -> bool:

        try:

            text = file.read_text(
                encoding="utf-8",
                errors="ignore",
            )

        except Exception:

            return False

        return any(
            marker in text
            for marker in self._MAIN_GUARD_MARKERS
        )

    # ==========================================================
    # EXECUTION MODE DETECTION
    # ==========================================================

    def _detect_execution_mode(
        self,
        content: str,
    ) -> str:
        """
        Detect how the generated Python program expects to run.

        Returns:

            cli
            interactive
            web
            gui
        """

        lowered = content.lower()

        # ------------------------------------------------------
        # GUI frameworks
        # ------------------------------------------------------

        if any(
            marker in lowered
            for marker in (
                "import tkinter",
                "from tkinter",
                "import pygame",
                "from pygame",
                "import pyqt",
                "from pyqt",
                "from pyqt5",
                "from pyqt6",
                "import pyqt5",
                "import pyqt6",
            )
        ):

            return "gui"

        # ------------------------------------------------------
        # Web frameworks
        # ------------------------------------------------------

        if any(
            marker in lowered
            for marker in (
                "from fastapi",
                "import fastapi",
                "from flask",
                "import flask",
                "from django",
                "import django",
                "import streamlit",
                "from streamlit",
                "import gradio",
                "from gradio",
            )
        ):

            return "web"

        # ------------------------------------------------------
        # Interactive input
        # ------------------------------------------------------

        if self._contains_input_call(content):

            if self._contains_cli_arguments(content):

                return "cli"

            return "interactive"

        return "cli"

    # ==========================================================
    # CLI DETECTION
    # ==========================================================

    def _contains_cli_arguments(
        self,
        content: str,
    ) -> bool:

        patterns = (
            "sys.argv",
            "argparse",
            "ArgumentParser",
            "click.command",
            "click.option",
            "typer.",
        )

        return any(
            pattern in content
            for pattern in patterns
        )

    # ==========================================================
    # INPUT DETECTION
    # ==========================================================

    def _contains_input_call(
        self,
        content: str,
    ) -> bool:

        return bool(
            re.search(
                r"\binput\s*\(",
                content,
            )
        )

    # ==========================================================
    # BUILD EXECUTION COMMAND
    # ==========================================================

    def _build_execution_command(
        self,
        entry: Path,
        content: str,
    ) -> list[str]:
        """
        Build a safe smoke-test command.

        argparse:

            python app.py --help

        sys.argv:

            python app.py <inferred arguments>

        normal script:

            python app.py
        """

        command = [
            sys.executable,
            str(entry),
        ]

        lowered = content.lower()

        # ------------------------------------------------------
        # argparse
        # ------------------------------------------------------

        if (
            "argparse" in lowered
            and "argumentparser" in lowered
        ):

            command.append("--help")

            return command

        # ------------------------------------------------------
        # Click / Typer
        # ------------------------------------------------------

        if (
            "click.command" in lowered
            or "typer." in lowered
        ):

            command.append("--help")

            return command

        # ------------------------------------------------------
        # sys.argv based CLI
        # ------------------------------------------------------

        if "sys.argv" in lowered:

            smoke_args = self._infer_sys_argv_arguments(
                content
            )

            command.extend(
                smoke_args
            )

            return command

        # ------------------------------------------------------
        # Interactive input
        # ------------------------------------------------------

        if self._contains_input_call(content):

            return command

        return command

    # ==========================================================
    # INFER SYS.ARGV ARGUMENTS
    # ==========================================================

    def _infer_sys_argv_arguments(
        self,
        content: str,
    ) -> list[str]:
        """
        Infer safe smoke-test arguments for common generated
        command-line applications.

        Example:

            operation = sys.argv[1]
            num1 = float(sys.argv[2])
            num2 = float(sys.argv[3])

        becomes:

            add 2 3
        """

        lowered = content.lower()

        # ------------------------------------------------------
        # Common calculator pattern
        # ------------------------------------------------------

        calculator_operations = (
            "add",
            "subtract",
            "multiply",
            "divide",
        )

        if all(
            operation in lowered
            for operation in calculator_operations
        ):

            return [
                "add",
                "2",
                "3",
            ]

        # ------------------------------------------------------
        # Common operation pattern
        # ------------------------------------------------------

        if (
            "operation" in lowered
            and "sys.argv[1]" in lowered
        ):

            return [
                "add",
                "2",
                "3",
            ]

        # ------------------------------------------------------
        # Generic numeric CLI
        # ------------------------------------------------------

        argv_indexes = re.findall(
            r"sys\.argv\[(\d+)\]",
            content,
        )

        indexes = sorted(
            {
                int(index)
                for index in argv_indexes
            }
        )

        if indexes:

            highest_index = max(indexes)

            if highest_index >= 3:

                return [
                    "add",
                    "2",
                    "3",
                ]

            if highest_index == 2:

                return [
                    "2",
                    "3",
                ]

            if highest_index == 1:

                return [
                    "2",
                ]

        # ------------------------------------------------------
        # Unknown CLI
        # ------------------------------------------------------

        return []

    # ==========================================================
    # IGNORED FILE
    # ==========================================================

    def _is_ignored(
        self,
        file: Path,
        project: Path,
    ) -> bool:

        relative = file.relative_to(
            project
        )

        return any(
            part in self.IGNORED_DIRS
            for part in relative.parts
        )

    # ==========================================================
    # FINISH
    # ==========================================================

    def _finish(
        self,
        result: dict,
        start_time: float,
    ) -> dict:

        result.setdefault(
            "success",
            False,
        )

        result.setdefault(
            "stdout",
            "",
        )

        result.setdefault(
            "stderr",
            "",
        )

        result.setdefault(
            "return_code",
            -1,
        )

        result["execution_time"] = round(
            time.perf_counter() - start_time,
            2,
        )

        return result

    # ==========================================================
    # ERROR
    # ==========================================================

    def _error(
        self,
        message: str,
    ) -> dict:

        return {
            "success": False,
            "stdout": "",
            "stderr": message,
            "return_code": -1,
            "execution_time": 0,
        }

    # ==========================================================
    # TIMEOUT OUTPUT
    # ==========================================================

    def _timeout_output(
        self,
        output,
    ) -> str:

        if output is None:
            return ""

        if isinstance(
            output,
            bytes,
        ):

            return output.decode(
                errors="replace"
            )

        return str(output)