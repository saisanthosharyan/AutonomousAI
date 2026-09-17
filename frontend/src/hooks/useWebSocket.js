import { useEffect, useRef, useState } from "react";

const AUTH_TOKEN_KEY = "autodev_access_token";

export default function useWebSocket(sessionId, runId) {
  const [runState, setRunState] = useState(null);
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);

  const ws = useRef(null);

  useEffect(() => {
    if (!sessionId || !runId) {
      return undefined;
    }

    const token =
      localStorage.getItem(AUTH_TOKEN_KEY);

    if (!token) {
      return undefined;
    }

    const socket = new WebSocket(
      `ws://127.0.0.1:8000/ws/${sessionId}?token=${encodeURIComponent(token)}`
    );

    ws.current = socket;

    socket.onopen = () => {
      console.log(
        "WebSocket connected for run:",
        runId
      );

      setConnected(true);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        console.log(
          "WebSocket message:",
          data
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
                ? data.progress
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
                ? data.progress
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

      setConnected(false);
    };

    socket.onclose = (event) => {
      console.log(
        "WebSocket closed:",
        event.code,
        event.reason
      );

      setConnected(false);
    };

    return () => {
      if (ws.current === socket) {
        ws.current = null;
      }

      if (
        socket.readyState ===
          WebSocket.OPEN ||
        socket.readyState ===
          WebSocket.CONNECTING
      ) {
        socket.close(
          1000,
          "Run changed"
        );
      }
    };
  }, [sessionId, runId]);

  return {
    runState,
    events,
    connected,
  };
}