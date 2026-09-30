import {
  Calendar,
  FolderCode,
  Trash2,
  ArrowRight,
} from "lucide-react";
import { Link } from "react-router-dom";

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

export default function ProjectCard({
  project,
  onDelete,
  deleting = false,
}) {
  return (
    <article className="aio-project-card">
      <div className="aio-project-card-top">
        <div className="aio-project-card-icon">
          <FolderCode size={18} />
        </div>

        <button
          type="button"
          className="aio-project-delete"
          onClick={() => onDelete(project)}
          disabled={deleting}
          aria-label={`Delete ${project.title}`}
          title="Delete project"
        >
          <Trash2 size={15} />
        </button>
      </div>

      <div className="aio-project-card-content">
        <h2>{project.title}</h2>

        <p className="aio-project-card-prompt">
          {project.prompt}
        </p>
      </div>

      <div className="aio-project-card-footer">
        <div className="aio-project-date">
          <Calendar size={13} />
          <span>{formatDate(project.created_at)}</span>
        </div>

        <Link
          to={`/projects/${project.id}`}
          className="aio-project-open"
        >
          Open project
          <ArrowRight size={14} />
        </Link>
      </div>
    </article>
  );
}