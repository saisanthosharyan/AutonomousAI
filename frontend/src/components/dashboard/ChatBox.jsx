import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import {
  CheckCircle2,
  CircleAlert,
  Download,
  Loader2,
  Sparkles,
} from "lucide-react";

import Progress from "./Progress";
import useWebSocket from "../../hooks/useWebSocket";
import {
  createRun,
  getRun,
} from "../../api/api";

const SESSION_STORAGE_KEY =
  "autodev_session_id";

function getSessionId() {
  const existing =
    localStorage.getItem(SESSION_STORAGE_KEY);

  if (existing) {
    return existing;
  }

  const id = crypto.randomUUID();

  localStorage.setItem(
    SESSION_STORAGE_KEY,
    id
  );

  return id;
}

export default function ChatBox() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [runId, setRunId] = useState(null);
  const [result, setResult] = useState(null);

  const sessionId = useMemo(
    () => getSessionId(),
    []
  );

  const {
    runState,
    connected,
  } = useWebSocket(sessionId);

  /*
   * Restore the run ID from WebSocket state.
   */
  useEffect(() => {
    if (!runState?.run_id) {
      return;
    }

    setRunId(runState.run_id);

    if (
      runState.status === "running" ||
      runState.status === "queued"
    ) {
      setLoading(true);
    }

    if (runState.status === "failed") {
      setLoading(false);
    }
  }, [runState]);

  /*
   * When the backend reports completion,
   * fetch the complete persisted result.
   */
  useEffect(() => {
    if (
      !runId ||
      runState?.status !== "completed"
    ) {
      return;
    }

    let cancelled = false;

    const loadCompletedRun = async () => {
      try {
        const response = await getRun(runId);

        if (cancelled) {
          return;
        }

        if (response?.run?.result) {
          setResult(response.run.result);
        }

        setLoading(false);
      } catch (error) {
        console.error(
          "Failed to load completed run:",
          error
        );
      }
    };

    loadCompletedRun();

    return () => {
      cancelled = true;
    };
  }, [runId, runState?.status]);

  const generateProject = async () => {
    const message = prompt.trim();

    if (!message) {
      toast.error(
        "Please enter a project description."
      );
      return;
    }

    setLoading(true);
    setResult(null);
    setRunId(null);

    try {
      const data = await createRun(
        sessionId,
        message
      );

      if (!data?.run_id) {
        throw new Error(
          "Backend did not return a run ID."
        );
      }

      setRunId(data.run_id);

      toast.success(
        "Project generation started."
      );
    } catch (error) {
      console.error(
        "Project generation failed:",
        error
      );

      setLoading(false);

      toast.error(
        error?.response?.data?.detail ||
          error.message ||
          "Failed to start project generation."
      );
    }
  };

  const handleDownload = () => {
    const downloadUrl =
      result?.project?.download_url;

    if (!downloadUrl) {
      toast.error(
        "Download is not available."
      );
      return;
    }

    window.open(
      downloadUrl,
      "_blank",
      "noopener,noreferrer"
    );
  };

  const isFailed =
    runState?.status === "failed";

  const isCompleted =
    runState?.status === "completed";

  const projectTitle =
    result?.plan?.title ||
    result?.project?.name ||
    "Generated Project";

  const validationScore =
    result?.validation?.score;

  const evaluationScore =
    result?.evaluation?.overall_score;

  return (
    <div className="mx-auto max-w-7xl space-y-8 p-6 md:p-8">

      {/* Hero */}

      <section className="rounded-3xl border border-cyan-500/20 bg-gradient-to-br from-cyan-600 via-blue-700 to-indigo-800 p-8 shadow-2xl md:p-10">

        <div className="flex items-start gap-4">

          <div className="rounded-2xl bg-white/10 p-3 backdrop-blur">
            <Sparkles size={32} />
          </div>

          <div>
            <h1 className="text-4xl font-bold md:text-5xl">
              AutoDev AI
            </h1>

            <p className="mt-2 text-lg text-cyan-100 md:text-xl">
              Autonomous AI Software Engineer
            </p>

            <p className="mt-4 max-w-3xl text-sm leading-6 text-blue-100 md:text-base">
              Describe what you want to build and
              AutoDev AI will plan, code, build,
              execute, debug, validate, test,
              review and evaluate the project.
            </p>
          </div>

        </div>

      </section>

      {/* Connection status */}

      <div className="flex items-center justify-between rounded-xl border border-gray-800 bg-gray-900 px-5 py-3">

        <div className="flex items-center gap-3">

          <span
            className={`h-2.5 w-2.5 rounded-full ${
              connected
                ? "bg-green-400"
                : "bg-red-400"
            }`}
          />

          <span className="text-sm text-gray-300">
            {connected
              ? "Live agent connection"
              : "Agent connection offline"}
          </span>

        </div>

        {runId && (
          <span className="max-w-[240px] truncate text-xs text-gray-500">
            Run: {runId}
          </span>
        )}

      </div>

      {/* Prompt */}

      <section className="rounded-2xl border border-gray-800 bg-gray-900 p-6 shadow-xl md:p-8">

        <div className="mb-6">

          <h2 className="flex items-center gap-3 text-2xl font-bold">
            <Sparkles className="text-cyan-400" />
            Build Anything
          </h2>

          <p className="mt-2 text-gray-400">
            Tell the AI what you want to build.
          </p>

        </div>

        <textarea
          rows={8}
          value={prompt}
          disabled={loading}
          onChange={(event) =>
            setPrompt(event.target.value)
          }
          placeholder={`Example:

Build a MERN ecommerce website with authentication,
admin panel, product management, Stripe payments,
Docker deployment and automated tests.`}
          className="w-full resize-none rounded-xl border border-gray-700 bg-gray-950 p-5 text-base text-white outline-none transition placeholder:text-gray-600 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
        />

        <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">

          <p className="text-sm text-gray-500">
            {prompt.length} characters
          </p>

          <button
            onClick={generateProject}
            disabled={loading}
            className="flex items-center justify-center gap-3 rounded-xl bg-cyan-500 px-8 py-4 font-bold text-white transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2
                  size={20}
                  className="animate-spin"
                />
                Generating...
              </>
            ) : (
              <>
                <Sparkles size={20} />
                Generate Project
              </>
            )}
          </button>

        </div>

      </section>

      {/* Progress */}

      <Progress runState={runState} />

      {/* Failure */}

      {isFailed && (
        <section className="rounded-2xl border border-red-500/30 bg-red-950/30 p-6">

          <div className="flex items-start gap-4">

            <CircleAlert
              className="mt-1 shrink-0 text-red-400"
              size={24}
            />

            <div>
              <h2 className="font-bold text-red-300">
                Project generation failed
              </h2>

              <p className="mt-2 text-sm text-red-200/80">
                {runState?.error ||
                  runState?.message ||
                  "The autonomous pipeline encountered an error."}
              </p>
            </div>

          </div>

        </section>
      )}

      {/* Result */}

      {result && (
        <section className="rounded-2xl border border-gray-800 bg-gray-900 p-6 shadow-xl md:p-8">

          <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">

            <div className="flex items-center gap-3">

              <CheckCircle2
                className="text-green-400"
                size={30}
              />

              <div>
                <h2 className="text-2xl font-bold">
                  Project Result
                </h2>

                <p className="text-sm text-gray-400">
                  Autonomous pipeline completed
                </p>
              </div>

            </div>

            {result?.project?.download_url && (
              <button
                onClick={handleDownload}
                className="flex items-center justify-center gap-2 rounded-xl bg-green-500 px-6 py-3 font-semibold transition hover:bg-green-400"
              >
                <Download size={19} />
                Download Project
              </button>
            )}

          </div>

          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">

            <div className="rounded-xl border border-gray-800 bg-gray-950 p-5">

              <p className="text-sm font-semibold text-cyan-400">
                Project
              </p>

              <p className="mt-2 font-semibold">
                {projectTitle}
              </p>

            </div>

            <div className="rounded-xl border border-gray-800 bg-gray-950 p-5">

              <p className="text-sm font-semibold text-cyan-400">
                Validation
              </p>

              <p className="mt-2 text-2xl font-bold">
                {validationScore ?? "—"}
                {validationScore !== undefined &&
                  "/100"}
              </p>

            </div>

            <div className="rounded-xl border border-gray-800 bg-gray-950 p-5">

              <p className="text-sm font-semibold text-cyan-400">
                Tests
              </p>

              <p className="mt-2 font-semibold">
                {result?.tests?.success
                  ? "Passed"
                  : "Failed"}
              </p>

            </div>

            <div className="rounded-xl border border-gray-800 bg-gray-950 p-5">

              <p className="text-sm font-semibold text-cyan-400">
                AI Evaluation
              </p>

              <p className="mt-2 text-2xl font-bold">
                {evaluationScore ?? "—"}
                {evaluationScore !== undefined &&
                  "/100"}
              </p>

            </div>

          </div>

          {/* Review */}

          {result?.review && (
            <div className="mt-6 rounded-xl border border-gray-800 bg-gray-950 p-5">

              <h3 className="font-semibold text-cyan-400">
                AI Review
              </h3>

              <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap text-sm leading-6 text-gray-300">
                {typeof result.review ===
                "string"
                  ? result.review
                  : JSON.stringify(
                      result.review,
                      null,
                      2
                    )}
              </pre>

            </div>
          )}

        </section>
      )}

      {/* Completed state without result */}

      {isCompleted && !result && (
        <div className="rounded-xl border border-yellow-500/20 bg-yellow-950/20 p-5 text-sm text-yellow-300">
          The run completed, but the final result
          is still being loaded...
        </div>
      )}

    </div>
  );
}