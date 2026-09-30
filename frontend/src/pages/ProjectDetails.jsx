import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Calendar,
  FolderCode,
  LoaderCircle,
} from "lucide-react";

import { getProject } from "../api/api";
import ProjectViewer from "../components/dashboard/ProjectViewer";

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

function getProjectName(projectPath) {
  if (!projectPath) {
    return "";
  }

  const normalized = projectPath.replace(/\\/g, "/");

  return normalized.split("/").filter(Boolean).pop() || "";
}

export default function ProjectDetails() {
  const { projectId } = useParams();

  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    const loadProject = async () => {
      try {
        const data = await getProject(projectId);

        if (cancelled) {
          return;
        }

        setProject(data?.project || null);
      } catch (err) {
        if (cancelled) {
          return;
        }

        console.error(
          "Failed to load project:",
          err,
        );

        setError(
          err?.response?.data?.detail ||
            "Unable to load project.",
        );
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadProject();

    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const projectName = useMemo(
    () => getProjectName(project?.project_path),
    [project?.project_path],
  );

  if (loading) {
    return (
      <div className="aio-workspace">
        <div className="aio-main">
          <div className="aio-project-details-state">
            <LoaderCircle
              className="aio-spin"
              size={22}
            />
            <span>Loading project...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="aio-workspace">
        <div className="aio-main">
          <section className="aio-project-details-page">
            <Link
              to="/projects"
              className="aio-project-details-back"
            >
              <ArrowLeft size={14} />
              Back to projects
            </Link>

            <div className="aio-projects-error">
              {error || "Project not found."}
            </div>
          </section>
        </div>
      </div>
    );
  }

  return (
    <div className="aio-workspace">
      <div className="aio-main">
        <section className="aio-project-details-page">
          <Link
            to="/projects"
            className="aio-project-details-back"
          >
            <ArrowLeft size={14} />
            Back to projects
          </Link>

          <div className="aio-project-details-header">
            <div className="aio-section-label">
              <FolderCode size={12} />
              PROJECT DETAILS
            </div>

            <h1>{project.title}</h1>

            <p>{project.prompt}</p>

            <div className="aio-project-details-meta">
              <span>
                <Calendar size={13} />
                {formatDate(project.created_at)}
              </span>

              <span>
                Project #{project.id}
              </span>
            </div>
          </div>

          {projectName ? (
            <ProjectViewer
              projectName={projectName}
            />
          ) : (
            <div className="aio-projects-error">
              Generated project files are unavailable.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}