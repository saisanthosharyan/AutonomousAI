import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import "../../styles/Dashboard.css";
import {
  ArrowUp,
  Check,
  CheckCircle2,
  CircleAlert,
  Download,
  Eye,
  Loader2,
  Maximize2,
  Sparkles,
  XCircle,
} from "lucide-react";

import ProjectViewer from "./ProjectViewer";
import useWebSocket from "../../hooks/useWebSocket";
import { createRun, getRun } from "../../api/api";

const SESSION_STORAGE_KEY = "autodev_session_id";
const API_BASE_URL = "http://127.0.0.1:8000";
const CHAT_HISTORY_KEY = "autodev_chat_history";

function getSessionId() {
  const existing = localStorage.getItem(SESSION_STORAGE_KEY);

  if (existing) {
    return existing;
  }

  const id = crypto.randomUUID();

  localStorage.setItem(SESSION_STORAGE_KEY, id);

  return id;
}

function getPreviewUrl(downloadUrl) {
  if (!downloadUrl) {
    return null;
  }

  try {
    const url = new URL(downloadUrl, API_BASE_URL);
    const downloadPrefix = "/download/";

    if (!url.pathname.startsWith(downloadPrefix)) {
      return null;
    }

    const zipName = url.pathname.slice(downloadPrefix.length);

    if (!zipName) {
      return null;
    }

    const projectName = decodeURIComponent(zipName).replace(
      /\.zip$/i,
      "",
    );

    return `${API_BASE_URL}/preview/${encodeURIComponent(
      projectName,
    )}/index.html`;
  } catch (error) {
    console.error("Failed to create preview URL:", error);
    return null;
  }
}

function getProjectName(projectPath) {
  if (!projectPath) {
    return null;
  }

  const normalizedPath = String(projectPath).replace(/\\/g, "/");
  const parts = normalizedPath.split("/");

  return parts[parts.length - 1] || null;
}

function CompactBuildStatus({ runState }) {
  const status = runState?.status ?? "running";
  const progress = runState?.progress ?? 0;
  const message =
    runState?.message || "Building your project...";

  const isFailed = status === "failed";
  const isCompleted = status === "completed";

  return (
    <div className="aio-chat-build-status">
      <div className="aio-chat-build-status-top">
        <div className="aio-chat-build-status-left">
          <div
            className={`aio-chat-build-status-icon ${
              isFailed ? "failed" : !isCompleted ? "loading" : ""
            }`}
          >
            {isFailed ? (
              <XCircle size={15} />
            ) : isCompleted ? (
              <CheckCircle2 size={15} />
            ) : (
              <Loader2 size={15} />
            )}
          </div>

          <span className="aio-chat-build-status-title">
            {isFailed
              ? "Build failed"
              : isCompleted
              ? "Build completed"
              : message}
          </span>
        </div>

        <span className="aio-chat-build-percent">
          {progress}%
        </span>
      </div>
    </div>
  );
}

function PreviewPanel({
  previewUrl,
  onFullscreen,
}) {
  return (
    <aside className="aio-project-preview-panel">
      <div className="aio-project-preview-header">
        <div className="aio-project-preview-heading">
          <div className="aio-project-preview-icon">
            <Eye size={15} />
          </div>

          <div>
            <strong>Project Preview</strong>
            <span>Live generated output</span>
          </div>
        </div>

        {previewUrl && (
          <button
            type="button"
            className="aio-project-preview-fullscreen"
            onClick={onFullscreen}
            title="Open fullscreen"
          >
            <Maximize2 size={15} />
          </button>
        )}
      </div>

      <div className="aio-project-preview-body">
        {previewUrl ? (
          <iframe
            id="autodev-preview-frame"
            title="AutoDev AI Project Preview"
            src={previewUrl}
            sandbox="allow-scripts allow-same-origin"
          />
        ) : (
          <div className="aio-project-preview-empty">
            <div className="aio-project-preview-empty-icon">
              <Eye size={20} />
            </div>

            <strong>Preview unavailable</strong>

            <span>
              A live preview will appear here when the generated
              project contains a supported web interface.
            </span>
          </div>
        )}
      </div>
    </aside>
  );
}

export default function ChatBox() {
  const [chatHistory, setChatHistory] = useState(() => {
    try {
      const saved = localStorage.getItem(CHAT_HISTORY_KEY);

      if (!saved) {
        return [];
      }

      const parsed = JSON.parse(saved);

      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      console.error(
        "Failed to load chat history:",
        error,
      );

      return [];
    }
  });

  const [prompt, setPrompt] = useState("");
  const [submittedPrompt, setSubmittedPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [runId, setRunId] = useState(null);
  const [result, setResult] = useState(null);
  const [syncedRunState, setSyncedRunState] = useState(null);

  const sessionId = useMemo(() => getSessionId(), []);

  const { runState } = useWebSocket(sessionId, runId);

  useEffect(() => {
    window.dispatchEvent(
      new CustomEvent("autodev-history-updated", {
        detail: chatHistory,
      }),
    );
  }, [chatHistory]);

  useEffect(() => {
    const handleNewChat = () => {
      setPrompt("");
      setSubmittedPrompt("");
      setLoading(false);
      setRunId(null);
      setResult(null);
      setSyncedRunState(null);
    };

    window.addEventListener(
      "autodev:new-chat",
      handleNewChat,
    );

    return () => {
      window.removeEventListener(
        "autodev:new-chat",
        handleNewChat,
      );
    };
  }, []);

  useEffect(() => {
    const handleOpenChat = (event) => {
      const chat = event.detail;

      if (!chat?.title) {
        return;
      }

      setSubmittedPrompt(chat.title);
      setPrompt("");
      setLoading(false);
      setRunId(null);
      setResult(null);
      setSyncedRunState(null);
    };

    window.addEventListener(
      "autodev:open-chat",
      handleOpenChat,
    );

    return () => {
      window.removeEventListener(
        "autodev:open-chat",
        handleOpenChat,
      );
    };
  }, []);

  useEffect(() => {
    if (!runId) {
      return undefined;
    }

    let cancelled = false;
    let intervalId = null;

    const syncRun = async () => {
      try {
        const response = await getRun(runId);
        const run = response?.run;

        if (cancelled || !run) {
          return;
        }

        if (run.status === "completed") {
          setSyncedRunState({
            run_id: run.run_id,
            session_id: run.session_id || sessionId,
            status: "completed",
            step: "Completed",
            progress: 100,
            message:
              run.message ||
              "Project generation completed successfully.",
            error: null,
          });

          if (run.result) {
            setResult(run.result);
          }

          setLoading(false);

          if (intervalId) {
            clearInterval(intervalId);
            intervalId = null;
          }

          return;
        }

        if (run.status === "failed") {
          setSyncedRunState({
            run_id: run.run_id,
            session_id: run.session_id || sessionId,
            status: "failed",
            step:
              run.current_step ||
              run.step ||
              "Failed",
            progress:
              typeof run.progress === "number"
                ? run.progress
                : 0,
            message:
              run.message ||
              "Project generation failed.",
            error:
              run.error ||
              run.message ||
              "The autonomous pipeline encountered an error.",
          });

          setLoading(false);

          if (intervalId) {
            clearInterval(intervalId);
            intervalId = null;
          }

          return;
        }

        setSyncedRunState({
          run_id: run.run_id,
          session_id: run.session_id || sessionId,
          status: run.status || "running",
          step:
            run.current_step ||
            run.step ||
            null,
          progress:
            typeof run.progress === "number"
              ? run.progress
              : 0,
          message: run.message || "",
          error: run.error || null,
        });

        setLoading(true);
      } catch (error) {
        console.error(
          "Failed to synchronize run:",
          error,
        );
      }
    };

    syncRun();

    intervalId = window.setInterval(syncRun, 2000);

    return () => {
      cancelled = true;

      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [runId, sessionId]);

  const generateProject = async () => {
    const message = prompt.trim();

    if (!message) {
      toast.error(
        "Please describe what you want to build.",
      );

      return;
    }

    setSubmittedPrompt(message);
    setPrompt("");
    setLoading(true);
    setResult(null);
    setSyncedRunState(null);

    try {
      const data = await createRun(sessionId, message);

      if (!data?.run_id) {
        throw new Error(
          "Backend did not return a run ID.",
        );
      }

      setRunId(data.run_id);

      const historyItem = {
        id: crypto.randomUUID(),
        title: message,
        runId: data.run_id,
        createdAt: Date.now(),
      };

      setChatHistory((previous) => {
        const updated = [
          historyItem,
          ...previous.filter(
            (item) => item.title !== message,
          ),
        ].slice(0, 20);

        localStorage.setItem(
          CHAT_HISTORY_KEY,
          JSON.stringify(updated),
        );

        return updated;
      });

      toast.success(
        "AutoDev AI started building your project.",
      );
    } catch (error) {
      console.error(
        "Project generation failed:",
        error,
      );

      setLoading(false);
      setRunId(null);

      toast.error(
        error?.response?.data?.detail ||
          error.message ||
          "Failed to start project generation.",
      );
    }
  };

  const handleDownload = () => {
    const downloadUrl =
      result?.project?.download_url;

    if (!downloadUrl) {
      toast.error("Download is not available.");
      return;
    }

    const link = document.createElement("a");

    link.href = downloadUrl;
    link.download = "";

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handlePreview = () => {
    const downloadUrl =
      result?.project?.download_url;

    const generatedPreviewUrl =
      getPreviewUrl(downloadUrl);

    if (!generatedPreviewUrl) {
      toast.error(
        "Preview is not available for this project.",
      );

      return;
    }

    const iframe = document.getElementById(
      "autodev-preview-frame",
    );

    if (iframe) {
      iframe.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });

      return;
    }

    toast.success(
      "Project preview is shown on the right.",
    );
  };

  const openPreviewFullscreen = () => {
    const iframe = document.getElementById(
      "autodev-preview-frame",
    );

    if (iframe?.requestFullscreen) {
      iframe.requestFullscreen();
    }
  };

  const handleSuggestion = (value) => {
    setPrompt(value);
  };

  const handleReset = () => {
    setPrompt("");
    setSubmittedPrompt("");
    setLoading(false);
    setRunId(null);
    setResult(null);
    setSyncedRunState(null);
  };

  const effectiveRunState =
    syncedRunState || runState;

  const isFailed =
    effectiveRunState?.status === "failed";

  const isCompleted =
    effectiveRunState?.status === "completed" ||
    result !== null;

  const projectTitle =
    result?.plan?.title ||
    result?.project?.name ||
    "Generated Project";

  const validationScore =
    result?.validation?.score;

  const evaluationScore =
    result?.evaluation?.overall_score;

  const projectType =
    result?.validation?.project_type ||
    null;

  const projectName = getProjectName(
    result?.project?.project_path,
  );

  const previewAvailable =
    projectType === "static_web";

  const generatedPreviewUrl =
    previewAvailable
      ? getPreviewUrl(
          result?.project?.download_url,
        )
      : null;

  return (
    <div className="aio-workspace">
      <div
        className={`aio-main aio-chat-layout ${
          result
            ? "aio-chat-layout-with-preview"
            : ""
        }`}
      >
        {!submittedPrompt && !loading && !result && (
          <section className="aio-create">
            <div className="aio-create-heading">
              <div className="aio-create-kicker">
                <span className="aio-kicker-line" />

                <span>
                  Autonomous development
                </span>

                <span className="aio-kicker-line" />
              </div>

              <h1>
                Build your next
                <span> project.</span>
              </h1>

              <p>
                Describe what you need.
                AutoDev AI plans the
                architecture, writes the
                code, runs it, tests it,
                and validates the result.
              </p>
            </div>

            <div className="aio-composer">
              <div className="aio-composer-label">
                <Sparkles size={15} />

                <span>
                  Project instructions
                </span>
              </div>

              <textarea
                value={prompt}
                onChange={(event) =>
                  setPrompt(event.target.value)
                }
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter" &&
                    !event.shiftKey
                  ) {
                    event.preventDefault();
                    generateProject();
                  }
                }}
                placeholder="Describe the application you want AutoDev AI to build..."
                rows={7}
              />

              <div className="aio-composer-bottom">
                <div className="aio-composer-hint">
                  <span>
                    {prompt.length}
                  </span>

                  <span>characters</span>

                  <span className="aio-hint-separator">
                    •
                  </span>

                  <span>
                    Enter to build
                  </span>
                </div>

                <button
                  className="aio-build-button"
                  onClick={generateProject}
                  disabled={!prompt.trim()}
                >
                  <span>
                    Build project
                  </span>

                  <ArrowUp size={16} />
                </button>
              </div>
            </div>

            <div className="aio-suggestions">
              <span className="aio-suggestions-label">
                Start with
              </span>

              <button
                onClick={() =>
                  handleSuggestion(
                    "Build a modern responsive landing page for a SaaS product.",
                  )
                }
              >
                Website
              </button>

              <button
                onClick={() =>
                  handleSuggestion(
                    "Build a full-stack web application with authentication and a dashboard.",
                  )
                }
              >
                Web App
              </button>

              <button
                onClick={() =>
                  handleSuggestion(
                    "Build an AI-powered application with a clean chat interface.",
                  )
                }
              >
                AI App
              </button>

              <button
                onClick={() =>
                  handleSuggestion(
                    "Build a professional analytics dashboard with charts and responsive design.",
                  )
                }
              >
                Dashboard
              </button>
            </div>

            <div className="aio-capabilities">
              <div>
                <Check size={14} />
                <span>Plan</span>
              </div>

              <div>
                <Check size={14} />
                <span>Code</span>
              </div>

              <div>
                <Check size={14} />
                <span>Execute</span>
              </div>

              <div>
                <Check size={14} />
                <span>Self-heal</span>
              </div>

              <div>
                <Check size={14} />
                <span>Validate</span>
              </div>
            </div>
          </section>
        )}

        {submittedPrompt && (
          <section className="aio-chat-conversation">
            <div className="aio-chat-user-message">
              <div className="aio-chat-user-message-inner">
                <div className="aio-chat-message-label">
                  You
                </div>

                <div className="aio-chat-user-bubble">
                  {submittedPrompt}
                </div>
              </div>
            </div>

            {(loading || isFailed) && (
              <div className="aio-chat-ai-message">
                <div className="aio-chat-ai-inner">
                  <div className="aio-chat-ai-heading">
                    <div className="aio-chat-ai-icon">
                      <Sparkles size={14} />
                    </div>

                    <span className="aio-chat-ai-name">
                      AutoDev AI
                    </span>
                  </div>

                  {loading && (
                    <>
                      <p className="aio-chat-response-text">
                        I'm building your project
                        autonomously. I'll plan,
                        generate, execute, test,
                        review, and validate it.
                      </p>

                      <CompactBuildStatus
                        runState={effectiveRunState}
                      />
                    </>
                  )}

                  {isFailed && (
                    <div className="aio-chat-error">
                      <CircleAlert size={15} />

                      <div>
                        <strong>
                          Build failed
                        </strong>

                        <p>
                          {effectiveRunState?.error ||
                            effectiveRunState?.message ||
                            "The autonomous pipeline encountered an error."}
                        </p>

                        <button
                          className="aio-retry-button"
                          onClick={handleReset}
                        >
                          Start new build
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {result && (
              <div className="aio-chat-ai-message">
                <div className="aio-chat-ai-inner">
                  <div className="aio-chat-ai-heading">
                    <div className="aio-chat-ai-icon">
                      <Sparkles size={14} />
                    </div>

                    <span className="aio-chat-ai-name">
                      AutoDev AI
                    </span>
                  </div>

                  <div className="aio-result">
                    <div className="aio-result-top">
                      <div className="aio-result-heading">
                        <div className="aio-result-badge">
                          <CheckCircle2 size={14} />
                          Build complete
                        </div>

                        <h1>
                          {projectTitle}
                        </h1>

                        <p>
                          Your project has been
                          generated, tested,
                          validated, and reviewed
                          by AutoDev AI.
                        </p>
                      </div>

                      <div className="aio-result-actions">
                        {previewAvailable && (
                          <button
                            onClick={handlePreview}
                            className="aio-secondary-button"
                          >
                            <Eye size={16} />
                            Preview
                          </button>
                        )}

                        <button
                          onClick={handleDownload}
                          className="aio-primary-button"
                        >
                          <Download size={16} />
                          Download
                        </button>
                      </div>
                    </div>

                    <div className="aio-result-grid">
                      <div>
                        <span>Validation</span>

                        <strong>
                          {validationScore ?? "—"}

                          {validationScore !==
                            undefined &&
                            "/100"}
                        </strong>
                      </div>

                      <div>
                        <span>Tests</span>

                        <strong
                          className={
                            result?.tests?.success
                              ? "aio-positive"
                              : "aio-negative"
                          }
                        >
                          {result?.tests?.success
                            ? "Passed"
                            : "Failed"}
                        </strong>
                      </div>

                      <div>
                        <span>AI Evaluation</span>

                        <strong>
                          {evaluationScore ?? "—"}

                          {evaluationScore !==
                            undefined &&
                            "/100"}
                        </strong>
                      </div>
                    </div>

                    {projectName && (
                      <ProjectViewer
                        projectName={projectName}
                        execution={result?.execution}
                        tests={result?.tests}
                      />
                    )}

                    {result?.review && (
                      <div className="aio-review">
                        <div className="aio-review-heading">
                          <div>
                            <span>
                              AutoDev AI Review
                            </span>

                            <small>
                              Automated analysis
                            </small>
                          </div>
                        </div>

                        <pre>
                          {typeof result.review ===
                          "string"
                            ? result.review
                            : JSON.stringify(
                                result.review,
                                null,
                                2,
                              )}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {isCompleted && !result && (
              <div className="aio-loading-result">
                <Loader2
                  size={17}
                  className="animate-spin"
                />

                Loading the completed project...
              </div>
            )}

            <div className="aio-chat-input-area">
              <textarea
                value={prompt}
                onChange={(event) =>
                  setPrompt(event.target.value)
                }
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter" &&
                    !event.shiftKey
                  ) {
                    event.preventDefault();

                    if (
                      prompt.trim() &&
                      !loading
                    ) {
                      generateProject();
                    }
                  }
                }}
                placeholder="Ask AutoDev AI to build something..."
                rows={2}
                disabled={loading}
              />

              <button
                type="button"
                className="aio-chat-send-button"
                onClick={generateProject}
                disabled={
                  !prompt.trim() || loading
                }
              >
                <ArrowUp size={17} />
              </button>
            </div>
          </section>
        )}
      </div>

      {result &&
        previewAvailable &&
        generatedPreviewUrl && (
          <PreviewPanel
            previewUrl={generatedPreviewUrl}
            onFullscreen={openPreviewFullscreen}
          />
        )}
    </div>
  );
}