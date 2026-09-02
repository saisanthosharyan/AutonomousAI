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

Your job is to understand the USER'S ACTUAL REQUEST and create an implementation plan BEFORE any code is written.

IMPORTANT:
The user's requirements have the highest priority.

Do NOT assume the project is a web application.
Do NOT automatically add FastAPI, React, PostgreSQL, Docker, JWT, authentication, APIs, or cloud deployment.
Only include technologies and features that are actually required by the user's request.

==================================================
EXISTING PROJECT CONTEXT
==================================================

{project_context or "No existing project supplied."}

==================================================
CONVERSATION HISTORY
==================================================

{history_text or "No previous conversation."}

==================================================
USER REQUEST
==================================================

{task}

==================================================
PLANNING RULES
==================================================

1. First identify exactly what the user wants.

2. Determine the project type from the user's request.

Possible project types include:
- CLI Application
- Web Application
- REST API
- Mobile Application
- Desktop Application
- Library
- Automation Script
- AI/ML Application
- Data Science Project
- Game
- Browser Extension
- Other

3. Choose the simplest appropriate technology stack.

4. DO NOT introduce unnecessary technologies.

For example:

If the user requests:

"Create a Python calculator CLI"

Then:

project_type = "CLI Application"
language = "Python"
framework = ""
database = ""
authentication = ""
api_style = ""
frontend = ""

Do NOT add:
- FastAPI
- React
- PostgreSQL
- JWT
- Docker
- Redis
- Kubernetes
- cloud deployment

unless the user explicitly requests them.

5. Prefer simplicity for small projects.

6. Only add a database when persistent data storage is actually required.

7. Only add authentication when users/accounts are actually required.

8. Only add a frontend when a graphical/web interface is actually required.

9. Only add an API when the user requests an API or the application genuinely requires one.

10. Only add Docker when containerization is requested or clearly necessary.

11. Only add deployment configuration when deployment is requested or clearly necessary.

12. Do not invent requirements.

13. Do not add features merely because they are common in other applications.

14. Do not turn a CLI application into a web application.

15. Do not turn a simple script into a complex architecture.

==================================================
EXISTING PROJECT RULES
==================================================

If an existing project is supplied:

- reuse the existing architecture
- preserve the existing coding style
- extend existing functionality
- avoid rewriting working code
- avoid duplicate files
- avoid duplicate dependencies
- preserve existing APIs
- preserve existing folder structure
- reuse existing utilities
- reuse existing services
- reuse existing models
- reuse existing project conventions

Only create new files when necessary.

==================================================
PROJECT COMPLEXITY
==================================================

Estimate complexity based on the actual request.

For a small project:

- keep the number of files small
- avoid unnecessary abstractions
- avoid unnecessary frameworks
- avoid unnecessary services
- avoid unnecessary infrastructure

For example, a simple Python calculator may only need:

app.py
README.md
tests/test_app.py

Do not create dozens of files for a simple application.

==================================================
REQUIRED JSON
==================================================

Return ONLY valid JSON.

Use exactly this structure:

{{
    "title": "Project Name",
    "description": "Concise description of the project.",

    "project_type": "CLI Application",
    "difficulty": "Beginner",

    "language": "Python",
    "framework": "",
    "backend": "",
    "frontend": "",
    "database": "",
    "authentication": "",
    "api_style": "",
    "deployment": "",
    "testing": "",

    "estimated_files": 3,

    "features": [],

    "dependencies": [],

    "folder_structure": [],

    "security": [],

    "performance": [],

    "implementation_order": [],

    "steps": []
}}

==================================================
FIELD RULES
==================================================

language:
The primary programming language required by the project.

framework:
Only include a framework if one is actually needed.

backend:
Only include a backend technology if required.

frontend:
Only include a frontend technology if required.

database:
Only include a database if persistent storage is required.

authentication:
Only include authentication if required.

api_style:
Only include REST/GraphQL/etc. if an API is required.

deployment:
Only include deployment technologies if deployment is requested.

testing:
Only include testing technologies appropriate to the project.

dependencies:
Only include dependencies that are actually needed.

folder_structure:
Only include directories that are actually necessary.

security:
Only include security measures relevant to the project.

performance:
Only include meaningful performance considerations.

==================================================
EXAMPLE
==================================================

For the request:

"Create a simple Python calculator CLI application."

A good plan would look approximately like:

{{
    "title": "Simple Python Calculator CLI",
    "description": "A command-line calculator that performs basic arithmetic operations.",

    "project_type": "CLI Application",
    "difficulty": "Beginner",

    "language": "Python",
    "framework": "",
    "backend": "",
    "frontend": "",
    "database": "",
    "authentication": "",
    "api_style": "",
    "deployment": "",
    "testing": "Pytest",

    "estimated_files": 3,

    "features": [
        "Addition",
        "Subtraction",
        "Multiplication",
        "Division",
        "Division by zero handling",
        "Command-line input"
    ],

    "dependencies": [
        "pytest"
    ],

    "folder_structure": [
        "app.py",
        "tests/",
        "tests/test_app.py",
        "README.md"
    ],

    "security": [],
    "performance": [],

    "implementation_order": [
        "Analyze calculator requirements",
        "Implement arithmetic operations",
        "Implement command-line interface",
        "Handle invalid input",
        "Add tests",
        "Create README"
    ],

    "steps": [
        "Create the calculator application",
        "Implement addition",
        "Implement subtraction",
        "Implement multiplication",
        "Implement division with division-by-zero handling",
        "Implement command-line argument handling",
        "Add automated tests",
        "Create project documentation"
    ]
}}

==================================================
FINAL RULES
==================================================

Return ONLY JSON.

No markdown.
No explanations.
No comments.
No code fences.

The plan MUST represent the user's actual request.

Never invent unnecessary technologies.

Never assume Web + FastAPI + React + PostgreSQL.

Always choose the simplest architecture that correctly solves the user's problem.
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
            error = "Planner failed to generate a task."

            await self._fail_run(
                run_id,
                error,
            )

            raise RuntimeError(error)

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