from app.core.logger import logger
from app.project.project_analyzer import ProjectAnalyzer

from app.services.testing.python_test_runner import PythonTestRunner
from app.services.testing.node_test_runner import NodeTestRunner
from app.services.testing.java_test_runner import JavaTestRunner
from app.services.testing.cpp_test_runner import CPPTestRunner


class TestManager:
    """
    Runs the appropriate test runner based on
    the project type detected by ProjectAnalyzer.
    """

    def __init__(self):

        self.runners = {
            "python": PythonTestRunner(),
            "node": NodeTestRunner(),
            "java": JavaTestRunner(),
            "cpp": CPPTestRunner(),
        }

        self.project_analyzer = ProjectAnalyzer()

    # --------------------------------------------------
    # Run Tests
    # --------------------------------------------------

    def run(self, project_path: str):

        logger.info("=" * 60)
        logger.info("Test Manager Started")
        logger.info("=" * 60)

        try:

            project_type = self.project_analyzer.detect(
                project_path
            )

            logger.info(
                f"Selected test runner: {project_type}"
            )

            runner = self.runners.get(project_type)

            if runner is None:

                logger.warning(
                    f"No supported test runner for "
                    f"'{project_type}' project."
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
                        "No stderr available.",
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