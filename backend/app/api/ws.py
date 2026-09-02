from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logger import logger
from app.database.crud import get_runs_by_session
from app.database.database import SessionLocal
from app.websocket.manager import manager


router = APIRouter(tags=["WebSocket"])


def serialize_run_state(run):
    """
    Convert a persisted Run model into a WebSocket-safe state payload.
    """

    return {
        "type": "run_state",
        "run_id": run.id,
        "session_id": run.session_id,
        "status": run.status,
        "step": run.current_step,
        "progress": run.progress,
        "message": run.message,
        "error": run.error,
    }


def get_latest_run_state(session_id: str):
    """
    Retrieve the most recent persisted run for a session.
    """

    db = SessionLocal()

    try:
        runs = get_runs_by_session(
            db,
            session_id,
        )

        if not runs:
            return None

        return serialize_run_state(
            runs[0]
        )

    finally:
        db.close()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
):

    if not session_id.strip():
        await websocket.close(code=1008)
        return

    logger.info("=" * 60)
    logger.info(
        f"Incoming WebSocket Connection: {session_id}"
    )
    logger.info("=" * 60)

    await manager.connect(
        session_id=session_id,
        websocket=websocket,
    )

    try:

        # --------------------------------------------------
        # Restore latest persisted run state
        # --------------------------------------------------

        try:

            run_state = get_latest_run_state(
                session_id
            )

            if run_state is not None:

                await manager.send_json(
                    session_id,
                    run_state,
                )

                logger.info(
                    f"[{session_id}] Restored latest run state."
                )

        except Exception:

            logger.exception(
                f"[{session_id}] Failed to restore run state."
            )

        # --------------------------------------------------
        # Listen for client messages
        # --------------------------------------------------

        while True:

            message = await websocket.receive_text()

            if not message.strip():
                continue

            logger.info(
                f"[{session_id}] Received: {message}"
            )

            # Heartbeat support
            if message.lower() == "ping":

                await websocket.send_text(
                    "pong"
                )

    except WebSocketDisconnect:

        logger.info(
            f"WebSocket disconnected: {session_id}"
        )

    except Exception:

        logger.exception(
            f"WebSocket error: {session_id}"
        )

    finally:

        manager.disconnect(
            session_id
        )

        logger.info(
            f"Connection closed: {session_id}"
        )