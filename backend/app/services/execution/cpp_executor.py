import os
import shutil
import subprocess
import time
from pathlib import Path

from app.core.logger import logger


class CPPExecutor:
    """
    Executes C++ projects by compiling discovered .cpp source files
    and running the resulting executable.
    """

    EXECUTION_TIMEOUT = 60
    COMPILE_TIMEOUT = 120

    IGNORE_DIRS = {
        "node_modules",
        "build",
        "dist",
        "out",
        "target",
        ".git",
    }

    def run(self, project_path: str) -> dict:

        project = Path(project_path).resolve()

        if not project.exists():
            return self._result(
                False,
                "",
                f"Project does not exist: {project}",
                -1,
                0,
            )

        compiler = shutil.which("g++")

        if compiler is None:
            return self._result(
                False,
                "",
                "g++ compiler not found in PATH.",
                -1,
                0,
            )

        cpp_files = self._find_cpp_files(project)

        if not cpp_files:
            return self._result(
                False,
                "",
                "No C++ source files found.",
                -1,
                0,
            )

        logger.info("=" * 60)
        logger.info("C++ Executor Started")
        logger.info("=" * 60)

        logger.info("Found %d C++ source files.", len(cpp_files))

        output_dir = project / "build"
        output_dir.mkdir(parents=True, exist_ok=True)

        executable_name = (
            "program.exe"
            if os.name == "nt"
            else "program"
        )

        executable = output_dir / executable_name

        try:

            # -------------------------------------------------
            # Compile all C++ source files
            # -------------------------------------------------

            logger.info("Compiling C++ project.")

            compile_command = [
                compiler,
                *[str(source) for source in cpp_files],
                "-o",
                str(executable),
            ]

            logger.info(
                "Compile command: %s",
                " ".join(compile_command),
            )

            compile_start = time.perf_counter()

            compile_result = subprocess.run(
                compile_command,
                cwd=project,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.COMPILE_TIMEOUT,
            )

            compile_time = round(
                time.perf_counter() - compile_start,
                2,
            )

            if compile_result.stdout:
                logger.info(compile_result.stdout)

            if compile_result.stderr:
                logger.error(compile_result.stderr)

            if compile_result.returncode != 0:

                logger.error(
                    "C++ compilation failed with exit code %s.",
                    compile_result.returncode,
                )

                return self._result(
                    False,
                    compile_result.stdout,
                    compile_result.stderr,
                    compile_result.returncode,
                    compile_time,
                )

            logger.info(
                "Compilation successful in %s seconds.",
                compile_time,
            )

            # -------------------------------------------------
            # Execute compiled program
            # -------------------------------------------------

            logger.info(
                "Running executable: %s",
                executable,
            )

            start = time.perf_counter()

            run_result = subprocess.run(
                [str(executable)],
                cwd=project,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.EXECUTION_TIMEOUT,
            )

            execution_time = round(
                time.perf_counter() - start,
                2,
            )

            if run_result.stdout:
                logger.info(run_result.stdout)

            if run_result.stderr:
                logger.error(run_result.stderr)

            return self._result(
                run_result.returncode == 0,
                run_result.stdout,
                run_result.stderr,
                run_result.returncode,
                execution_time,
            )

        except subprocess.TimeoutExpired:

            logger.error("C++ execution timed out.")

            return self._result(
                False,
                "",
                f"Execution timed out after {self.EXECUTION_TIMEOUT} seconds.",
                -1,
                self.EXECUTION_TIMEOUT,
            )

        except Exception as e:

            logger.exception("C++ execution failed.")

            return self._result(
                False,
                "",
                str(e),
                -1,
                0,
            )

        finally:

            logger.info("=" * 60)
            logger.info("C++ Executor Finished")
            logger.info("=" * 60)

    def _find_cpp_files(self, project: Path) -> list[Path]:

        files = []

        for file in project.rglob("*.cpp"):

            relative_parts = file.relative_to(project).parts[:-1]

            if any(
                part in self.IGNORE_DIRS
                for part in relative_parts
            ):
                continue

            files.append(file)

        return sorted(files)

    def _result(
        self,
        success: bool,
        stdout: str,
        stderr: str,
        return_code: int,
        execution_time: float,
    ) -> dict:

        return {
            "success": success,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": return_code,
            "execution_time": execution_time,
        }