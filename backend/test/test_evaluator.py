from unittest.mock import MagicMock

from app.services.evaluator.evaluator import Evaluator
from app.services.execution.execution_manager import ExecutionResult


def create_evaluator():
    evaluator = Evaluator()

    evaluator.project_analyzer = MagicMock()
    evaluator.project_checker = MagicMock()
    evaluator.quality_checker = MagicMock()
    evaluator.documentation_checker = MagicMock()
    evaluator.execution_manager = MagicMock()

    return evaluator


def configure_successful_evaluation(evaluator):
    evaluator.project_analyzer.detect.return_value = "python"

    evaluator.project_checker.check.return_value = {
        "score": 100,
        "passed": ["requirements.txt", "README.md", "main.py"],
        "missing": [],
    }

    evaluator.execution_manager.run.return_value = ExecutionResult(
        success=True,
        stdout="Hello",
        stderr="",
        return_code=0,
        execution_time=0.1,
        project_type="python",
    )

    evaluator.quality_checker.check.return_value = {
        "score": 100,
        "issues": [],
    }

    evaluator.documentation_checker.check.return_value = {
        "score": 100,
        "found": ["README.md", "Comments"],
        "missing": [],
    }


def test_evaluator_successful_project(tmp_path):
    evaluator = create_evaluator()

    configure_successful_evaluation(evaluator)

    result = evaluator.evaluate(str(tmp_path))

    assert result["project_type"] == "python"
    assert result["overall_score"] == 100
    assert result["recommendation"] == (
        "Excellent. Project is production ready."
    )
    assert result["execution"]["success"] is True


def test_evaluator_failed_execution(tmp_path):
    evaluator = create_evaluator()

    evaluator.project_analyzer.detect.return_value = "python"

    evaluator.project_checker.check.return_value = {
        "score": 100,
        "passed": [],
        "missing": [],
    }

    evaluator.execution_manager.run.return_value = ExecutionResult(
        success=False,
        stdout="",
        stderr="RuntimeError",
        return_code=1,
        execution_time=0.1,
        project_type="python",
    )

    evaluator.quality_checker.check.return_value = {
        "score": 100,
        "issues": [],
    }

    evaluator.documentation_checker.check.return_value = {
        "score": 100,
        "found": [],
        "missing": [],
    }

    result = evaluator.evaluate(str(tmp_path))

    assert result["execution"]["success"] is False
    assert result["execution"]["stderr"] == "RuntimeError"
    assert result["overall_score"] == 75
    assert result["recommendation"] == (
        "Good project. Minor improvements recommended."
    )


def test_evaluator_score_75(tmp_path):
    evaluator = create_evaluator()

    evaluator.project_analyzer.detect.return_value = "python"

    evaluator.project_checker.check.return_value = {
        "score": 100,
        "passed": [],
        "missing": [],
    }

    evaluator.execution_manager.run.return_value = ExecutionResult(
        success=False,
        project_type="python",
    )

    evaluator.quality_checker.check.return_value = {
        "score": 100,
        "issues": [],
    }

    evaluator.documentation_checker.check.return_value = {
        "score": 100,
        "found": [],
        "missing": [],
    }

    result = evaluator.evaluate(str(tmp_path))

    assert result["overall_score"] == 75


def test_evaluator_score_60(tmp_path):
    evaluator = create_evaluator()

    evaluator.project_analyzer.detect.return_value = "python"

    evaluator.project_checker.check.return_value = {
        "score": 40,
        "passed": [],
        "missing": [],
    }

    evaluator.execution_manager.run.return_value = ExecutionResult(
        success=False,
        project_type="python",
    )

    evaluator.quality_checker.check.return_value = {
        "score": 100,
        "issues": [],
    }

    evaluator.documentation_checker.check.return_value = {
        "score": 100,
        "found": [],
        "missing": [],
    }

    result = evaluator.evaluate(str(tmp_path))

    assert result["overall_score"] == 60
    assert result["recommendation"] == (
        "Average project. Needs improvements."
    )


def test_evaluator_major_fixes(tmp_path):
    evaluator = create_evaluator()

    evaluator.project_analyzer.detect.return_value = "python"

    evaluator.project_checker.check.return_value = {
        "score": 0,
        "passed": [],
        "missing": [],
    }

    evaluator.execution_manager.run.return_value = ExecutionResult(
        success=False,
        project_type="python",
    )

    evaluator.quality_checker.check.return_value = {
        "score": 0,
        "issues": ["No source files found."],
    }

    evaluator.documentation_checker.check.return_value = {
        "score": 0,
        "found": [],
        "missing": ["README.md"],
    }

    result = evaluator.evaluate(str(tmp_path))

    assert result["overall_score"] == 0
    assert result["recommendation"] == (
        "Project requires major fixes."
    )


def test_evaluator_calls_all_components(tmp_path):
    evaluator = create_evaluator()

    configure_successful_evaluation(evaluator)

    evaluator.evaluate(str(tmp_path))

    evaluator.project_analyzer.detect.assert_called_once_with(
        str(tmp_path)
    )

    evaluator.project_checker.check.assert_called_once_with(
        str(tmp_path),
        "python",
    )

    evaluator.execution_manager.run.assert_called_once_with(
        str(tmp_path)
    )

    evaluator.quality_checker.check.assert_called_once_with(
        str(tmp_path)
    )

    evaluator.documentation_checker.check.assert_called_once_with(
        str(tmp_path)
    )


def test_evaluator_execution_result_is_converted_to_dict(tmp_path):
    evaluator = create_evaluator()

    configure_successful_evaluation(evaluator)

    result = evaluator.evaluate(str(tmp_path))

    assert isinstance(result["execution"], dict)
    assert result["execution"]["success"] is True
    assert result["execution"]["project_type"] == "python"
    assert result["execution"]["return_code"] == 0


def test_evaluator_detects_node_project(tmp_path):
    evaluator = create_evaluator()

    evaluator.project_analyzer.detect.return_value = "node"

    evaluator.project_checker.check.return_value = {
        "score": 100,
        "passed": [],
        "missing": [],
    }

    evaluator.execution_manager.run.return_value = ExecutionResult(
        success=True,
        project_type="node",
    )

    evaluator.quality_checker.check.return_value = {
        "score": 100,
        "issues": [],
    }

    evaluator.documentation_checker.check.return_value = {
        "score": 100,
        "found": [],
        "missing": [],
    }

    result = evaluator.evaluate(str(tmp_path))

    assert result["project_type"] == "node"
    assert result["execution"]["project_type"] == "node"
    assert result["overall_score"] == 100
