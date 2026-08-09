from pathlib import Path

from app.core.logger import logger

from app.services.testing.python_test_runner import PythonTestRunner
from app.services.testing.node_test_runner import NodeTestRunner
from app.services.testing.java_test_runner import JavaTestRunner
from app.services.testing.cpp_test_runner import CPPTestRunner


class TestManager:
    """
    Detects the project type and runs the appropriate test runner.
    """

    def __init__(self):
        self.runners = {
            "python": PythonTestRunner(),
            "node": NodeTestRunner(),
            "java": JavaTestRunner(),
            "cpp": CPPTestRunner(),
        }

    # --------------------------------------------------
    # Detect Project Type
    # --------------------------------------------------

    def detect_project_type(self, project_path: str) -> str:

        project = Path(project_path).resolve()

        if not project.exists():
            raise FileNotFoundError(
                f"Project directory does not exist: {project}"
            )

        # Python
        if (
            (project / "requirements.txt").exists()
            or (project / "pyproject.toml").exists()
            or any(project.rglob("*.py"))
        ):
            logger.info("Detected Python project.")
            return "python"

        # Node.js
        if (project / "package.json").exists():
            logger.info("Detected Node.js project.")
            return "node"

        # Java
        if any(project.rglob("*.java")):
            logger.info("Detected Java project.")
            return "java"

        # C++
        if any(project.rglob("*.cpp")):
            logger.info("Detected C++ project.")
            return "cpp"

        logger.warning("Unable to detect project type.")

        return "unknown"

    # --------------------------------------------------
    # Run Tests
    # --------------------------------------------------

    def run(self, project_path: str):

        logger.info("=" * 60)
        logger.info("Test Manager Started")
        logger.info("=" * 60)

        try:

            project_type = self.detect_project_type(project_path)

            logger.info(
                f"Selected test runner: {project_type}"
            )

            runner = self.runners.get(project_type)

            if runner is None:

                logger.warning(
                    f"No supported test runner for '{project_type}' project."
                )

                return {
                    "success": False,
                    "stdout": "",
                    "stderr": (
                        f"No supported test runner for "
                        f"'{project_type}' project."
                    ),
                    "return_code": -1,
                    "execution_time": 0,
                }

            result = runner.run(project_path)

            if result.get("success"):

                logger.info(
                    "Testing completed successfully."
                )

            else:

                logger.warning(
                    "Testing failed."
                )

                logger.error(
                    result.get(
                        "stderr",
                        "No stderr available."
                    )
                )

                if result.get("stdout"):

                    logger.info(
                        result["stdout"]
                    )

            return result

        except Exception as e:

            logger.exception(
                "Test Manager crashed."
            )

            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "execution_time": 0,
            }

        finally:

            logger.info("=" * 60)
            logger.info("Test Manager Finished")
            logger.info("=" * 60)