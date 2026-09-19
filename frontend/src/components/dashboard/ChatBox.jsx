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
  X,
} from "lucide-react";

import Progress from "./Progress";
import ProjectViewer from "./ProjectViewer";
import useWebSocket from "../../hooks/useWebSocket";
import { createRun, getRun } from "../../api/api";

const SESSION_STORAGE_KEY = "autodev_session_id";
const API_BASE_URL = "http://127.0.0.1:8000";

function getSessionId() {
  const existing = localStorage.getItem(
    SESSION_STORAGE_KEY,
  );

  if (existing) {
    return existing;
  }

  const id = crypto.randomUUID();

  localStorage.setItem(
    SESSION_STORAGE_KEY,
    id,
  );

  return id;
}

function getPreviewUrl(downloadUrl) {
  if (!downloadUrl) {
    return null;
  }

  try {
    const url = new URL(
      downloadUrl,
      API_BASE_URL,
    );

    const downloadPrefix = "/download/";

    if (
      !url.pathname.startsWith(
        downloadPrefix,
      )
    ) {
      return null;
    }

    const zipName = url.pathname.slice(
      downloadPrefix.length,
    );

    if (!zipName) {
      return null;
    }

    const projectName = decodeURIComponent(
      zipName,
    ).replace(/\.zip$/i, "");

    return `${API_BASE_URL}/preview/${encodeURIComponent(
      projectName,
    )}/index.html`;
  } catch (error) {
    console.error(
      "Failed to create preview URL:",
      error,
    );

    return null;
  }
}

function getProjectName(projectPath) {
  if (!projectPath) {
    return null;
  }

  const normalizedPath = String(
    projectPath,
  ).replace(/\\/g, "/");

  const parts = normalizedPath.split("/");

  return parts[parts.length - 1] || null;
}

export default function ChatBox() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [runId, setRunId] = useState(null);
  const [result, setResult] = useState(null);
  const [syncedRunState, setSyncedRunState] =
    useState(null);
  const [previewOpen, setPreviewOpen] =
    useState(false);
  const [previewUrl, setPreviewUrl] =
    useState(null);

  const sessionId = useMemo(
    () => getSessionId(),
    [],
  );

  const { runState } = useWebSocket(
    sessionId,
    runId,
  );

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
            session_id:
              run.session_id || sessionId,
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
            session_id:
              run.session_id || sessionId,
            status: "failed",
            step:
              run.current_step ||
              run.step ||
              "Failed",
            progress:
              typeof run.progress ===
              "number"
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
          session_id:
            run.session_id || sessionId,
          status:
            run.status || "running",
          step:
            run.current_step ||
            run.step ||
            null,
          progress:
            typeof run.progress ===
            "number"
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

    intervalId = window.setInterval(
      syncRun,
      2000,
    );

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

    setLoading(true);
    setResult(null);
    setSyncedRunState(null);
    setPreviewOpen(false);
    setPreviewUrl(null);

    try {
      const data = await createRun(
        sessionId,
        message,
      );

      if (!data?.run_id) {
        throw new Error(
          "Backend did not return a run ID.",
        );
      }

      setRunId(data.run_id);

      toast.success(
        "AutoDev AI started building your project.",
      );
    } catch (error) {
      console.error(
        "Project generation failed:",
        error,
      );

      setLoading(false);

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
      toast.error(
        "Download is not available.",
      );

      return;
    }

    const link =
      document.createElement("a");

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

    setPreviewUrl(
      generatedPreviewUrl,
    );

    setPreviewOpen(true);
  };

  const closePreview = () => {
    setPreviewOpen(false);
    setPreviewUrl(null);
  };

  const openPreviewFullscreen = () => {
    const iframe =
      document.getElementById(
        "autodev-preview-frame",
      );

    if (iframe?.requestFullscreen) {
      iframe.requestFullscreen();
    }
  };

  const handleSuggestion = (value) => {
    setPrompt(value);
  };

  const effectiveRunState =
    syncedRunState || runState;

  const isFailed =
    effectiveRunState?.status ===
    "failed";

  const isCompleted =
    effectiveRunState?.status ===
      "completed" ||
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

  const projectName =
    getProjectName(
      result?.project?.project_path,
    );

  const previewAvailable =
    projectType === "static_web";

  return (
    <>
      <div className="aio-workspace">
        <div className="aio-main">
          {!loading &&
            !result &&
            !isFailed && (
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
                    architecture, writes
                    the code, runs it, tests
                    it, and validates the
                    result.
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
                      setPrompt(
                        event.target.value,
                      )
                    }
                    onKeyDown={(event) => {
                      if (
                        event.key ===
                          "Enter" &&
                        (event.metaKey ||
                          event.ctrlKey)
                      ) {
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

                      <span>
                        characters
                      </span>

                      <span className="aio-hint-separator">
                        •
                      </span>

                      <span>
                        Ctrl + Enter to
                        build
                      </span>
                    </div>

                    <button
                      className="aio-build-button"
                      onClick={
                        generateProject
                      }
                      disabled={
                        !prompt.trim()
                      }
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
                    <span>
                      Plan
                    </span>
                  </div>

                  <div>
                    <Check size={14} />
                    <span>
                      Code
                    </span>
                  </div>

                  <div>
                    <Check size={14} />
                    <span>
                      Execute
                    </span>
                  </div>

                  <div>
                    <Check size={14} />
                    <span>
                      Self-heal
                    </span>
                  </div>

                  <div>
                    <Check size={14} />
                    <span>
                      Validate
                    </span>
                  </div>
                </div>
              </section>
            )}

          {loading && (
            <section className="aio-building">
              <div className="aio-building-top">
                <div className="aio-building-icon">
                  <Loader2
                    size={21}
                    className="animate-spin"
                  />
                </div>

                <div>
                  <span className="aio-section-label">
                    AUTONOMOUS BUILD
                  </span>

                  <h1>
                    Building your project
                  </h1>
                </div>
              </div>

              <p>
                AutoDev AI is working through
                the development pipeline.
              </p>

              <div className="aio-progress-container">
                <div className="aio-progress-header">
                  <span>
                    {effectiveRunState?.step ||
                      "Initializing"}
                  </span>

                  <span>
                    {effectiveRunState?.progress ??
                      0}
                    %
                  </span>
                </div>

                <Progress
                  runState={
                    effectiveRunState
                  }
                />
              </div>

              <div className="aio-building-status">
                <span className="aio-live-dot" />

                <span>
                  {effectiveRunState?.message ||
                    "AI is working on your project..."}
                </span>
              </div>

              {runId && (
                <div className="aio-build-id">
                  RUN{" "}
                  <span>
                    {runId.slice(0, 8)}
                  </span>
                </div>
              )}
            </section>
          )}

          {isFailed && (
            <section className="aio-failed">
              <div className="aio-failed-icon">
                <CircleAlert size={22} />
              </div>

              <span className="aio-section-label">
                BUILD FAILED
              </span>

              <h1>
                Something went wrong
              </h1>

              <p>
                {effectiveRunState?.error ||
                  effectiveRunState?.message ||
                  "The autonomous pipeline encountered an error."}
              </p>

              <button
                className="aio-retry-button"
                onClick={() => {
                  setSyncedRunState(
                    null,
                  );

                  setRunId(null);
                  setLoading(false);
                }}
              >
                Start again
              </button>
            </section>
          )}

          {result && (
            <section className="aio-result">
              <div className="aio-result-top">
                <div className="aio-result-heading">
                  <div className="aio-result-badge">
                    <CheckCircle2
                      size={14}
                    />
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
                      onClick={
                        handlePreview
                      }
                      className="aio-secondary-button"
                    >
                      <Eye size={16} />
                      Preview
                    </button>
                  )}

                  <button
                    onClick={
                      handleDownload
                    }
                    className="aio-primary-button"
                  >
                    <Download size={16} />
                    Download
                  </button>
                </div>
              </div>

              <div className="aio-result-grid">
                <div>
                  <span>
                    Validation
                  </span>

                  <strong>
                    {validationScore ??
                      "—"}

                    {validationScore !==
                      undefined &&
                      "/100"}
                  </strong>
                </div>

                <div>
                  <span>
                    Tests
                  </span>

                  <strong
                    className={
                      result?.tests
                        ?.success
                        ? "aio-positive"
                        : "aio-negative"
                    }
                  >
                    {result?.tests
                      ?.success
                      ? "Passed"
                      : "Failed"}
                  </strong>
                </div>

                <div>
                  <span>
                    AI Evaluation
                  </span>

                  <strong>
                    {evaluationScore ??
                      "—"}

                    {evaluationScore !==
                      undefined &&
                      "/100"}
                  </strong>
                </div>
              </div>

              {projectName && (
                <ProjectViewer
                  projectName={
                    projectName
                  }
                  execution={
                    result?.execution
                  }
                  tests={
                    result?.tests
                  }
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
            </section>
          )}

          {isCompleted &&
            !result && (
              <div className="aio-loading-result">
                <Loader2
                  size={17}
                  className="animate-spin"
                />

                Loading the completed
                project...
              </div>
            )}
        </div>
      </div>

      {previewOpen &&
        previewUrl && (
          <div className="aio-preview-overlay">
            <div className="aio-preview-modal">
              <header className="aio-preview-header">
                <div>
                  <strong>
                    Project Preview
                  </strong>

                  <span>
                    Generated by AutoDev AI
                  </span>
                </div>

                <div className="aio-preview-controls">
                  <button
                    onClick={
                      openPreviewFullscreen
                    }
                    title="Fullscreen"
                  >
                    <Maximize2
                      size={17}
                    />
                  </button>

                  <button
                    onClick={
                      closePreview
                    }
                    title="Close preview"
                  >
                    <X size={19} />
                  </button>
                </div>
              </header>

              <div className="aio-preview-content">
                <iframe
                  id="autodev-preview-frame"
                  title="AutoDev AI Project Preview"
                  src={previewUrl}
                  sandbox="allow-scripts"
                />
              </div>
            </div>
          </div>
        )}
    </>
  );
}
