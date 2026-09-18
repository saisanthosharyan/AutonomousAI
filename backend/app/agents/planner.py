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

        if not task or not task.strip():
            raise ValueError(
                "PlannerAgent received an empty task."
            )

        recent_history = (history or [])[-MAX_HISTORY_MESSAGES:]

        history_lines = [
            f"{str(m.get('role', 'user')).strip()}: "
            f"{str(m.get('content', '')).strip()}"
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

Your job is to understand the USER'S ACTUAL REQUEST and create
a minimal implementation plan BEFORE any code is written.

The user's requirements have the highest priority.

==================================================
MOST IMPORTANT FILE GENERATION RULE
==================================================

Generate ONLY the files that are explicitly requested by the user
OR technically required to make the requested functionality work.

NEVER create extra files simply because they are common software
engineering practices.

Do NOT automatically create:

- README.md
- .gitignore
- tests/
- test files
- requirements.txt
- pyproject.toml
- package.json
- Dockerfile
- docker-compose.yml
- CI/CD configuration
- GitHub Actions
- LICENSE
- .env.example
- configuration files
- documentation files

unless:

1. The user explicitly requests them, OR
2. They are technically required for the requested application.

A simple code request MUST remain a simple code request.

For example, if the user says:

"Write a Python program to print all prime numbers from 1 to 100."

The correct result is a single Python source file such as:

main.py

Do NOT generate:

README.md
.gitignore
tests/test_main.py
requirements.txt
Dockerfile
CI/CD
or any other unnecessary file.

==================================================
GENERATION MODES
==================================================

Determine the user's actual generation intent.

Use exactly one of these modes:

- "code"
- "website"
- "application"
- "api"
- "library"
- "script"
- "project"

--------------------------------------------------
CODE
--------------------------------------------------

Use "code" when the user primarily asks for code,
a program, function, algorithm, script, solution, or example.

Examples:

"Write a Python program to print prime numbers."

"Give me Java code for binary search."

"Create a JavaScript function to validate an email."

For code mode:

- Generate the minimum number of source files.
- Usually generate ONE source file.
- Do not create tests unless requested.
- Do not create README unless requested.
- Do not create project configuration unless technically required.
- Do not create documentation files unless requested.

--------------------------------------------------
WEBSITE
--------------------------------------------------

Use "website" when the user asks to build a website,
web page, landing page, dashboard, frontend, or browser UI.

Only create files actually needed by the requested website.

For example:

index.html
style.css
script.js

But do not automatically add:

README.md
.gitignore
tests
Docker
CI/CD

unless requested or required.

--------------------------------------------------
APPLICATION
--------------------------------------------------

Use "application" when the user asks for a complete
working application with multiple components or features.

Create only the architecture and files required by
the requested functionality.

--------------------------------------------------
API
--------------------------------------------------

Use "api" when the user explicitly requests an API,
backend service, REST API, GraphQL API, or similar.

Only create backend files required for the API.

--------------------------------------------------
LIBRARY
--------------------------------------------------

Use "library" when the user asks to create a reusable
package, module, SDK, or library.

Only create packaging/configuration files when they
are actually required or explicitly requested.

--------------------------------------------------
SCRIPT
--------------------------------------------------

Use "script" for automation scripts or one-off utilities.

Prefer one file unless additional files are explicitly
required.

--------------------------------------------------
PROJECT
--------------------------------------------------

Use "project" when the user explicitly asks for a complete
project/repository or asks for project structure, documentation,
tests, configuration, deployment, or similar project artifacts.

==================================================
USER REQUEST
==================================================

{task}

==================================================
EXISTING PROJECT CONTEXT
==================================================

{project_context or "No existing project supplied."}

==================================================
CONVERSATION HISTORY
==================================================

{history_text or "No previous conversation."}

==================================================
PLANNING RULES
==================================================

1. First understand exactly what the user requested.

2. Determine the generation_mode from the user's actual wording.

3. Never upgrade a simple code request into a complete project.

4. Never add files merely because they are considered
   "best practice."

5. If the user explicitly names files, include those files.

6. If the user explicitly asks for tests, create tests.

7. If the user explicitly asks for README/documentation,
   create documentation.

8. If the user explicitly asks for .gitignore,
   create .gitignore.

9. If the user explicitly asks for dependency files,
   create the appropriate dependency file.

10. If the user explicitly asks for a complete project,
    create the files necessary for that project.

11. If the user asks only for code, provide only code files.

12. Do not add a testing framework merely because the
    generated code could be tested.

13. Do not add dependencies when the language standard
    library is sufficient.

14. Do not add a framework when plain language features
    are sufficient.

15. Prefer the simplest possible implementation.

16. Do not invent requirements.

17. Do not introduce unnecessary technologies.

18. Do not assume Web + FastAPI + React + PostgreSQL.

19. Do not turn a script into an application.

20. Do not turn a code request into a repository.

21. estimated_files MUST represent the actual number of
    user-facing project files that should be generated.

22. requested_files MUST contain ONLY the files that should
    actually be generated for the user.

23. The Coder will use requested_files as the authoritative
    file-generation boundary.

==================================================
TECHNOLOGY RULES
==================================================

Only use technologies actually required by the request.

For example:

If the user asks:

"Write a Python program to print prime numbers."

Return:

generation_mode = "code"
project_type = "code"
language = "Python"
framework = ""
database = ""
authentication = ""
deployment = ""
testing = ""
dependencies = []
requested_files = ["main.py"]

Do NOT add pytest.

Do NOT add requirements.txt.

Do NOT add README.md.

Do NOT add .gitignore.

==================================================
EXPLICIT FILE REQUESTS
==================================================

If the user says:

"Create index.html, style.css and script.js"

then:

requested_files = [
    "index.html",
    "style.css",
    "script.js"
]

If the user says:

"Create a website with HTML CSS and JavaScript"

you may infer:

requested_files = [
    "index.html",
    "style.css",
    "script.js"
]

because these files are directly required for the requested
website.

However, do not add README, tests, gitignore, Docker,
CI/CD, or other files unless requested or technically required.

==================================================
EXISTING PROJECT RULES
==================================================

If an existing project is supplied:

- reuse the existing architecture
- preserve existing coding style
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

If the user asks for a small change to an existing project,
do not generate unrelated new project files.

==================================================
PROJECT COMPLEXITY
==================================================

Keep complexity proportional to the user's request.

A one-file code request should normally produce one file.

A small website should normally produce only the frontend
files required by that website.

A full application may require multiple files.

A complete project may require project configuration,
tests, documentation, and supporting files only when the
user requests them or they are technically necessary.

==================================================
REQUIRED JSON
==================================================

Return ONLY valid JSON.

Use exactly this structure:

{{
    "title": "Project Name",
    "description": "Concise description of the project.",

    "project_type": "code",
    "generation_mode": "code",

    "language": "Python",
    "framework": "",
    "backend": "",
    "frontend": "",
    "database": "",
    "authentication": "",
    "api_style": "",
    "deployment": "",
    "testing": "",

    "estimated_files": 1,

    "requested_files": [
        "main.py"
    ],

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

title:
Short meaningful name.

description:
Short description of what the user requested.

project_type:
Actual type of the requested software.

generation_mode:
One of:

code
website
application
api
library
script
project

language:
Primary programming language.

framework:
Only if actually required.

backend:
Only if actually required.

frontend:
Only if actually required.

database:
Only if persistent storage is required.

authentication:
Only if authentication is required.

deployment:
Only if deployment is requested or required.

testing:
Only if testing is explicitly requested or genuinely
required by the project.

dependencies:
Only dependencies required by the implementation.

features:
Only features requested by the user.

requested_files:
ONLY files that should actually be generated.

estimated_files:
Must equal the number of requested_files whenever
possible.

folder_structure:
Only directories/files that are actually necessary.

security:
Only relevant security considerations.

performance:
Only meaningful performance considerations.

implementation_order:
Only actual implementation steps.

steps:
Only actual implementation steps.

==================================================
EXAMPLE 1 — SIMPLE CODE REQUEST
==================================================

User:

"Write a Python program to print all prime numbers from 1 to 100."

Correct plan:

{{
    "title": "Prime Number Printer",
    "description": "A Python program that prints prime numbers from 1 to 100.",
    "project_type": "code",
    "generation_mode": "code",
    "language": "Python",
    "framework": "",
    "backend": "",
    "frontend": "",
    "database": "",
    "authentication": "",
    "api_style": "",
    "deployment": "",
    "testing": "",
    "estimated_files": 1,
    "requested_files": [
        "main.py"
    ],
    "features": [
        "Identify prime numbers",
        "Print prime numbers from 1 to 100"
    ],
    "dependencies": [],
    "folder_structure": [
        "main.py"
    ],
    "security": [],
    "performance": [],
    "implementation_order": [
        "Implement prime number detection",
        "Generate prime numbers from 1 to 100",
        "Print the results"
    ],
    "steps": [
        "Implement prime number detection",
        "Generate prime numbers from 1 to 100",
        "Print the results"
    ]
}}

==================================================
EXAMPLE 2 — WEBSITE
==================================================

User:

"Create a responsive todo website using HTML CSS and JavaScript."

Correct plan:

{{
    "title": "Responsive Todo Website",
    "description": "A responsive browser-based todo application.",
    "project_type": "Web Application",
    "generation_mode": "website",
    "language": "JavaScript",
    "framework": "",
    "backend": "",
    "frontend": "HTML, CSS, JavaScript",
    "database": "",
    "authentication": "",
    "api_style": "",
    "deployment": "",
    "testing": "",
    "estimated_files": 3,
    "requested_files": [
        "index.html",
        "style.css",
        "script.js"
    ],
    "features": [
        "Add tasks",
        "Complete tasks",
        "Delete tasks",
        "Responsive layout"
    ],
    "dependencies": [],
    "folder_structure": [
        "index.html",
        "style.css",
        "script.js"
    ],
    "security": [],
    "performance": [],
    "implementation_order": [
        "Create HTML structure",
        "Create responsive styles",
        "Implement todo functionality"
    ],
    "steps": [
        "Create HTML structure",
        "Create responsive styles",
        "Implement todo functionality"
    ]
}}

==================================================
FINAL RULES
==================================================

Return ONLY valid JSON.

No markdown.
No explanations.
No comments.
No code fences.

The plan MUST represent the user's actual request.

requested_files is the authoritative list of user-facing
files that the Coder should generate.

Never invent unnecessary files.

Never generate project boilerplate unless requested.

Never turn a simple code request into a complete project.

Always choose the minimum file set that correctly solves
the user's request.
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
                "Planner failed to generate a task."
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

        if any(
            not str(step).strip()
            for step in plan.steps
        ):
            raise RuntimeError(
                "PlannerAgent returned an empty implementation step."
            )

        if not plan.requested_files:
            raise RuntimeError(
                "PlannerAgent returned no requested files."
            )

        estimated_files = len(
            plan.requested_files
        )

        logger.info(
            "Estimated files: %s",
            estimated_files,
        )

        step_count = len(plan.steps)

        logger.info(
            "Planner generated %s implementation step(s).",
            step_count,
        )

        logger.info(
            "Generation mode: %s",
            plan.generation_mode,
        )

        logger.info(
            "Project type: %s",
            plan.project_type,
        )

        logger.info(
            "Requested files: %s",
            plan.requested_files,
        )

        logger.debug(
            "Project title: %s",
            plan.title,
        )

        logger.debug(
            "Description: %s",
            plan.description,
        )

        logger.debug(
            "Steps: %s",
            plan.steps,
        )

        logger.info("=" * 60)
        logger.info("Planner Agent Finished")
        logger.info("=" * 60)

        return plan