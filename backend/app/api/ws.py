from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.database.crud import get_runs_by_session
from app.database.database import SessionLocal
from app.database.models import User
from app.services.auth.service import decode_access_token
from app.websocket.manager import manager

router = APIRouter(tags=["WebSocket"])


def get_authenticated_user(websocket: WebSocket) -> User | None:
    token = websocket.query_params.get("token")

    if not token:
        return None

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")

        if not user_id:
            return None

        user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    except Exception:
        return None

    db: Session = SessionLocal()

    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


def serialize_run_state(run):
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


def get_latest_run_state(
    session_id: str,
    user_id: int,
):
    db = SessionLocal()

    try:
        runs = get_runs_by_session(
            db,
            session_id,
            user_id,
        )

        if not runs:
            return None

        return serialize_run_state(runs[0])
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

    user = get_authenticated_user(websocket)

    if user is None:
        await websocket.close(code=1008)
        return

    logger.info("=" * 60)
    logger.info(f"Incoming WebSocket Connection: {session_id}")
    logger.info("=" * 60)

    await manager.connect(
        session_id=session_id,
        websocket=websocket,
    )

    try:
        try:
            run_state = get_latest_run_state(
                session_id,
                user.id,
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

        while True:
            message = await websocket.receive_text()

            if not message.strip():
                continue

            logger.info(
                f"[{session_id}] Received: {message}"
            )

            if message.lower() == "ping":
                await websocket.send_text("pong")

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
            session_id,
            websocket,
        )
        logger.info(
            f"Connection closed: {session_id}"
        )