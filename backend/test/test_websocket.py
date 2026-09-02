import uuid
from datetime import datetime, UTC

from fastapi.testclient import TestClient

from app.database.database import Base, SessionLocal, engine
from app.database.models import Run
from app.main import app


# --------------------------------------------------
# Test Database Setup
# --------------------------------------------------

Base.metadata.create_all(
    bind=engine
)


# --------------------------------------------------
# Helpers
# --------------------------------------------------


def create_test_run(
    session_id,
    status="running",
    current_step="Coder",
    progress=35,
    message="Generating project source code...",
):
    run_id = f"ws-run-{uuid.uuid4()}"

    now = datetime.now(
        UTC
    ).replace(
        tzinfo=None
    )

    db = SessionLocal()

    try:

        run = Run(
            id=run_id,
            session_id=session_id,
            prompt="Create a hello world application",
            status=status,
            current_step=current_step,
            progress=progress,
            message=message,
            result=None,
            error=None,
            created_at=now,
            started_at=now,
            completed_at=None,
            updated_at=now,
        )

        db.add(run)
        db.commit()
        db.refresh(run)

        return run_id

    finally:

        db.close()


def delete_test_runs(
    session_id
):
    db = SessionLocal()

    try:

        runs = (
            db.query(Run)
            .filter(
                Run.session_id == session_id
            )
            .all()
        )

        for run in runs:
            db.delete(run)

        db.commit()

    finally:

        db.close()


# --------------------------------------------------
# Restore Latest Run State
# --------------------------------------------------


def test_websocket_restores_latest_run_state():

    session_id = (
        f"ws-session-{uuid.uuid4()}"
    )

    try:

        run_id = create_test_run(
            session_id=session_id,
            status="running",
            current_step="Coder",
            progress=35,
            message=(
                "Generating project source code..."
            ),
        )

        client = TestClient(app)

        with client.websocket_connect(
            f"/ws/{session_id}"
        ) as websocket:

            data = websocket.receive_json()

            assert data["type"] == "run_state"

            assert (
                data["run_id"]
                == run_id
            )

            assert (
                data["session_id"]
                == session_id
            )

            assert (
                data["status"]
                == "running"
            )

            assert (
                data["step"]
                == "Coder"
            )

            assert data["progress"] == 35

            assert (
                data["message"]
                == "Generating project source code..."
            )

            assert data["error"] is None

    finally:

        delete_test_runs(
            session_id
        )


# --------------------------------------------------
# Empty Session
# --------------------------------------------------


def test_websocket_without_run_state():

    session_id = (
        f"empty-ws-session-{uuid.uuid4()}"
    )

    client = TestClient(app)

    with client.websocket_connect(
        f"/ws/{session_id}"
    ) as websocket:

        websocket.send_text(
            "ping"
        )

        response = (
            websocket.receive_text()
        )

        assert response == "pong"


# --------------------------------------------------
# Heartbeat
# --------------------------------------------------


def test_websocket_ping():

    session_id = (
        f"ping-session-{uuid.uuid4()}"
    )

    client = TestClient(app)

    with client.websocket_connect(
        f"/ws/{session_id}"
    ) as websocket:

        websocket.send_text(
            "ping"
        )

        response = (
            websocket.receive_text()
        )

        assert response == "pong"