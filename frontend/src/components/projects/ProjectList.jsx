import { FolderOpen, LoaderCircle } from "lucide-react";

import ProjectCard from "../dashboard/ProjectCard";

export default function ProjectList({
  projects,
  loading,
  deletingId,
  onDelete,
}) {
  if (loading) {
    return (
      <div className="aio-projects-state">
        <LoaderCircle
          className="aio-spin"
          size={22}
        />

        <p>Loading your projects...</p>
      </div>
    );
  }

  if (!projects.length) {
    return (
      <div className="aio-projects-state">
        <div className="aio-projects-state-icon">
          <FolderOpen size={21} />
        </div>

        <h2>No projects yet</h2>

        <p>
          Projects generated with AutoDev AI will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="aio-project-grid">
      {projects.map((project) => (
        <ProjectCard
          key={project.id}
          project={project}
          onDelete={onDelete}
          deleting={deletingId === project.id}
        />
      ))}
    </div>
  );
}