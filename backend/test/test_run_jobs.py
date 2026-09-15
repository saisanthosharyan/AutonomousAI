import asyncio
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database.database import Base, SessionLocal, engine
from app.database.models import Run
from app.main import app
from app.services.run.job_manager import RunJobManager
from app.services.auth.service import create_access_token


TEST_TOKEN = create_access_token(
    user_id=1,
    username="santhosh_test",
)

AUTH_HEADERS = {
    "Authorization": f"Bearer {TEST_TOKEN}",
}


Base.metadata.create_all(bind=engine)


def get_run_from_db(run_id):
    db = SessionLocal()

    try:
        return (
            db.query(Run)
            .filter(Run.id == run_id)
            .first()
        )
    finally:
        db.close()


def get_runs_for_session(session_id):
    db = SessionLocal()

    try:
        return (
            db.query(Run)
            .filter(Run.session_id == session_id)
            .all()
        )
    finally:
        db.close()


def delete_run(run_id):
    db = SessionLocal()

    try:
        run = (
            db.query(Run)
            .filter(Run.id == run_id)
            .first()
        )

        if run is not None:
            db.delete(run)
            db.commit()

    finally:
        db.close()


def test_create_background_run(monkeypatch):
    session_id = f"job-session-{uuid.uuid4()}"
    captured = {}

    def fake_start(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "app.api.runs.RunJobManager.start",
        fake_start,
    )

    client = TestClient(app)

    response = client.post(
        "/runs",
        headers=AUTH_HEADERS,
        json={
            "session_id": session_id,
            "message": "Create a hello world application",
        },
    )

    assert response.status_code == 202

    data = response.json()

    assert data["success"] is True
    assert data["session_id"] == session_id
    assert data["run_id"]
    assert data["status"] == "queued"
    assert data["message"] == "Run queued successfully."

    run_id = data["run_id"]

    try:
        run = get_run_from_db(run_id)

        assert run is not None
        assert run.id == run_id
        assert run.session_id == session_id
        assert run.prompt == "Create a hello world application"
        assert run.status == "queued"
        assert run.progress == 0

        assert captured["run_id"] == run_id
        assert captured["session_id"] == session_id
        assert captured["prompt"] == "Create a hello world application"
        assert captured["provider"] is None
        assert captured["api_key"] is None
        assert captured["model"] is None

    finally:
        delete_run(run_id)


def test_create_background_run_passes_llm_options(
    monkeypatch,
):
    session_id = f"llm-job-{uuid.uuid4()}"
    captured = {}

    def fake_start(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "app.api.runs.RunJobManager.start",
        fake_start,
    )

    client = TestClient(app)

    response = client.post(
        "/runs",
        headers=AUTH_HEADERS,
        json={
            "session_id": session_id,
            "message": "Build a Python API",
            "provider": "gemini",
            "api_key": "test-secret-key",
            "model": "gemini-test-model",
        },
    )

    assert response.status_code == 202

    data = response.json()
    run_id = data["run_id"]

    try:
        assert captured["provider"] == "gemini"
        assert captured["api_key"] == "test-secret-key"
        assert captured["model"] == "gemini-test-model"

        run = get_run_from_db(run_id)

        assert run is not None

        assert "test-secret-key" not in (
            run.prompt or ""
        )

        assert run.error is None

        raw_result = run.result or ""
        assert "test-secret-key" not in raw_result

    finally:
        delete_run(run_id)


@pytest.mark.asyncio
async def test_background_job_success(monkeypatch):
    run_id = f"success-job-{uuid.uuid4()}"
    session_id = f"success-session-{uuid.uuid4()}"

    db = SessionLocal()

    try:
        run = Run(
            id=run_id,
            user_id=1,
            session_id=session_id,
            prompt="Create a test application",
            status="queued",
            current_step="queued",
            progress=0,
            message="Run queued.",
        )

        db.add(run)
        db.commit()

    finally:
        db.close()

    fake_result = {
        "success": True,
        "review": "Project completed successfully.",
    }

    class FakeOrchestrator:
        def __init__(self, llm=None):
            self.llm = llm

        async def execute(self, **kwargs):
            assert kwargs["task"] == "Create a test application"
            assert kwargs["session_id"] == session_id
            assert kwargs["run_id"] == run_id

            return fake_result

    monkeypatch.setattr(
        "app.services.run.job_manager.AgentOrchestrator",
        FakeOrchestrator,
    )

    monkeypatch.setattr(
        "app.services.run.job_manager.LLMRouter.get_llm",
        lambda **kwargs: object(),
    )

    messages = []

    monkeypatch.setattr(
        "app.services.run.job_manager.add_message",
        lambda session_id, role, content: messages.append(
            {
                "session_id": session_id,
                "role": role,
                "content": content,
            }
        ),
    )

    try:
        await RunJobManager._execute(
            run_id=run_id,
            user_id=1,
            session_id=session_id,
            prompt="Create a test application",
            history=[],
            provider=None,
            api_key=None,
            model=None,
        )

        assert messages == [
            {
                "session_id": session_id,
                "role": "assistant",
                "content": "Project completed successfully.",
            }
        ]

    finally:
        delete_run(run_id)


@pytest.mark.asyncio
async def test_background_job_failure(monkeypatch):
    run_id = f"failed-job-{uuid.uuid4()}"
    session_id = f"failed-session-{uuid.uuid4()}"

    db = SessionLocal()

    try:
        run = Run(
            id=run_id,
            user_id=1,
            session_id=session_id,
            prompt="Create a broken application",
            status="queued",
            current_step="queued",
            progress=0,
            message="Run queued.",
        )

        db.add(run)
        db.commit()

    finally:
        db.close()

    class FailingOrchestrator:
        def __init__(self, llm=None):
            pass

        async def execute(self, **kwargs):
            raise RuntimeError(
                "Simulated orchestrator failure"
            )

    monkeypatch.setattr(
        "app.services.run.job_manager.AgentOrchestrator",
        FailingOrchestrator,
    )

    monkeypatch.setattr(
        "app.services.run.job_manager.LLMRouter.get_llm",
        lambda **kwargs: object(),
    )

    try:
        await RunJobManager._execute(
            run_id=run_id,
            user_id=1,
            session_id=session_id,
            prompt="Create a broken application",
            history=[],
            provider=None,
            api_key=None,
            model=None,
        )

        run = get_run_from_db(run_id)

        assert run is not None
        assert run.status == "failed"
        assert run.current_step == "Failed"
        assert run.progress == 100
        assert run.completed_at is not None
        assert run.error == "Simulated orchestrator failure"

    finally:
        delete_run(run_id)


@pytest.mark.asyncio
async def test_run_job_manager_registry(monkeypatch):
    run_id = f"registry-job-{uuid.uuid4()}"

    async def fake_execute(**kwargs):
        await asyncio.sleep(0.05)

    monkeypatch.setattr(
        RunJobManager,
        "_execute",
        fake_execute,
    )

    task = RunJobManager.start(
        run_id=run_id,
        session_id="registry-session",
        prompt="Registry test",
        history=[],
    )

    try:
        assert RunJobManager.is_running(run_id)
        assert RunJobManager.active_count() >= 1

        await task
        await asyncio.sleep(0)

        assert not RunJobManager.is_running(run_id)

    finally:
        existing = RunJobManager._tasks.pop(
            run_id,
            None,
        )

        if existing is not None and not existing.done():
            existing.cancel()

            await asyncio.gather(
                existing,
                return_exceptions=True,
            )


def test_background_run_api_key_not_persisted(
    monkeypatch,
):
    session_id = f"security-job-{uuid.uuid4()}"
    secret = "super-secret-user-key"
    captured = {}

    def fake_start(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "app.api.runs.RunJobManager.start",
        fake_start,
    )

    client = TestClient(app)

    response = client.post(
        "/runs",
        headers=AUTH_HEADERS,
        json={
            "session_id": session_id,
            "message": "Create an application",
            "provider": "gemini",
            "api_key": secret,
            "model": "gemini-2.5-flash",
        },
    )

    assert response.status_code == 202

    run_id = response.json()["run_id"]

    try:
        run = get_run_from_db(run_id)

        assert run is not None

        serialized = json.dumps(
            {
                "prompt": run.prompt,
                "result": run.result,
                "error": run.error,
                "message": run.message,
            }
        )

        assert secret not in serialized
        assert captured["api_key"] == secret

    finally:
        delete_run(run_id)


def test_reject_duplicate_active_run(
    monkeypatch,
):
    session_id = f"duplicate-session-{uuid.uuid4()}"
    existing_run_id = f"existing-{uuid.uuid4()}"

    db = SessionLocal()

    try:
        run = Run(
            id=existing_run_id,
            user_id=1,
            session_id=session_id,
            prompt="Existing active task",
            status="running",
            current_step="Coding",
            progress=40,
            message="Run is currently executing.",
        )

        db.add(run)
        db.commit()

    finally:
        db.close()

    start_called = False

    def fake_start(**kwargs):
        nonlocal start_called
        start_called = True

    monkeypatch.setattr(
        "app.api.runs.RunJobManager.start",
        fake_start,
    )

    client = TestClient(app)

    try:
        response = client.post(
        "/runs",
        headers=AUTH_HEADERS,
            json={
                "session_id": session_id,
                "message": "Start another task",
            },
        )

        assert response.status_code == 409

        data = response.json()

        assert (
            data["detail"]
            == "An active run already exists for this session."
        )

        assert start_called is False

        runs = get_runs_for_session(session_id)

        assert len(runs) == 1
        assert runs[0].id == existing_run_id
        assert runs[0].prompt == "Existing active task"

    finally:
        delete_run(existing_run_id)


def test_reject_duplicate_queued_run(
    monkeypatch,
):
    session_id = f"queued-duplicate-{uuid.uuid4()}"
    existing_run_id = f"queued-existing-{uuid.uuid4()}"

    db = SessionLocal()

    try:
        run = Run(
            id=existing_run_id,
            user_id=1,
            session_id=session_id,
            prompt="Queued active task",
            status="queued",
            current_step="queued",
            progress=0,
            message="Run queued.",
        )

        db.add(run)
        db.commit()

    finally:
        db.close()

    start_called = False

    def fake_start(**kwargs):
        nonlocal start_called
        start_called = True

    monkeypatch.setattr(
        "app.api.runs.RunJobManager.start",
        fake_start,
    )

    client = TestClient(app)

    try:
        response = client.post(
        "/runs",
        headers=AUTH_HEADERS,
            json={
                "session_id": session_id,
                "message": "Start another queued task",
            },
        )

        assert response.status_code == 409

        data = response.json()

        assert (
            data["detail"]
            == "An active run already exists for this session."
        )

        assert start_called is False

        runs = get_runs_for_session(session_id)

        assert len(runs) == 1

    finally:
        delete_run(existing_run_id)


@pytest.mark.parametrize(
    "run_status",
    [
        "completed",
        "failed",
        "cancelled",
    ],
)
def test_new_run_allowed_after_finished_run(
    monkeypatch,
    run_status,
):
    session_id = (
        f"finished-session-{run_status}-{uuid.uuid4()}"
    )
    existing_run_id = f"finished-{uuid.uuid4()}"
    captured = {}

    db = SessionLocal()

    try:
        run = Run(
            id=existing_run_id,
            user_id=1,
            session_id=session_id,
            prompt="Previous task",
            status=run_status,
            current_step="Completed",
            progress=100,
            message="Previous run finished.",
        )

        db.add(run)
        db.commit()

    finally:
        db.close()

    def fake_start(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "app.api.runs.RunJobManager.start",
        fake_start,
    )

    client = TestClient(app)

    response = client.post(
        "/runs",
        headers=AUTH_HEADERS,
        json={
            "session_id": session_id,
            "message": "Start a new task",
        },
    )

    assert response.status_code == 202

    data = response.json()

    assert data["success"] is True
    assert data["session_id"] == session_id
    assert data["status"] == "queued"
    assert data["run_id"] != existing_run_id

    new_run_id = data["run_id"]

    try:
        assert captured["run_id"] == new_run_id
        assert captured["session_id"] == session_id
        assert captured["prompt"] == "Start a new task"

        runs = get_runs_for_session(session_id)

        assert len(runs) == 2

    finally:
        delete_run(existing_run_id)
        delete_run(new_run_id)


def test_different_sessions_can_start_runs(
    monkeypatch,
):
    session_one = f"session-one-{uuid.uuid4()}"
    session_two = f"session-two-{uuid.uuid4()}"

    existing_run_id = f"session-one-run-{uuid.uuid4()}"

    db = SessionLocal()

    try:
        run = Run(
            id=existing_run_id,
            user_id=1,
            session_id=session_one,
            prompt="Existing task",
            status="running",
            current_step="Coding",
            progress=50,
            message="Running.",
        )

        db.add(run)
        db.commit()

    finally:
        db.close()

    captured = {}

    def fake_start(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "app.api.runs.RunJobManager.start",
        fake_start,
    )

    client = TestClient(app)

    response = client.post(
        "/runs",
        headers=AUTH_HEADERS,
        json={
            "session_id": session_two,
            "message": "Different session task",
        },
    )

    assert response.status_code == 202

    data = response.json()

    assert data["success"] is True
    assert data["session_id"] == session_two
    assert data["run_id"] != existing_run_id

    new_run_id = data["run_id"]

    try:
        assert captured["run_id"] == new_run_id
        assert captured["session_id"] == session_two
        assert captured["prompt"] == "Different session task"

    finally:
        delete_run(existing_run_id)
        delete_run(new_run_id)


def test_duplicate_run_does_not_add_user_message(
    monkeypatch,
):
    session_id = f"message-protection-{uuid.uuid4()}"
    existing_run_id = f"message-existing-{uuid.uuid4()}"

    db = SessionLocal()

    try:
        run = Run(
            id=existing_run_id,
            user_id=1,
            session_id=session_id,
            prompt="Existing task",
            status="running",
            current_step="Coding",
            progress=20,
            message="Running.",
        )

        db.add(run)
        db.commit()

    finally:
        db.close()

    monkeypatch.setattr(
        "app.api.runs.RunJobManager.start",
        lambda **kwargs: pytest.fail(
            "RunJobManager.start should not be called."
        ),
    )

    message_called = False

    def fake_add_message(
        session_id,
        role,
        content,
    ):
        nonlocal message_called
        message_called = True

    monkeypatch.setattr(
        "app.api.runs.add_message",
        fake_add_message,
    )

    client = TestClient(app)

    try:
        response = client.post(
        "/runs",
        headers=AUTH_HEADERS,
            json={
                "session_id": session_id,
                "message": "This should be rejected",
            },
        )

        assert response.status_code == 409

        assert message_called is False

    finally:
        delete_run(existing_run_id)


@pytest.mark.asyncio
async def test_cancel_active_run(monkeypatch):
    run_id = f"cancel-job-{uuid.uuid4()}"
    session_id = f"cancel-session-{uuid.uuid4()}"

    db = SessionLocal()

    try:
        run = Run(
            id=run_id,
            user_id=1,
            session_id=session_id,
            prompt="Long running task",
            status="running",
            current_step="Coding",
            progress=35,
            message="Generating code.",
        )

        db.add(run)
        db.commit()

    finally:
        db.close()

    async def fake_execute(**kwargs):
        await asyncio.sleep(60)

    monkeypatch.setattr(
        RunJobManager,
        "_execute",
        fake_execute,
    )

    task = RunJobManager.start(
        run_id=run_id,
            user_id=1,
        session_id=session_id,
        prompt="Long running task",
        history=[],
    )

    try:
        await asyncio.sleep(0)

        assert RunJobManager.is_running(run_id)

        cancelled = RunJobManager.cancel(run_id)

        assert cancelled is True

        await asyncio.gather(
            task,
            return_exceptions=True,
        )

        await asyncio.sleep(0)

        assert not RunJobManager.is_running(run_id)

        run = get_run_from_db(run_id)

        assert run is not None
        assert run.status == "cancelled"
        assert run.current_step == "Cancelled"
        assert run.progress == 100
        assert run.message == "Run cancelled by user."
        assert run.completed_at is not None
        assert run.error is None

    finally:
        existing = RunJobManager._tasks.pop(
            run_id,
            None,
        )

        if existing is not None and not existing.done():
            existing.cancel()

            await asyncio.gather(
                existing,
                return_exceptions=True,
            )

        delete_run(run_id)


def test_cancel_unknown_run():
    run_id = f"unknown-cancel-{uuid.uuid4()}"

    client = TestClient(app)

    response = client.post(
        f"/runs/{run_id}/cancel",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 404

    data = response.json()

    assert data["detail"] == "Run not found."


@pytest.mark.parametrize(
    "run_status",
    [
        "completed",
        "failed",
        "cancelled",
    ],
)
def test_cancel_finished_run(run_status):
    run_id = f"finished-cancel-{uuid.uuid4()}"
    session_id = f"finished-session-{uuid.uuid4()}"

    db = SessionLocal()

    try:
        run = Run(
            id=run_id,
            user_id=1,
            session_id=session_id,
            prompt="Finished task",
            status=run_status,
            current_step="Completed",
            progress=100,
            message="Run finished.",
        )

        db.add(run)
        db.commit()

    finally:
        db.close()

    client = TestClient(app)

    try:
        response = client.post(
        f"/runs/{run_id}/cancel",
        headers=AUTH_HEADERS,
    )

        assert response.status_code == 409

        data = response.json()

        assert (
            data["detail"]
            == (
                "Run cannot be cancelled because "
                f"it is already {run_status}."
            )
        )

    finally:
        delete_run(run_id)


@pytest.mark.asyncio
async def test_cancel_missing_active_task():
    run_id = f"orphan-cancel-{uuid.uuid4()}"
    session_id = f"orphan-session-{uuid.uuid4()}"

    db = SessionLocal()

    try:
        run = Run(
            id=run_id,
            user_id=1,
            session_id=session_id,
            prompt="Orphaned task",
            status="running",
            current_step="Coding",
            progress=35,
            message="Generating code.",
        )

        db.add(run)
        db.commit()

    finally:
        db.close()

    client = TestClient(app)

    try:
        response = client.post(
        f"/runs/{run_id}/cancel",
        headers=AUTH_HEADERS,
    )

        assert response.status_code == 409

        data = response.json()

        assert (
            data["detail"]
            == "Run is not currently active."
        )

    finally:
        delete_run(run_id)











