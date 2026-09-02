from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.main import app
from app.api import chat as chat_module


def test_chat_success(monkeypatch, tmp_path):
    project_dir = tmp_path / "generated-project"
    project_dir.mkdir()

    fake_result = {
        "success": True,
        "plan": {
            "goal": "Create a hello world application",
            "steps": ["Create main file", "Run application"],
        },
        "project": {
            "project_path": str(project_dir),
            "project_name": "generated-project",
            "zip_path": str(tmp_path / "generated-project.zip"),
        },
        "execution": {
            "success": True,
            "stdout": "Hello World",
            "stderr": "",
            "return_code": 0,
        },
        "validation": {
            "valid": True,
            "errors": [],
        },
        "tests": {
            "success": True,
            "passed": 1,
            "failed": 0,
        },
        "debug_report": {},
        "retry_stats": {
            "total_attempts": 1,
            "successful": True,
        },
        "review": "The project looks good.",
        "evaluation": {
            "score": 0.9,
        },
        "improved_code": None,
        "metrics": {
            "total_duration": 1.0,
        },
    }

    fake_orchestrator = AsyncMock()
    fake_orchestrator.execute.return_value = fake_result

    monkeypatch.setattr(
        chat_module,
        "AgentOrchestrator",
        lambda: fake_orchestrator,
    )

    monkeypatch.setattr(
        chat_module,
        "get_history",
        lambda session_id: [
            {
                "role": "user",
                "content": "Create a hello world application",
            }
        ],
    )

    added_messages = []

    def fake_add_message(session_id, role, content):
        added_messages.append(
            {
                "session_id": session_id,
                "role": role,
                "content": content,
            }
        )

    monkeypatch.setattr(
        chat_module,
        "add_message",
        fake_add_message,
    )

    client = TestClient(app)

    response = client.post(
        "/chat",
        json={
            "session_id": "test-session",
            "message": "Create a hello world application",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["session_id"] == "test-session"

    assert data["plan"]["goal"] == "Create a hello world application"

    assert data["project"]["project_name"] == "generated-project"
    assert (
        data["project"]["download_url"]
        == "/download/generated-project"
    )

    assert data["execution"]["success"] is True
    assert data["execution"]["stdout"] == "Hello World"

    assert data["validation"]["valid"] is True
    assert data["tests"]["success"] is True
    assert data["review"] == "The project looks good."

    assert data["retry_stats"]["total_attempts"] == 1
    assert data["evaluation"]["score"] == 0.9
    assert data["metrics"]["total_duration"] == 1.0

    fake_orchestrator.execute.assert_awaited_once()

    call_kwargs = fake_orchestrator.execute.await_args.kwargs

    assert call_kwargs["task"] == "Create a hello world application"
    assert call_kwargs["session_id"] == "test-session"

    assert added_messages[0]["role"] == "user"
    assert (
        added_messages[0]["content"]
        == "Create a hello world application"
    )

    assert added_messages[-1]["role"] == "assistant"
    assert (
        added_messages[-1]["content"]
        == "The project looks good."
    )


def test_chat_failed_pipeline(monkeypatch, tmp_path):
    project_dir = tmp_path / "failed-project"
    project_dir.mkdir()

    fake_result = {
        "success": False,
        "plan": {
            "goal": "Create an application",
            "steps": ["Create files", "Run tests"],
        },
        "project": {
            "project_path": str(project_dir),
            "project_name": "failed-project",
            "zip_path": str(tmp_path / "failed-project.zip"),
        },
        "execution": {
            "success": False,
            "stdout": "",
            "stderr": "RuntimeError: application failed",
            "return_code": 1,
        },
        "validation": {
            "valid": False,
            "errors": ["Validation failed"],
        },
        "tests": {
            "success": False,
            "passed": 0,
            "failed": 1,
        },
        "debug_report": {
            "category": "RuntimeError",
        },
        "retry_stats": {
            "total_attempts": 3,
            "successful": False,
        },
        "review": "The project requires fixes.",
        "evaluation": {
            "score": 0.2,
        },
        "improved_code": None,
        "metrics": {
            "total_duration": 3.0,
        },
    }

    fake_orchestrator = AsyncMock()
    fake_orchestrator.execute.return_value = fake_result

    monkeypatch.setattr(
        chat_module,
        "AgentOrchestrator",
        lambda: fake_orchestrator,
    )

    monkeypatch.setattr(
        chat_module,
        "get_history",
        lambda session_id: [],
    )

    monkeypatch.setattr(
        chat_module,
        "add_message",
        lambda *args: None,
    )

    client = TestClient(app)

    response = client.post(
        "/chat",
        json={
            "session_id": "failed-session",
            "message": "Create an application",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is False

    assert data["execution"]["success"] is False
    assert data["validation"]["valid"] is False
    assert data["tests"]["success"] is False

    assert data["retry_stats"]["total_attempts"] == 3
    assert data["retry_stats"]["successful"] is False

    assert data["evaluation"]["score"] == 0.2


def test_chat_orchestrator_failure(monkeypatch):
    fake_orchestrator = AsyncMock()

    fake_orchestrator.execute.side_effect = RuntimeError(
        "Orchestrator failed"
    )

    monkeypatch.setattr(
        chat_module,
        "AgentOrchestrator",
        lambda: fake_orchestrator,
    )

    monkeypatch.setattr(
        chat_module,
        "get_history",
        lambda session_id: [],
    )

    monkeypatch.setattr(
        chat_module,
        "add_message",
        lambda *args: None,
    )

    client = TestClient(app)

    response = client.post(
        "/chat",
        json={
            "session_id": "test-session",
            "message": "Build an application",
        },
    )

    assert response.status_code == 500

    data = response.json()

    assert data["detail"]["success"] is False
    assert data["detail"]["message"] == "Orchestrator failed"


def test_chat_validation():
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={
            "session_id": "",
            "message": "Build an application",
        },
    )

    assert response.status_code == 422

    response = client.post(
        "/chat",
        json={
            "session_id": "test-session",
            "message": "",
        },
    )

    assert response.status_code == 422