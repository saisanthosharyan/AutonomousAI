import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.orchestrator import AgentOrchestrator
from app.models.task import Task


def create_orchestrator():
    with (
        patch(
            "app.agents.orchestrator.PlannerAgent"
        ) as planner,
        patch(
            "app.agents.orchestrator.CoderAgent"
        ) as coder,
        patch(
            "app.agents.orchestrator.ReviewerAgent"
        ) as reviewer,
        patch(
            "app.agents.orchestrator.ProjectBuilder"
        ) as builder,
        patch(
            "app.agents.orchestrator.ProjectValidator"
        ) as validator,
        patch(
            "app.agents.orchestrator.RetryManager"
        ) as retry_manager,
        patch(
            "app.agents.orchestrator.TestManager"
        ) as tester,
        patch(
            "app.agents.orchestrator.Evaluator"
        ) as evaluator,
        patch(
            "app.agents.orchestrator.MemoryManager"
        ) as memory,
    ):
        orchestrator = AgentOrchestrator()

    # Make the mock RetryManager expose the same shared memory
    # instance that AgentOrchestrator created.
    orchestrator.retry_manager.memory = orchestrator.memory

    return orchestrator


def create_task(
    title="Test Project",
    description="A test project",
):
    return Task(
        title=title,
        description=description,
        project_type="web",
        language="python",
    )


def configure_success(orchestrator, tmp_path):
    project_path = str(tmp_path / "project")
    zip_path = str(tmp_path / "project.zip")

    orchestrator.planner.run = AsyncMock(
        return_value=create_task()
    )

    orchestrator.coder.run = AsyncMock(
        return_value="print('hello')"
    )

    orchestrator.builder.build.return_value = {
        "project_path": project_path,
        "zip_path": zip_path,
    }

    orchestrator.retry_manager.execute_with_retry = AsyncMock(
        return_value=(
            {
                "success": True,
                "stdout": "Hello",
                "stderr": "",
                "return_code": 0,
            },
            {
                "project_path": project_path,
                "zip_path": zip_path,
            },
            "print('hello')",
            {
                "success": True,
            },
            {
                "attempts": 1,
                "retries": 0,
            },
        )
    )

    orchestrator.validator.validate.return_value = {
        "valid": True,
        "errors": [],
        "warnings": [],
    }

    orchestrator.tester.run.return_value = {
        "success": True,
        "stdout": "All tests passed",
        "stderr": "",
        "return_code": 0,
    }

    # ReviewerAgent.run() returns a review string.
    orchestrator.reviewer.run = AsyncMock(
        return_value="""
## Overall Summary

The generated project is functional and well structured.

## Strengths

- Clear implementation
- Working source code
- Basic test coverage

## Problems Found

No significant problems were found.

## Final Score

9/10
"""
    )

    orchestrator.evaluator.evaluate.return_value = {
        "overall_score": 95,
        "recommendation": "Excellent",
    }


@patch(
    "app.agents.orchestrator.SessionLocal"
)
@patch(
    "app.agents.orchestrator.create_project"
)
def test_orchestrator_success(
    create_project,
    session_local,
    tmp_path,
):
    orchestrator = create_orchestrator()

    configure_success(
        orchestrator,
        tmp_path,
    )

    db = MagicMock()
    session_local.return_value = db

    result = asyncio.run(
        orchestrator.execute(
            task="Create a test project",
            session_id="test-session",
        )
    )

    assert result["success"] is True
    assert result["plan"]["title"] == "Test Project"
    assert result["execution"]["success"] is True
    assert result["validation"]["valid"] is True
    assert result["tests"]["success"] is True

    # ReviewerAgent returns a string.
    assert isinstance(result["review"], str)
    assert "Overall Summary" in result["review"]
    assert "Final Score" in result["review"]
    assert "9/10" in result["review"]

    assert result["evaluation"]["overall_score"] == 95
    assert result["improved_code"] == "print('hello')"

    create_project.assert_called_once()


def test_orchestrator_rejects_empty_task():
    orchestrator = create_orchestrator()

    with pytest.raises(
        ValueError,
        match="Task cannot be empty",
    ):
        asyncio.run(
            orchestrator.execute("")
        )


def test_orchestrator_rejects_whitespace_task():
    orchestrator = create_orchestrator()

    with pytest.raises(
        ValueError,
        match="Task cannot be empty",
    ):
        asyncio.run(
            orchestrator.execute("   ")
        )


def test_planner_failure():
    orchestrator = create_orchestrator()

    orchestrator.planner.run = AsyncMock(
        side_effect=RuntimeError(
            "Planner failed"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Planner failed",
    ):
        asyncio.run(
            orchestrator.execute(
                "Create project"
            )
        )


def test_planner_returns_none():
    orchestrator = create_orchestrator()

    orchestrator.planner.run = AsyncMock(
        return_value=None
    )

    with pytest.raises(
        RuntimeError,
        match="Planner failed to generate a task",
    ):
        asyncio.run(
            orchestrator.execute(
                "Create project"
            )
        )


def test_coder_failure():
    orchestrator = create_orchestrator()

    orchestrator.planner.run = AsyncMock(
        return_value=create_task(
            description="Test"
        )
    )

    orchestrator.coder.run = AsyncMock(
        side_effect=RuntimeError(
            "Coder failed"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Coder failed",
    ):
        asyncio.run(
            orchestrator.execute(
                "Create project"
            )
        )


def test_coder_returns_empty_code():
    orchestrator = create_orchestrator()

    orchestrator.planner.run = AsyncMock(
        return_value=create_task(
            description="Test"
        )
    )

    orchestrator.coder.run = AsyncMock(
        return_value=""
    )

    with pytest.raises(
        RuntimeError,
        match="Coder failed to generate source code",
    ):
        asyncio.run(
            orchestrator.execute(
                "Create project"
            )
        )


def test_builder_failure():
    orchestrator = create_orchestrator()

    orchestrator.planner.run = AsyncMock(
        return_value=create_task(
            description="Test"
        )
    )

    orchestrator.coder.run = AsyncMock(
        return_value="print('hello')"
    )

    orchestrator.builder.build.side_effect = RuntimeError(
        "Builder failed"
    )

    with pytest.raises(
        RuntimeError,
        match="Builder failed",
    ):
        asyncio.run(
            orchestrator.execute(
                "Create project"
            )
        )


def test_retry_manager_failure(tmp_path):
    orchestrator = create_orchestrator()

    configure_success(
        orchestrator,
        tmp_path,
    )

    orchestrator.retry_manager.execute_with_retry = AsyncMock(
        side_effect=RuntimeError(
            "Execution failed"
        )
    )

    with patch(
        "app.agents.orchestrator.SessionLocal"
    ) as session_local, patch(
        "app.agents.orchestrator.create_project"
    ):
        session_local.return_value = MagicMock()

        result = asyncio.run(
            orchestrator.execute(
                "Create project"
            )
        )

    assert result["execution"]["success"] is False
    assert result["debug_report"]["success"] is False
    assert result["success"] is False


def test_validation_failure_does_not_crash_pipeline(
    tmp_path,
):
    orchestrator = create_orchestrator()

    configure_success(
        orchestrator,
        tmp_path,
    )

    orchestrator.validator.validate.side_effect = RuntimeError(
        "Validation error"
    )

    with patch(
        "app.agents.orchestrator.SessionLocal"
    ) as session_local, patch(
        "app.agents.orchestrator.create_project"
    ):
        session_local.return_value = MagicMock()

        result = asyncio.run(
            orchestrator.execute(
                "Create project"
            )
        )

    assert result["validation"]["valid"] is False
    assert "Validation error" in result["validation"]["errors"]
    assert result["success"] is False


def test_testing_failure_does_not_crash_pipeline(
    tmp_path,
):
    orchestrator = create_orchestrator()

    configure_success(
        orchestrator,
        tmp_path,
    )

    orchestrator.tester.run.side_effect = RuntimeError(
        "Testing error"
    )

    with patch(
        "app.agents.orchestrator.SessionLocal"
    ) as session_local, patch(
        "app.agents.orchestrator.create_project"
    ):
        session_local.return_value = MagicMock()

        result = asyncio.run(
            orchestrator.execute(
                "Create project"
            )
        )

    assert result["tests"]["success"] is False
    assert "Testing error" in result["tests"]["stderr"]
    assert result["success"] is False


def test_review_failure_does_not_crash_pipeline(
    tmp_path,
):
    orchestrator = create_orchestrator()

    configure_success(
        orchestrator,
        tmp_path,
    )

    orchestrator.reviewer.run = AsyncMock(
        side_effect=RuntimeError(
            "Review error"
        )
    )

    with patch(
        "app.agents.orchestrator.SessionLocal"
    ) as session_local, patch(
        "app.agents.orchestrator.create_project"
    ):
        session_local.return_value = MagicMock()

        result = asyncio.run(
            orchestrator.execute(
                "Create project"
            )
        )

    assert isinstance(
        result["review"],
        str,
    )

    assert result["review"] == (
        "Reviewer Agent failed: Review error"
    )

    assert result["success"] is False


def test_evaluation_failure_does_not_crash_pipeline(
    tmp_path,
):
    orchestrator = create_orchestrator()

    configure_success(
        orchestrator,
        tmp_path,
    )

    orchestrator.evaluator.evaluate.side_effect = RuntimeError(
        "Evaluation error"
    )

    with patch(
        "app.agents.orchestrator.SessionLocal"
    ) as session_local, patch(
        "app.agents.orchestrator.create_project"
    ):
        session_local.return_value = MagicMock()

        result = asyncio.run(
            orchestrator.execute(
                "Create project"
            )
        )

    # The current orchestrator catches evaluator failures and
    # returns a structured evaluation error instead of crashing.
    assert result["evaluation"]["overall_score"] == 0
    assert result["evaluation"]["recommendation"] == (
        "Evaluation failed."
    )
    assert result["evaluation"]["error"] == (
        "Evaluation error"
    )


def test_orchestrator_calls_shared_memory():
    orchestrator = create_orchestrator()

    assert (
        orchestrator.retry_manager.memory
        is orchestrator.memory
    )


def test_final_result_contains_expected_sections(
    tmp_path,
):
    orchestrator = create_orchestrator()

    configure_success(
        orchestrator,
        tmp_path,
    )

    with patch(
        "app.agents.orchestrator.SessionLocal"
    ) as session_local, patch(
        "app.agents.orchestrator.create_project"
    ):
        session_local.return_value = MagicMock()

        result = asyncio.run(
            orchestrator.execute(
                "Create project"
            )
        )

    expected = {
        "success",
        "plan",
        "project",
        "execution",
        "validation",
        "tests",
        "debug_report",
        "retry_stats",
        "review",
        "evaluation",
        "improved_code",
        "metrics",
    }

    assert expected.issubset(
        result.keys()
    )


def test_pipeline_metrics_are_recorded(
    tmp_path,
):
    orchestrator = create_orchestrator()

    configure_success(
        orchestrator,
        tmp_path,
    )

    with patch(
        "app.agents.orchestrator.SessionLocal"
    ) as session_local, patch(
        "app.agents.orchestrator.create_project"
    ):
        session_local.return_value = MagicMock()

        result = asyncio.run(
            orchestrator.execute(
                "Create project"
            )
        )

    metrics = result["metrics"]

    assert metrics["pipeline_time"] >= 0

    assert "planner" in metrics["stage_times"]
    assert "coder" in metrics["stage_times"]
    assert "builder" in metrics["stage_times"]
    assert "execution" in metrics["stage_times"]
    assert "validation" in metrics["stage_times"]
    assert "testing" in metrics["stage_times"]
    assert "review" in metrics["stage_times"]
    assert "evaluation" in metrics["stage_times"]
    assert "save" in metrics["stage_times"]