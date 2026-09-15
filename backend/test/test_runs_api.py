import uuid
from datetime import datetime, UTC

from fastapi.testclient import TestClient

from app.database.database import Base, SessionLocal, engine
from app.database.models import Run
from app.main import app
from app.services.auth.service import create_access_token


from app.services.auth.service import create_access_token


TEST_TOKEN = create_access_token(
    user_id=1,
    username="santhosh_test",
)

AUTH_HEADERS = {
    "Authorization": f"Bearer {TEST_TOKEN}",
}

TEST_TOKEN = create_access_token(
    user_id=1,
    username="santhosh_test",
)

AUTH_HEADERS = {
    "Authorization": f"Bearer {TEST_TOKEN}",
}


Base.metadata.create_all(bind=engine)


def create_test_run(
    run_id=None,
    session_id="test-session",
):
    if run_id is None:
        run_id = f"test-run-{uuid.uuid4()}"

    now = datetime.now(UTC).replace(tzinfo=None)

    db = SessionLocal()

    try:
        run = Run(
            id=run_id,
            user_id=1,
            session_id=session_id,
            prompt="Create a hello world application",
            status="completed",
            current_step="Completed",
            progress=100,
            message="Project generation completed successfully.",
            result='{"success": true, "score": 0.9}',
            error=None,
            created_at=now,
            started_at=now,
            completed_at=now,
            updated_at=now,
        )

        db.add(run)
        db.commit()
        db.refresh(run)

        return run

    finally:
        db.close()


def delete_test_run(run_id):
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


def delete_test_runs_by_session(session_id):
    db = SessionLocal()

    try:
        runs = (
            db.query(Run)
            .filter(Run.session_id == session_id)
            .all()
        )

        for run in runs:
            db.delete(run)

        db.commit()

    finally:
        db.close()


def test_get_run():
    run_id = f"test-get-run-{uuid.uuid4()}"

    try:
        create_test_run(
            run_id=run_id,
            session_id="single-run-session",
        )

        client = TestClient(app)

        response = client.get(
            f"/runs/{run_id}",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200

        data = response.json()

        assert data["success"] is True

        run = data["run"]

        assert run["run_id"] == run_id

        assert run["session_id"] == "single-run-session"

        assert run["status"] == "completed"

        assert run["current_step"] == "Completed"
        assert run["progress"] == 100

        assert (
            run["message"]
            == "Project generation completed successfully."
        )

        assert run["result"]["success"] is True

        assert run["result"]["score"] == 0.9

        assert run["error"] is None

        assert run["created_at"] is not None
        assert run["started_at"] is not None
        assert run["completed_at"] is not None
        assert run["updated_at"] is not None

    finally:
        delete_test_run(run_id)


def test_get_missing_run():
    client = TestClient(app)

    response = client.get(
        f"/runs/non-existent-{uuid.uuid4()}",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 404

    data = response.json()

    assert data["detail"] == "Run not found."


def test_get_runs_by_session():
    session_id = f"history-session-{uuid.uuid4()}"

    run_id_1 = f"history-run-1-{uuid.uuid4()}"
    run_id_2 = f"history-run-2-{uuid.uuid4()}"

    try:
        create_test_run(
            run_id=run_id_1,
            session_id=session_id,
        )

        create_test_run(
            run_id=run_id_2,
            session_id=session_id,
        )

        client = TestClient(app)

        response = client.get(
            f"/runs/session/{session_id}",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200

        data = response.json()

        assert data["success"] is True

        assert data["count"] == 2

        assert len(data["runs"]) == 2

        run_ids = [
            run["run_id"]
            for run in data["runs"]
        ]

        assert run_id_1 in run_ids
        assert run_id_2 in run_ids

        for run in data["runs"]:
            assert run["session_id"] == session_id

            assert run["status"] == "completed"

            assert run["progress"] == 100

    finally:
        delete_test_runs_by_session(session_id)


def test_get_runs_empty_session():
    session_id = f"empty-session-{uuid.uuid4()}"

    client = TestClient(app)

    response = client.get(
        f"/runs/session/{session_id}",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["count"] == 0
    assert data["runs"] == []


def test_get_all_runs():
    client = TestClient(app)

    response = client.get(
        "/runs/",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert "count" in data
    assert "runs" in data
    assert isinstance(data["runs"], list)
    assert data["count"] == len(data["runs"])
