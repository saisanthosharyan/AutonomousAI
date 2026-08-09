import shutil
import subprocess
import time
import queue
import shutil
import subprocess
import threading
from pathlib import Path

from app.core.logger import logger


class DockerExecutor:
    """
    Executes Docker-based projects.
    """

    BUILD_TIMEOUT = 300
    RUN_TIMEOUT = 120

    def run(self, project_path: str) -> dict:

        project = Path(project_path).resolve()

        if not project.exists():
            return self._result(
                False,
                "",
                f"Project directory does not exist: {project}",
                -1,
                0,
            )

        docker = shutil.which("docker")

        # --------------------------------------------------
        # Docker not installed -> Skip instead of Fail
        # --------------------------------------------------

        if docker is None:

            logger.warning(
                "Docker is not installed. Skipping Docker execution."
            )

            return {
                "success": False,
                "skip": True,
                "stdout": "",
                "stderr": "Docker is not installed.",
                "return_code": -1,
                "execution_time": 0,
            }

        dockerfile = project / "Dockerfile"

        if not dockerfile.exists():

            return {
                "success": False,
                "skip": True,
                "stdout": "",
                "stderr": "Dockerfile not found.",
                "return_code": -1,
                "execution_time": 0,
            }

        image_name = f"autodev-{project.name.lower()}"

        logger.info("=" * 60)
        logger.info("Docker Executor Started")
        logger.info("=" * 60)

        # -----------------------------
        # Build Image
        # -----------------------------

        logger.info(f"Building Docker image: {image_name}")

        start = time.time()

        try:

            build = subprocess.run(
                [
                    docker,
                    "build",
                    "-t",
                    image_name,
                    ".",
                ],
                cwd=project,
                capture_output=True,
                text=True,
                timeout=self.BUILD_TIMEOUT,
            )

            if build.returncode != 0:

                return self._result(
                    False,
                    build.stdout,
                    build.stderr,
                    build.returncode,
                    round(time.time() - start, 2),
                )

            logger.info("Docker image built successfully.")

        except subprocess.TimeoutExpired:

            return self._result(
                False,
                "",
                "Docker build timed out.",
                -1,
                self.BUILD_TIMEOUT,
            )

        except Exception as e:

            return self._result(
                False,
                "",
                str(e),
                -1,
                0,
            )

        # -----------------------------
        # Run Container
        # -----------------------------

        logger.info("Running Docker container...")

        start = time.time()

        try:

            run = subprocess.run(
                [
                    docker,
                    "run",
                    "--rm",
                    image_name,
                ],
                cwd=project,
                capture_output=True,
                text=True,
                timeout=self.RUN_TIMEOUT,
            )

            return self._result(
                run.returncode == 0,
                run.stdout,
                run.stderr,
                run.returncode,
                round(time.time() - start, 2),
            )

        except subprocess.TimeoutExpired:

            return self._result(
                False,
                "",
                "Docker execution timed out.",
                -1,
                self.RUN_TIMEOUT,
            )

        except Exception as e:

            return self._result(
                False,
                "",
                str(e),
                -1,
                0,
            )

        finally:

            logger.info("=" * 60)
            logger.info("Docker Executor Finished")
            logger.info("=" * 60)

    def _result(
        self,
        success,
        stdout,
        stderr,
        return_code,
        execution_time,
    ):

        return {
            "success": success,
            "skip": False,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": return_code,
            "execution_time": execution_time,
        }