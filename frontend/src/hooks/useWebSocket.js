import { useEffect, useRef, useState } from "react";

export default function useWebSocket(sessionId) {
  const [runState, setRunState] = useState(null);
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);

  const ws = useRef(null);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    const socket = new WebSocket(
      `ws://127.0.0.1:8000/ws/${sessionId}`
    );

    ws.current = socket;

    socket.onopen = () => {
      console.log("WebSocket connected");
      setConnected(true);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        console.log("WebSocket message:", data);

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
            run_id:
              data.run_id ?? previous?.run_id ?? null,
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
            status:
              data.status ??
              previous?.status ??
              "running",
            message:
              data.message ??
              previous?.message ??
              "",
          }));
        }

        if (data.type === "error") {
          setRunState((previous) => ({
            ...previous,
            status: "failed",
            error: data.message,
            message: data.message,
          }));
        }

        if (data.type === "complete") {
          setRunState((previous) => ({
            ...previous,
            status: "completed",
            progress: 100,
            message: "Run completed.",
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
      socket.close();
      ws.current = null;
    };
  }, [sessionId]);

  return {
    runState,
    events,
    connected,
  };
}