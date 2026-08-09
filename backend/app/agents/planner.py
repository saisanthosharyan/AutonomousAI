from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.core.logger import logger
from app.models.task import Task
from app.services.llm.router import LLMRouter
from app.project.project_context import ProjectContext

MAX_HISTORY_MESSAGES = 20


class PlannerAgent(BaseAgent):
    """
    Generates a structured implementation plan before code generation.
    """

    def __init__(
        self,
        llm=None,
    ):
        self.llm = llm

        self.project_context = ProjectContext()

    async def run(
        self,
        task: str,
        project_directory: str | None = None,
        history: list[dict] | None = None,
    ) -> Task:

        logger.info("=" * 60)
        logger.info("Planner Agent Started")
        logger.info("=" * 60)

        # --------------------------------------------------
        # Validate input
        # --------------------------------------------------

        if not task or not task.strip():
            raise ValueError(
                "PlannerAgent received an empty task."
            )

        # --------------------------------------------------
        # Build conversation history safely (sanitized + truncated)
        # --------------------------------------------------

        recent_history = (history or [])[-MAX_HISTORY_MESSAGES:]

        history_lines = [
            f"{str(m.get('role', 'user')).strip()}: {str(m.get('content', '')).strip()}"
            for m in recent_history
            if isinstance(m, dict)
        ]

        history_text = "\n".join(history_lines)
        
        project_context = ""

        if project_directory:

            logger.info(
                "Analyzing existing project..."
            )

            try:

                self.project_context.build(
                    project_directory
                )

                project_context = (
                    self.project_context.build_llm_context(
                        max_chars=8000
                    )
                )

            except Exception:

                logger.exception(
                    "Project analysis failed."
                )

                self.project_context.clear()

        llm = self.llm or LLMRouter.get_llm()

        prompt = f"""
You are a Principal Software Architect and Technical Lead.

Your responsibility is to analyze the user's request and create a complete implementation plan BEFORE any code is written.

Existing Project Context

{project_context or "No existing project supplied."}

==================================================
CONVERSATION HISTORY
==================================================

{history_text or "No previous conversation."}

==================================================
CURRENT USER REQUEST
==================================================

{task}

==================================================
YOUR RESPONSIBILITIES
==================================================

Analyze BOTH

1. Existing project
2. User request

If the project already exists:

• reuse architecture
• preserve coding style
• extend instead of rewrite
• avoid duplicate files
• avoid duplicate dependencies
• preserve APIs
• preserve folder structure

Only generate new files if necessary.
• Project title
• Project objective
• Core features
• Recommended programming language
• Recommended framework(s)
• Database requirements
• Authentication requirements
• API requirements
• Folder structure
• Testing strategy
• Deployment strategy
• Implementation order

Choose the most appropriate technologies automatically.

==================================================
OUTPUT FORMAT
==================================================

Return ONLY valid JSON.

{{
  "title": "Project Name",
  "description": "A concise description of the project, its purpose, and expected outcome.",

  "project_type": "Web Application",
  "difficulty": "Intermediate",

  "backend": "FastAPI",
  "frontend": "React",
  "database": "PostgreSQL",
  "authentication": "JWT Authentication",
  "api_style": "REST API",
  "deployment": "Docker + Nginx + GitHub Actions",
  "testing": "Pytest + Playwright",

  "estimated_files": 35,

  "features": [
    "User Authentication",
    "Role-Based Access Control",
    "Dashboard",
    "CRUD Operations",
    "Search & Filtering",
    "Pagination",
    "File Upload",
    "Notifications",
    "Logging",
    "Error Handling"
  ],

  "dependencies": [
    "FastAPI",
    "SQLAlchemy",
    "Pydantic",
    "Alembic",
    "PostgreSQL",
    "React",
    "Axios",
    "JWT",
    "Docker"
  ],

  "folder_structure": [
    "app/",
    "app/api/",
    "app/models/",
    "app/schemas/",
    "app/services/",
    "app/repositories/",
    "app/core/",
    "app/utils/",
    "tests/",
    "frontend/",
    "docker/"
  ],

  "security": [
    "JWT Authentication",
    "Password Hashing",
    "Input Validation",
    "SQL Injection Protection",
    "XSS Protection",
    "CSRF Protection",
    "Rate Limiting",
    "Environment Variable Management"
  ],

  "performance": [
    "Database Indexing",
    "Caching",
    "Async Operations",
    "Pagination",
    "Lazy Loading",
    "Optimized Queries"
  ],

  "implementation_order": [
    "Requirement Analysis",
    "Project Architecture",
    "Project Initialization",
    "Database Design",
    "Backend Development",
    "Authentication",
    "API Development",
    "Frontend Development",
    "Testing",
    "Deployment"
  ],

  "steps": [
    "Analyze project requirements",
    "Design scalable system architecture",
    "Create project folder structure",
    "Initialize backend framework",
    "Initialize frontend framework",
    "Configure database",
    "Implement authentication and authorization",
    "Develop REST API endpoints",
    "Implement business logic",
    "Develop frontend UI components",
    "Integrate frontend with backend",
    "Implement validation and error handling",
    "Add logging and monitoring",
    "Write unit tests",
    "Write integration tests",
    "Perform security validation",
    "Optimize application performance",
    "Containerize using Docker",
    "Configure CI/CD pipeline",
    "Deploy the application"
  ]
}}

==================================================
RULES
==================================================

- Return ONLY JSON.
- No markdown.
- No explanations.
- No comments.
- No code fences.
- JSON must match the schema exactly.

When planning:

Prefer modifying existing files over creating new ones.

Never recreate an existing architecture.

Always preserve project consistency.

Avoid duplicate dependencies.

Reuse existing utilities.

Reuse existing services.

Reuse existing models.

Reuse existing APIs.

Reuse existing project conventions.
"""

        logger.info(
            "Generating implementation plan..."
        )

        try:

            plan = await llm.generate_structured(
                prompt=prompt,
                schema=Task,
            )

        except Exception as exc:

            logger.exception(
                "Planner Agent failed."
            )

            raise RuntimeError(
                f"PlannerAgent failed: {exc}"
            ) from exc

        if plan is None:

            raise RuntimeError(
                "PlannerAgent received no response."
            )

        if not isinstance(plan, Task):

            raise RuntimeError(
                "PlannerAgent returned an invalid Task object."
            )

        if not plan.title.strip():

            raise RuntimeError(
                "PlannerAgent returned an empty title."
            )

        if not plan.description.strip():

            raise RuntimeError(
                "PlannerAgent returned an empty description."
            )

        if not plan.steps:

            raise RuntimeError(
                "PlannerAgent returned no implementation steps."
            )

        if any(not str(step).strip() for step in plan.steps):

            raise RuntimeError(
                "PlannerAgent returned an empty implementation step."
            )

        step_count = len(plan.steps or [])

        logger.info(
            f"Planner generated {step_count} implementation step(s)."
        )
        logger.debug("Project title: %s", plan.title)
        logger.debug("Description: %s", plan.description)
        logger.debug("Steps: %s", plan.steps)

        logger.info("=" * 60)
        logger.info("Planner Agent Finished")
        logger.info("=" * 60)

        return plan