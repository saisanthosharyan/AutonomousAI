import json
import shutil
import subprocess
import time
from pathlib import Path

from app.core.logger import logger


class NodeTestRunner:
    """
    Runs tests for Node.js projects.
    """

    INSTALL_TIMEOUT = 300
    TEST_TIMEOUT = 120

    def run(self, project_path: str):

        project = Path(project_path).resolve()

        package_json = project / "package.json"

        if not package_json.exists():

            return {
                "success": False,
                "stdout": "",
                "stderr": "package.json not found.",
                "return_code": -1,
                "execution_time": 0,
            }

        npm_path = shutil.which("npm")

        if npm_path is None:

            return {
                "success": False,
                "stdout": "",
                "stderr": "npm not found in PATH.",
                "return_code": -1,
                "execution_time": 0,
            }

        # --------------------------------------------------
        # Read package.json
        # --------------------------------------------------

        try:

            with open(package_json, "r", encoding="utf-8") as file:
                package = json.load(file)

        except Exception as e:

            logger.exception("Failed to read package.json.")

            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "execution_time": 0,
            }

        scripts = package.get("scripts", {})

        if "test" not in scripts:

            logger.warning("No test script found.")

            return {
                "success": True,
                "stdout": "No tests defined.",
                "stderr": "",
                "return_code": 0,
                "execution_time": 0,
            }

        # --------------------------------------------------
        # Install Dependencies
        # --------------------------------------------------

        node_modules = project / "node_modules"

        if not node_modules.exists():

            logger.info("Installing Node dependencies...")

            start = time.time()

            try:

                install = subprocess.run(
                    [npm_path, "install"],
                    cwd=project,
                    capture_output=True,
                    text=True,
                    timeout=self.INSTALL_TIMEOUT,
                )

                end = time.time()

                if install.stdout:
                    logger.info(install.stdout)

                if install.stderr:
                    logger.error(install.stderr)

                if install.returncode != 0:

                    return {
                        "success": False,
                        "stdout": install.stdout,
                        "stderr": install.stderr,
                        "return_code": install.returncode,
                        "execution_time": round(end - start, 2),
                    }

                logger.info(
                    f"Dependencies installed successfully in {round(end - start, 2)} seconds."
                )

            except subprocess.TimeoutExpired:

                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "npm install timed out.",
                    "return_code": -1,
                    "execution_time": self.INSTALL_TIMEOUT,
                }

            except Exception as e:

                logger.exception("Dependency installation failed.")

                return {
                    "success": False,
                    "stdout": "",
                    "stderr": str(e),
                    "return_code": -1,
                    "execution_time": 0,
                }

        else:

            logger.info("Dependencies already installed.")

        # --------------------------------------------------
        # Run Tests
        # --------------------------------------------------

        logger.info("Running npm test...")

        start = time.time()

        try:

            test_command = [
                npm_path,
                "test",
            ]

            test_script = str(
                scripts.get("test", "")
            ).lower()

            if "react-scripts test" in test_script:
                test_command.extend(
                    [
                        "--",
                        "--watchAll=false",
                        "--passWithNoTests",
                    ]
                )

            process = subprocess.run(
                test_command,
                cwd=project,
                capture_output=True,
                text=True,
                timeout=self.TEST_TIMEOUT,
            )

            end = time.time()

            execution_time = round(end - start, 2)

            if process.stdout:
                logger.info(process.stdout)

            if process.stderr:
                logger.error(process.stderr)

            logger.info(
                f"Testing completed in {execution_time} seconds."
            )

            return {
                "success": process.returncode == 0,
                "stdout": process.stdout,
                "stderr": process.stderr,
                "return_code": process.returncode,
                "execution_time": execution_time,
            }

        except subprocess.TimeoutExpired:

            logger.error(
                f"npm test timed out after {self.TEST_TIMEOUT} seconds."
            )

            return {
                "success": False,
                "stdout": "",
                "stderr": f"npm test timed out after {self.TEST_TIMEOUT} seconds.",
                "return_code": -1,
                "execution_time": self.TEST_TIMEOUT,
            }

        except Exception as e:

            logger.exception("Test execution failed.")

            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "execution_time": 0,
            }