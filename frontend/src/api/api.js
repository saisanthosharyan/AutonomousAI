import axios from "axios";

const AUTH_TOKEN_KEY = "autodev_access_token";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

export const registerUser = async (
  username,
  email,
  password,
) => {
  const response = await api.post("/auth/register", {
    username,
    email,
    password,
  });

  return response.data;
};

export const loginUser = async (
  email,
  password,
) => {
  const response = await api.post("/auth/login", {
    email,
    password,
  });

  return response.data;
};

export const getCurrentUser = async () => {
  const response = await api.get("/auth/me");

  return response.data;
};

export const createRun = async (
  sessionId,
  message,
  provider,
  apiKey,
  model,
) => {
  const response = await api.post("/runs", {
    session_id: sessionId,
    message,
    provider: provider || undefined,
    api_key: apiKey || undefined,
    model: model || undefined,
  });

  return response.data;
};

export const getRun = async (runId) => {
  const response = await api.get(`/runs/${runId}`);

  return response.data;
};

export const getSessionRuns = async (
  sessionId,
) => {
  const response = await api.get(
    `/runs/session/${sessionId}`,
  );

  return response.data;
};

export const getRuns = async () => {
  const response = await api.get("/runs");

  return response.data;
};

export const cancelRun = async (runId) => {
  const response = await api.post(
    `/runs/${runId}/cancel`,
  );

  return response.data;
};

export const getProjects = async () => {
  const response = await api.get("/projects");

  return response.data;
};

export const getProject = async (projectId) => {
  const response = await api.get(
    `/projects/${projectId}`,
  );

  return response.data;
};

export const deleteProject = async (
  projectId,
) => {
  const response = await api.delete(
    `/projects/${projectId}`,
  );

  return response.data;
};

export const getProjectFiles = async (
  projectName,
) => {
  const response = await api.get(
    `/project-files/${encodeURIComponent(projectName)}`,
  );

  return response.data;
};

export default api;