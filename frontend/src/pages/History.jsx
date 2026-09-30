import { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  History as HistoryIcon,
  LoaderCircle,
  RefreshCw,
  XCircle,
} from "lucide-react";

import { getRuns } from "../api/api";

function formatDate(value) {
  if (!value) {
    return "Unknown date";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown date";
  }

  return date.toLocaleString();
}

function getStatusIcon(status) {
  switch (status) {
    case "completed":
      return <CheckCircle2 size={15} />;

    case "failed":
      return <AlertCircle size={15} />;

    case "cancelled":
      return <XCircle size={15} />;

    case "running":
    case "queued":
      return <LoaderCircle className="aio-spin" size={15} />;

    default:
      return <Clock3 size={15} />;
  }
}

export default function History() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadRuns = async () => {
    try {
      setLoading(true);
      setError("");

      const data = await getRuns();

      setRuns(
        Array.isArray(data?.runs)
          ? data.runs
          : [],
      );
    } catch (err) {
      console.error(
        "Failed to load build history:",
        err,
      );

      setError(
        err?.response?.data?.detail ||
          "Unable to load build history.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      loadRuns();
    }, 0);

    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="aio-workspace">
      <div className="aio-main">
        <section className="aio-history-page">
          <div className="aio-history-header">
            <div>
              <div className="aio-section-label">
                <HistoryIcon size={12} />
                BUILD HISTORY
              </div>

              <h1>Build History</h1>

              <p>
                View your previous AutoDev AI project
                generations and build activity.
              </p>
            </div>

            <button
              type="button"
              className="aio-history-refresh"
              onClick={loadRuns}
              disabled={loading}
            >
              <RefreshCw
                size={14}
                className={
                  loading ? "aio-spin" : ""
                }
              />
              Refresh
            </button>
          </div>

          {error && (
            <div
              className="aio-projects-error"
              role="alert"
            >
              {error}
            </div>
          )}

          {loading ? (
            <div className="aio-history-empty">
              <LoaderCircle
                className="aio-spin"
                size={22}
              />

              <p>Loading build history...</p>
            </div>
          ) : runs.length === 0 ? (
            <div className="aio-history-empty">
              <div className="aio-history-empty-icon">
                <HistoryIcon size={20} />
              </div>

              <h2>No build history yet</h2>

              <p>
                Projects you generate with AutoDev AI
                will appear here.
              </p>
            </div>
          ) : (
            <div className="aio-history-list">
              {runs.map((run) => (
                <article
                  key={run.run_id}
                  className="aio-history-card"
                >
                  <div className="aio-history-card-main">
                    <div
                      className={`aio-history-status is-${run.status}`}
                    >
                      {getStatusIcon(run.status)}

                      <span>
                        {run.status || "unknown"}
                      </span>
                    </div>

                    <h2>{run.prompt}</h2>

                    <div className="aio-history-details">
                      <span>
                        {run.current_step ||
                          "No step information"}
                      </span>

                      <span>
                        {Number.isFinite(run.progress)
                          ? `${run.progress}%`
                          : "0%"}
                      </span>
                    </div>

                    {run.error && (
                      <div className="aio-history-error">
                        {run.error}
                      </div>
                    )}
                  </div>

                  <div className="aio-history-card-meta">
                    <span>
                      {formatDate(run.created_at)}
                    </span>

                    <span
                      className="aio-history-run-id"
                      title={run.run_id}
                    >
                      {run.run_id}
                    </span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}