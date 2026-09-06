from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.logger import logger


class ConnectionManager:
    """
    Manages active WebSocket connections.

    A session can have only one active connection.
    When an old connection disconnects, it will only be
    removed if it is still the connection registered for
    that session.
    """

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    # --------------------------------------------------
    # Connect
    # --------------------------------------------------

    async def connect(
        self,
        session_id: str,
        websocket: WebSocket,
    ):
        await websocket.accept()

        old = self.active_connections.get(session_id)

        # Replace the existing connection.
        if old is not None and old is not websocket:
            if old.client_state == WebSocketState.CONNECTED:
                try:
                    await old.close()
                except Exception:
                    pass

        self.active_connections[session_id] = websocket

        logger.info(
            f"WebSocket connected: {session_id}"
        )

    # --------------------------------------------------
    # Disconnect
    # --------------------------------------------------

    def disconnect(
        self,
        session_id: str,
        websocket: WebSocket | None = None,
    ):
        current = self.active_connections.get(session_id)

        if current is None:
            return

        # If a specific websocket was supplied, only remove it
        # if it is still the currently registered connection.
        if websocket is not None and current is not websocket:
            return

        self.active_connections.pop(session_id, None)

        logger.info(
            f"WebSocket disconnected: {session_id}"
        )

    # --------------------------------------------------
    # Send JSON
    # --------------------------------------------------

    async def send_json(
        self,
        session_id: str,
        data: dict,
    ):
        websocket = self.active_connections.get(session_id)

        if websocket is None:
            return

        if websocket.client_state != WebSocketState.CONNECTED:
            self.disconnect(
                session_id,
                websocket,
            )
            return

        try:
            await websocket.send_json(data)

        except Exception:
            logger.exception(
                f"Failed sending WebSocket message: {session_id}"
            )

            self.disconnect(
                session_id,
                websocket,
            )

    # --------------------------------------------------
    # Progress
    # --------------------------------------------------

    async def send_progress(
        self,
        session_id: str,
        step: str,
        progress: int,
        message: str,
    ):
        await self.send_json(
            session_id,
            {
                "type": "progress",
                "step": step,
                "progress": progress,
                "message": message,
            },
        )

    # --------------------------------------------------
    # Status
    # --------------------------------------------------

    async def send_status(
        self,
        session_id: str,
        message: str,
    ):
        await self.send_json(
            session_id,
            {
                "type": "status",
                "message": message,
            },
        )

    # --------------------------------------------------
    # Error
    # --------------------------------------------------

    async def send_error(
        self,
        session_id: str,
        message: str,
    ):
        await self.send_json(
            session_id,
            {
                "type": "error",
                "message": message,
            },
        )

    # --------------------------------------------------
    # Complete
    # --------------------------------------------------

    async def send_complete(
        self,
        session_id: str,
        result: dict,
    ):
        await self.send_json(
            session_id,
            {
                "type": "complete",
                "result": result,
            },
        )

    # --------------------------------------------------
    # Broadcast
    # --------------------------------------------------

    async def broadcast(
        self,
        data: dict,
    ):
        disconnected = []

        for session_id, websocket in list(
            self.active_connections.items()
        ):
            try:
                if (
                    websocket.client_state
                    == WebSocketState.CONNECTED
                ):
                    await websocket.send_json(data)

                else:
                    disconnected.append(
                        (session_id, websocket)
                    )

            except Exception:
                disconnected.append(
                    (session_id, websocket)
                )

        for session_id, websocket in disconnected:
            self.disconnect(
                session_id,
                websocket,
            )

    # --------------------------------------------------
    # Stats
    # --------------------------------------------------

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


manager = ConnectionManager()