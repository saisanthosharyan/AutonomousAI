from app.core.logger import logger

from app.project.project_analyzer import ProjectAnalyzer

from app.services.evaluator.project_checker import ProjectChecker
from app.services.evaluator.quality_checker import QualityChecker
from app.services.evaluator.documentation_checker import DocumentationChecker
from app.services.execution.execution_manager import ExecutionManager


class Evaluator:
    """
    Evaluates the generated project.

    Checks:

    1. Project Structure
    2. Execution
    3. Code Quality
    4. Documentation

    Produces a final score and recommendation.
    """

    def __init__(self):

        self.project_analyzer = ProjectAnalyzer()

        self.project_checker = ProjectChecker()
        self.quality_checker = QualityChecker()
        self.documentation_checker = DocumentationChecker()

        self.execution_manager = ExecutionManager(
            analyzer=self.project_analyzer
        )

    # --------------------------------------------------
    # Evaluate
    # --------------------------------------------------

    def evaluate(
        self,
        project_path: str,
        execution_result: dict | None = None,
    ) -> dict:

        logger.info("=" * 60)
        logger.info("Starting Project Evaluation")
        logger.info("=" * 60)

        # --------------------------------------------------
        # Detect Project Type
        # --------------------------------------------------

        project_type = self.project_analyzer.detect(
            project_path
        )

        logger.info(
            "Detected project type: %s",
            project_type,
        )

        # --------------------------------------------------
        # Project Structure
        # --------------------------------------------------

        structure = self.project_checker.check(
            project_path,
            project_type,
        )

        # --------------------------------------------------
        # Execution
        # --------------------------------------------------

        execution = execution_result

        if execution is None:

            logger.info(
                "No execution result supplied. "
                "Running project for evaluation."
            )

            execution = self.execution_manager.run(
                project_path
            )

        if hasattr(execution, "to_dict"):
            execution = execution.to_dict()

        execution = execution or {}

        execution_score = (
            100
            if execution.get("success")
            else 0
        )

        # --------------------------------------------------
        # Quality
        # --------------------------------------------------

        quality = self.quality_checker.check(
            project_path
        )

        # --------------------------------------------------
        # Documentation
        # --------------------------------------------------

        documentation = (
            self.documentation_checker.check(
                project_path
            )
        )

        # --------------------------------------------------
        # Overall Score
        # --------------------------------------------------

        overall_score = round(
            (
                structure["score"]
                + execution_score
                + quality["score"]
                + documentation["score"]
            )
            / 4
        )

        # --------------------------------------------------
        # Recommendation
        # --------------------------------------------------

        if overall_score >= 90:

            recommendation = (
                "Excellent. Project is production ready."
            )

        elif overall_score >= 75:

            recommendation = (
                "Good project. Minor improvements recommended."
            )

        elif overall_score >= 60:

            recommendation = (
                "Average project. Needs improvements."
            )

        else:

            recommendation = (
                "Project requires major fixes."
            )

        logger.info(
            "Overall Evaluation Score: %s",
            overall_score,
        )

        logger.info(
            recommendation
        )

        logger.info("=" * 60)
        logger.info("Evaluation Completed")
        logger.info("=" * 60)

        return {
            "overall_score": overall_score,
            "recommendation": recommendation,
            "project_type": project_type,
            "structure": structure,
            "execution": execution,
            "quality": quality,
            "documentation": documentation,
        }