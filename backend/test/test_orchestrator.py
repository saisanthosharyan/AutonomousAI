import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.orchestrator import AgentOrchestrator
from app.models.task import Task


def create_task():
    return Task(
        title="Test Project",
        description="A test project",
        project_type="web",
        language="python",
        framework=None,
        database=None,
        authentication=None,
        deployment=None,
        architecture=None,
        testing=None,
        dependencies=[],
        features=[],
        steps=[],
    )


def create_orchestrator():
    with (
        patch(
            "app.agents.orchestrator.PlannerAgent"
        ),
        patch(
            "app.agents.orchestrator.CoderAgent"
        ),
        patch(
            "app.agents.orchestrator.ReviewerAgent"
        ),
        patch(
            "app.agents.orchestrator.ProjectBuilder"
        ),
        patch(
            "app.agents.orchestrator.ProjectValidator"
        ),
        patch(
            "app.agents.orchestrator.RetryManager"
        ),
        patch(
            "app.agents.orchestrator.TestManager"
        ),
        patch(
            "app.agents.orchestrator.Evaluator"
        ),
        patch(
            "app.agents.orchestrator.MemoryManager"
        ),
    ):
        orchestrator = AgentOrchestrator()

    orchestrator.retry_manager.memory = orchestrator.memory

    return orchestrator


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

    orchestrator.reviewer.run = AsyncMock(
        return_value={
            "success": True,
            "summary": "Looks good",
        }
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
    assert result["plan"]["project_type"] == "web"
    assert result["plan"]["language"] == "python"

    assert result["execution"]["success"] is True
    assert result["validation"]["valid"] is True
    assert result["tests"]["success"] is True
    assert result["review"]["success"] is True

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
        return_value=create_task()
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
        return_value=create_task()
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
        return_value=create_task()
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
    assert result["retry_stats"] == {}


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

    assert result["review"]["success"] is False
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

    assert result["evaluation"] == {
        "overall_score": 0,
        "recommendation": "Evaluation failed.",
        "error": "Evaluation error",
    }


def test_orchestrator_calls_shared_memory():
    orchestrator = create_orchestrator()

    assert orchestrator.retry_manager.memory is orchestrator.memory


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
        "improved_code",
        "metrics",
        "evaluation",
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
