import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
  headers: {
    "Content-Type": "application/json",
  },
});

export const createRun = async (sessionId, message) => {
  const response = await api.post("/chat", {
    session_id: sessionId,
    message,
  });

  return response.data;
};

export const getRun = async (runId) => {
  const response = await api.get(`/runs/${runId}`);

  return response.data;
};

export const getSessionRuns = async (sessionId) => {
  const response = await api.get(`/runs/session/${sessionId}`);

  return response.data;
};

export default api;