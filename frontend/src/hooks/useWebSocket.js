import { useEffect, useRef, useState } from "react";

const AUTH_TOKEN_KEY = "autodev_access_token";
const MAX_RECONNECT_ATTEMPTS = 10;
const RECONNECT_DELAY = 1500;

export default function useWebSocket(sessionId, runId) {
  const [runState, setRunState] = useState(null);
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);

  const ws = useRef(null);
  const reconnectTimer = useRef(null);
  const reconnectAttempts = useRef(0);
  const stopped = useRef(false);

  useEffect(() => {
    if (!sessionId || !runId) {
      return undefined;
    }

    const token = localStorage.getItem(AUTH_TOKEN_KEY);

    if (!token) {
      return undefined;
    }

    stopped.current = false;
    reconnectAttempts.current = 0;

    const connect = () => {
      if (stopped.current) {
        return;
      }

      if (
        ws.current &&
        (
          ws.current.readyState === WebSocket.OPEN ||
          ws.current.readyState === WebSocket.CONNECTING
        )
      ) {
        return;
      }

      const socket = new WebSocket(
        `ws://127.0.0.1:8000/ws/${sessionId}?token=${encodeURIComponent(token)}`
      );

      ws.current = socket;

      socket.onopen = () => {
        if (stopped.current || ws.current !== socket) {
          return;
        }

        console.log(
          "WebSocket connected for run:",
          runId
        );

        reconnectAttempts.current = 0;
        setConnected(true);
      };

      socket.onmessage = (event) => {
        if (stopped.current || ws.current !== socket) {
          return;
        }

        try {
          const data = JSON.parse(event.data);

          console.log(
            "WebSocket message:",
            data
          );

          console.log(
            "AUTODEV EVENT:",
            JSON.stringify(data, null, 2)
          );

          if (
            data.run_id &&
            data.run_id !== runId
          ) {
            console.log(
              "Ignoring message from different run:",
              data.run_id
            );
            return;
          }

          setEvents((previous) => [
            ...previous,
            data,
          ]);

          if (
            data.type === "run_state" ||
            data.type === "progress"
          ) {
            setRunState((previous) => ({
              ...previous,
              run_id: runId,
              session_id:
                data.session_id ??
                previous?.session_id ??
                sessionId,
              status:
                data.status ??
                previous?.status ??
                "running",
              step:
                data.step ??
                data.current_step ??
                previous?.step ??
                null,
              progress:
                typeof data.progress === "number"
                  ? Math.max(data.progress, previous?.progress ?? 0)
                  : previous?.progress ?? 0,
              message:
                data.message ??
                previous?.message ??
                "",
              error:
                data.error ??
                previous?.error ??
                null,
            }));
          }

          if (data.type === "status") {
            setRunState((previous) => ({
              ...previous,
              run_id: runId,
              session_id:
                previous?.session_id ??
                sessionId,
              status:
                data.status ??
                previous?.status ??
                "running",
              step:
                data.step ??
                data.current_step ??
                previous?.step ??
                null,
              progress:
                typeof data.progress === "number"
                  ? Math.max(data.progress, previous?.progress ?? 0)
                  : previous?.progress ?? 0,
              message:
                data.message ??
                previous?.message ??
                "",
              error:
                data.error ??
                previous?.error ??
                null,
            }));
          }

          if (data.type === "error") {
            setRunState((previous) => ({
              ...previous,
              run_id: runId,
              session_id:
                previous?.session_id ??
                sessionId,
              status: "failed",
              error:
                data.message ||
                data.error ||
                "WebSocket reported an error.",
              message:
                data.message ||
                data.error ||
                "WebSocket reported an error.",
            }));
          }

          if (data.type === "complete") {
            setRunState((previous) => ({
              ...previous,
              run_id: runId,
              session_id:
                previous?.session_id ??
                sessionId,
              status: "completed",
              progress: 100,
              step: "Completed",
              message:
                data.message ||
                "Project generation completed successfully.",
              error: null,
            }));
          }
        } catch (error) {
          console.error(
            "Failed to parse WebSocket message:",
            error
          );
        }
      };

      socket.onerror = (error) => {
        console.error(
          "WebSocket error:",
          error
        );

        if (ws.current === socket) {
          setConnected(false);
        }
      };

      socket.onclose = (event) => {
        console.log(
          "WebSocket closed:",
          event.code,
          event.reason
        );

        if (ws.current === socket) {
          ws.current = null;
          setConnected(false);
        }

        if (stopped.current) {
          return;
        }

        if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) {
          console.error(
            "WebSocket maximum reconnect attempts reached."
          );
          return;
        }

        reconnectAttempts.current += 1;

        console.log(
          `Reconnecting WebSocket (${reconnectAttempts.current}/${MAX_RECONNECT_ATTEMPTS})...`
        );

        reconnectTimer.current = setTimeout(
          connect,
          RECONNECT_DELAY
        );
      };
    };

    connect();

    return () => {
      stopped.current = true;

      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }

      const socket = ws.current;

      ws.current = null;

      if (
        socket &&
        (
          socket.readyState === WebSocket.OPEN ||
          socket.readyState === WebSocket.CONNECTING
        )
      ) {
        socket.close(
          1000,
          "Run changed"
        );
      }

      setConnected(false);
    };
  }, [sessionId, runId]);

  return {
    runState,
    events,
    connected,
  };
}