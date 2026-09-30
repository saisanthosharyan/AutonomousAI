# 🤖 AutoDev AI

> An autonomous AI software engineering platform that transforms natural-language requirements into working software projects through planning, code generation, execution, testing, self-healing, review, validation, and evaluation.

AutoDev AI is designed to go beyond a traditional AI coding assistant.

Instead of only returning code in a chat response, AutoDev AI runs an autonomous software-development pipeline that can understand a user's requirement, create a development plan, generate a multi-file project, build and execute it, run automated tests, detect failures, repair the project, review the implementation, validate the final output, evaluate its quality, and deliver the generated project through a web interface.

---

## 📌 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [How AutoDev AI Works](#-how-autodev-ai-works)
- [Autonomous Repair System](#-autonomous-repair-system)
- [AI Agents](#-ai-agents)
- [LLM Providers](#-llm-providers)
- [Generated Code Security](#️-generated-code-security)
- [Frontend Features](#️-frontend-features)
- [Backend Features](#️-backend-features)
- [Tech Stack](#️-tech-stack)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Environment Configuration](#️-environment-configuration)
- [Running the Backend](#-running-the-backend)
- [Running the Frontend](#-running-the-frontend)
- [Using Ollama](#-using-ollama)
- [Testing](#-testing)
- [Authentication](#-authentication)
- [Generated Projects](#-generated-projects)
- [Current Status](#-current-status)
- [Architecture](#️-architecture)
- [Project Goal](#-project-goal)
- [Security Notes](#-security-notes)
- [Development Roadmap](#️-development-roadmap)

---

# 🌟 Overview

AutoDev AI is an experimental autonomous software engineer.

A user can provide a high-level request such as:

```text
Create a Python calculator CLI with addition, subtraction,
multiplication and division with automated tests.
```

AutoDev AI can then progress through the software-development lifecycle:

```text
Requirement
    ↓
Planning
    ↓
Code Generation
    ↓
Project Building
    ↓
Execution
    ↓
Testing
    ↓
Debugging / Repair
    ↓
AI Review
    ↓
Validation
    ↓
Evaluation
    ↓
Delivery
```

The objective is to reduce the amount of manual intervention required between describing a software requirement and receiving a working project.

---

# 🚀 Key Features

## Autonomous Software Generation

- Natural-language project requirements
- AI-generated development plans
- Multi-file project generation
- Project structure generation
- Source-code generation
- Automated project building
- Generated project persistence

## Execution & Testing

- Automatic generated-project execution
- Language-aware execution infrastructure
- Automated test discovery and execution
- Execution output capture
- Test output capture
- Return-code handling
- Failure detection
- Structured execution results

## Self-Healing

- Automatic execution retry
- Automatic test retry
- AI-assisted code repair
- Error categorization
- Debug context generation
- Project rebuilding after repairs
- Repair history
- Retry statistics
- Review-driven repair loops

## AI Review & Evaluation

- AI code review
- Structured review results
- Review issue detection
- Review repair attempts
- Final project validation
- Project evaluation
- Quality scoring
- Final result aggregation

## LLM Infrastructure

- Google Gemini support
- OpenAI support
- OpenRouter support
- Ollama support
- Configurable provider priority
- Automatic provider fallback
- Local LLM support
- Request-scoped LLM handling

## Web Application

- React frontend
- Authentication
- AI development chat
- Real-time run progress
- Recent chats
- Historical chat restoration
- Projects dashboard
- Project details
- Generated-file browser
- Run history
- Project preview
- Project download
- Settings page
- Account information
- Sign out

## Security

- JWT authentication
- User-scoped project access
- Project-file ownership checks
- Python AST validation
- Unsafe `eval()` detection
- Unsafe `exec()` detection
- Reviewer security checks
- API-key configuration through environment variables

---

# 🧠 How AutoDev AI Works

The core pipeline follows this flow:

```text
┌──────────────────────┐
│      User Prompt     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│    Planner Agent     │
│                      │
│ Understands request  │
│ and creates a plan   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│     Coder Agent      │
│                      │
│ Generates project    │
│ source files         │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Project Builder    │
│                      │
│ Creates project      │
│ structure/files      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│      Execution       │
└──────────┬───────────┘
           │
     ┌─────┴─────┐
     │           │
  Success      Failure
     │           │
     │           ▼
     │    ┌───────────────┐
     │    │ Debug / Fixer │
     │    └───────┬───────┘
     │            │
     │            ▼
     │       Rebuild + Retry
     │            │
     └────────────┘
           │
           ▼
┌──────────────────────┐
│   Automated Tests    │
└──────────┬───────────┘
           │
     ┌─────┴─────┐
     │           │
  Success      Failure
     │           │
     │           ▼
     │       Repair Loop
     │           │
     └───────────┘
           │
           ▼
┌──────────────────────┐
│    Reviewer Agent    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Final Validation   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│      Evaluation      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Project Delivery   │
└──────────────────────┘
```

---

# 🔄 Autonomous Repair System

One of the core capabilities of AutoDev AI is its self-healing workflow.

Generated software does not always work correctly on the first attempt. Instead of immediately returning a failed project, AutoDev AI can analyze the failure and attempt a repair.

```text
Generated Project
       │
       ▼
Execute Project
       │
       ▼
Did it succeed?
   │         │
  Yes        No
   │         │
   │         ▼
   │    Capture Error
   │         │
   │         ▼
   │    Categorize Error
   │         │
   │         ▼
   │    Build Debug Context
   │         │
   │         ▼
   │      Fixer Agent
   │         │
   │         ▼
   │    Rebuild Project
   │         │
   │         ▼
   │       Retry
   │
   ▼
Testing
```

Similar retry behavior is available for testing and review stages.

The system tracks information such as:

- Number of attempts
- Number of retries
- Execution failures
- Test failures
- Repairs
- Repair history
- Debug information
- Final success/failure state

---

# 🤖 AI Agents

AutoDev AI separates responsibilities across specialized components.

## Planner Agent

The Planner Agent interprets the user's request and converts it into a structured project specification.

It determines information such as:

- Project title
- Description
- Project type
- Generation mode
- Programming language
- Expected files
- Development requirements

---

## Coder Agent

The Coder Agent generates the source code required to implement the plan.

Responsibilities include:

- Generating source files
- Creating tests
- Following the requested technology
- Producing complete project output
- Ensuring generated Python syntax is valid
- Rejecting unsafe Python dynamic execution patterns

---

## Fixer Agent

The Fixer Agent participates in autonomous repair.

When execution or testing fails, it receives debugging context and attempts to repair the project.

The repaired files are rebuilt before another execution/test attempt.

---

## Reviewer Agent

The Reviewer Agent performs a final AI-assisted review of generated source code.

The review can examine:

- Functional correctness
- Code structure
- Maintainability
- Error handling
- Testing
- Applicable security concerns

For Python projects, the reviewer is explicitly instructed to inspect unsafe dynamic execution such as `eval()` and `exec()` when untrusted input is involved.

---

## Evaluator

The Evaluator analyzes the final generated project and produces quality/evaluation information after execution, testing, review, and validation.

---

# 🌐 LLM Providers

AutoDev AI supports multiple LLM providers.

Current providers:

| Provider | Purpose |
|---|---|
| Google Gemini | Cloud LLM |
| OpenAI | Cloud LLM |
| OpenRouter | Multi-model cloud gateway |
| Ollama | Local LLM execution |

The active provider order is configurable.

Example:

```env
LLM_PRIORITY=gemini,openai,openrouter,ollama
```

This produces the fallback sequence:

```text
Gemini
   ↓
OpenAI
   ↓
OpenRouter
   ↓
Ollama
```

If an earlier provider is unavailable or cannot satisfy the request, the LLM infrastructure can move to another configured provider.

### Current model configuration

```env
GEMINI_MODEL=gemini-3.6-flash
OPENAI_MODEL=gpt-4.1-mini
OPENROUTER_MODEL=openrouter/free
OLLAMA_MODEL=qwen2.5-coder:7b
```

Provider availability and pricing depend on the external provider and the user's account/configuration.

---

# 🛡️ Generated Code Security

AutoDev AI includes generated-code validation before Python source code enters later stages of the pipeline.

## Python AST Validation

Generated Python files are parsed using Python's Abstract Syntax Tree.

This catches invalid Python syntax before the generated application proceeds.

## Dynamic Execution Protection

The Coder validation layer currently rejects direct calls to:

```python
eval(...)
exec(...)
```

If detected, generation is rejected with information about the affected file and line.

Example protection:

```text
Unsafe Python dynamic execution detected in main.py:
eval() at line 2.
```

The Coder prompts also explicitly instruct the model not to generate:

- `eval()` on generated or user-controlled input
- `exec()` on generated or user-controlled input
- Arbitrary dynamic code execution

The Reviewer Agent additionally checks for unsafe dynamic execution when reviewing Python applications.

> These safeguards improve generated-code safety but should not be considered a complete sandbox or a guarantee that arbitrary generated software is safe to execute.

---

# 🖥️ Frontend Features

The frontend provides the main user interface for AutoDev AI.

## AI Development Chat

Users can submit software-development requests and follow generation progress.

## Real-Time Progress

Run progress can be delivered to the frontend while the autonomous pipeline executes.

## Recent Chats

Recent development requests are stored and displayed in the sidebar.

Users can reopen previous runs without starting another generation.

Historical runs do not incorrectly reconnect to the live generation WebSocket.

## New Chat

Users can reset the current development session and begin a new request.

## Projects

The Projects interface allows users to inspect generated projects.

## Project Details

Generated project information and files can be viewed through the application.

## Preview

Supported generated applications can be previewed through the project preview functionality.

## Download

Generated projects can be downloaded for local development.

## History

Previous development runs can be inspected through the History interface.

## Settings

The Settings page displays authenticated account information including:

- Username
- Email
- Account ID
- Application information

It also supports signing out.

---

# ⚙️ Backend Features

The FastAPI backend provides:

- Authentication APIs
- Chat/generation APIs
- Run APIs
- Project APIs
- Project-file APIs
- Preview APIs
- Download APIs
- WebSocket progress
- Database persistence
- Background execution
- LLM routing
- Agent orchestration
- Retry management
- Execution management
- Testing
- Validation
- Evaluation
- Project building
- Generated-project storage

---

# 🛠️ Tech Stack

## Backend

| Technology | Usage |
|---|---|
| Python | Core backend and agent system |
| FastAPI | REST API |
| Uvicorn | ASGI server |
| Pydantic | Validation/configuration |
| Pydantic Settings | Environment configuration |
| SQLAlchemy | Database ORM |
| SQLite | Development database |
| PyJWT | JWT handling |
| Passlib / bcrypt | Authentication/password security |
| WebSockets | Real-time communication |
| Pytest | Automated testing |
| OpenAI SDK | OpenAI/OpenRouter integration |
| Google GenAI | Gemini integration |
| Ollama | Local LLM integration |

## Frontend

| Technology | Usage |
|---|---|
| React 19 | UI framework |
| Vite 8 | Development/build tooling |
| Tailwind CSS 4 | Styling |
| React Router | Client-side routing |
| Axios | API requests |
| Framer Motion | UI animations |
| Lucide React | Icons |
| React Markdown | Markdown rendering |
| React Hot Toast | Notifications |
| Socket.IO Client | Client communication support |

## Development / Infrastructure

- Git
- GitHub
- PowerShell
- Pytest
- ESLint
- Docker structure
- Python virtual environments

---

# 📂 Project Structure

```text
AutoDev-AI/
│
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── planner
│   │   │   ├── coder
│   │   │   ├── fixer
│   │   │   ├── reviewer
│   │   │   └── orchestrator
│   │   │
│   │   ├── api/
│   │   │   ├── auth
│   │   │   ├── chat
│   │   │   ├── projects
│   │   │   ├── project_files
│   │   │   ├── runs
│   │   │   ├── preview
│   │   │   └── download
│   │   │
│   │   ├── core/
│   │   ├── database/
│   │   ├── models/
│   │   └── services/
│   │       ├── auth/
│   │       ├── execution/
│   │       ├── llm/
│   │       ├── retry/
│   │       └── ...
│   │
│   ├── test/
│   ├── .env.example
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── context/
│   │   ├── hooks/
│   │   ├── pages/
│   │   └── ...
│   │
│   ├── package.json
│   └── vite.config.*
│
├── generated_projects/
├── database/
├── docker/
├── docs/
├── examples/
├── memory/
├── tests/
│
├── autodev.db
├── pytest.ini
├── .gitignore
└── README.md
```

> Some internal file names may evolve as development continues; this structure represents the major project areas.

---

# 📋 Prerequisites

Before running AutoDev AI, install:

- Python 3.12+ recommended
- Node.js
- npm
- Git

Optional:

- Ollama, if you want to use a local LLM
- Docker, for future/containerized workflows

You also need credentials for any cloud LLM providers you want to enable.

You do **not** need to configure every cloud provider. Configure the providers you intend to use and set `LLM_PRIORITY` accordingly.

---

# 📦 Installation

Clone the repository:

```bash
git clone https://github.com/saisanthosharyan/AutonomousAI.git
```

Enter the project:

```bash
cd AutonomousAI
```

---

# ⚙️ Environment Configuration

AutoDev AI loads backend configuration from environment variables.

The repository contains:

```text
backend/.env.example
```

Create:

```text
backend/.env
```

and configure the required values.

Example:

```env
# ==========================
# Application
# ==========================

PROJECT_NAME=AutoDev AI
PROJECT_VERSION=0.1.0
DEBUG=False

HOST=0.0.0.0
PORT=8000

SECRET_KEY=CHANGE_ME_TO_A_STRONG_RANDOM_SECRET
JWT_EXPIRATION_HOURS=24

# ==========================
# LLM Configuration
# ==========================

LLM_PRIORITY=gemini,openai,openrouter,ollama

# Gemini
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-3.6-flash

# OpenAI
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
OPENAI_MODEL=gpt-4.1-mini

# OpenRouter
OPENROUTER_API_KEY=YOUR_OPENROUTER_API_KEY
OPENROUTER_MODEL=openrouter/free

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b

# ==========================
# Database
# ==========================

DATABASE_URL=sqlite:///../autodev.db

# ==========================
# Vector Database
# ==========================

CHROMA_DB_PATH=./chroma_db

# ==========================
# Retry Configuration
# ==========================

MAX_RETRIES=3
RETRY_DELAY=2

# ==========================
# Run Concurrency
# ==========================

MAX_CONCURRENT_RUNS=2

# ==========================
# Logging
# ==========================

LOG_LEVEL=INFO
```

Never commit real API keys or production secrets.

---

# ▶️ Running the Backend

Move into the backend directory:

```powershell
cd backend
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Ensure your `.env` file is configured.

Start AutoDev AI:

```powershell
python -m uvicorn app.main:app --reload
```

The backend should be available at:

```text
http://127.0.0.1:8000
```

---

# 💻 Running the Frontend

Open another terminal and move into the frontend:

```powershell
cd frontend
```

Install dependencies:

```powershell
npm install
```

Start the Vite development server:

```powershell
npm run dev
```

The frontend should be available at:

```text
http://localhost:5173
```

---

# 🦙 Using Ollama

Ollama can be used as a local LLM provider.

The default configuration is:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b
```

Ensure Ollama is installed and the configured model is available locally before enabling it in the fallback chain.

Example priority:

```env
LLM_PRIORITY=gemini,openai,openrouter,ollama
```

Or for local-only experimentation:

```env
LLM_PRIORITY=ollama
```

---

# 🧪 Testing

## Backend

Move into:

```powershell
cd backend
```

Run the regression suite:

```powershell
python -m pytest
```

Latest verified regression result during current development:

```text
162 passed
```

The current suite includes coverage for areas such as:

- Orchestrator success flow
- Planner failures
- Coder failures
- Builder failures
- Execution/retry failures
- Validation failures
- Testing failures
- Review failures
- Evaluation failures
- Pipeline metrics
- Shared memory behavior
- API behavior
- Run handling
- WebSockets
- Project building
- Execution managers
- Python execution
- Node execution
- Java execution
- C++ execution
- LLM security
- User LLM keys
- Retry management
- Self-healing integration
- Generated Python security validation

Coder security regression tests verify:

- `eval()` is rejected
- `exec()` is rejected
- Normal safe Python is accepted

A real Gemini repair E2E test is also available for exercising autonomous repair behavior when configured with appropriate credentials.

---

## Frontend

Run:

```powershell
npm run lint
```

Latest verified result:

```text
PASS
```

Build the production frontend:

```powershell
npm run build
```

Latest verified result:

```text
Vite production build successful
1861 modules transformed
```

---

# 🔐 Authentication

AutoDev AI includes JWT-based user authentication.

The authentication system supports authenticated API access and user-specific project operations.

Project-file access includes ownership verification.

Conceptually:

```text
Authenticated User
       │
       ▼
Requested Project
       │
       ▼
Database Ownership Check
       │
   ┌───┴───┐
   │       │
 Owned   Not Owned
   │       │
   ▼       ▼
Allow     404
```

This prevents a user from simply supplying another generated project's folder name to access its files through the project-files API.

---

# 📁 Generated Projects

Generated applications are stored under the configured generated-project directory.

The backend configuration derives the default project directory from the repository structure.

Generated project operations include:

- Build
- Rebuild
- Execute
- Test
- Review
- Validate
- Evaluate
- Browse files
- Preview
- Download

Internal AutoDev debugging artifacts such as `.autodev_debug` are excluded from the user-facing project-file listing.

---

# 📊 Run Information

A completed autonomous run can contain information about:

```text
Plan
Execution
Tests
Validation
Review
Evaluation
Improved Code
Retry Statistics
Repair History
Pipeline Metrics
Generated Project
```

This provides more visibility than returning only the final generated source code.

---

# ⚡ Real-Time Progress

AutoDev AI provides progress updates while the autonomous pipeline runs.

The frontend can show stages such as:

```text
Planning
    ↓
Generating Code
    ↓
Building
    ↓
Executing
    ↓
Testing
    ↓
Reviewing
    ↓
Validating
    ↓
Evaluating
    ↓
Complete
```

Historical completed runs are separated from active WebSocket generation behavior so reopening an old chat does not unnecessarily start a live run connection.

---

# 🧾 Recent Chats & History

The frontend maintains recent development requests and allows users to reopen previous work.

Recent chat information is persisted in browser storage and restored in the sidebar.

The application also provides run/project history backed by backend data.

This allows users to move between:

```text
New Development Request
Previous Chat
Generated Project
Run History
Project Details
```

without treating every navigation action as a new generation request.

---

# 📈 Current Status

AutoDev AI's core autonomous development pipeline is operational.

## Implemented

- [x] FastAPI backend
- [x] React frontend
- [x] User authentication
- [x] JWT authorization
- [x] Planner Agent
- [x] Coder Agent
- [x] Fixer Agent
- [x] Reviewer Agent
- [x] Agent orchestration
- [x] Project Builder
- [x] Generated-project persistence
- [x] Python execution
- [x] Multi-language execution infrastructure
- [x] Automated testing
- [x] Execution retry
- [x] Test retry
- [x] Review retry
- [x] Autonomous repair
- [x] Project validation
- [x] Project evaluation
- [x] Repair history
- [x] Pipeline metrics
- [x] WebSocket progress
- [x] Background run handling
- [x] Run history
- [x] Projects interface
- [x] Project details
- [x] Project-file browser
- [x] Project preview
- [x] Project download
- [x] Recent chats
- [x] Historical chat restoration
- [x] Settings page
- [x] Gemini integration
- [x] OpenAI integration
- [x] OpenRouter integration
- [x] Ollama integration
- [x] LLM fallback
- [x] Python AST validation
- [x] `eval()` protection
- [x] `exec()` protection
- [x] Project ownership checks
- [x] Backend regression suite
- [x] Frontend lint validation
- [x] Frontend production build validation

---

# 🏗️ Architecture

At a high level:

```text
                    ┌────────────────────┐
                    │   React Frontend   │
                    │                    │
                    │ Chat / Projects    │
                    │ History / Settings │
                    └─────────┬──────────┘
                              │
                         HTTP / WS
                              │
                              ▼
                    ┌────────────────────┐
                    │  FastAPI Backend   │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │ Agent Orchestrator │
                    └─────────┬──────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
          Planner           Coder          Reviewer
              │               │               │
              └───────────────┼───────────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │  Project Builder   │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │ Execution / Tests  │
                    └─────────┬──────────┘
                              │
                        Failure?
                         │    │
                        Yes   No
                         │    │
                         ▼    │
                    ┌──────────────┐
                    │ Retry/Fixer  │
                    └──────┬───────┘
                           │
                           └──────► Rebuild
                              │
                              ▼
                    ┌────────────────────┐
                    │ Validate/Evaluate  │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │ SQLite / Projects  │
                    │ Runs / Memory      │
                    └────────────────────┘
```

---

# 🎯 Project Goal

The long-term goal of AutoDev AI is to build an AI system that behaves less like a code-completion chatbot and more like an autonomous software engineer.

Traditional coding assistant:

```text
Prompt
  ↓
Code
```

AutoDev AI:

```text
Requirement
    ↓
Understand
    ↓
Plan
    ↓
Generate
    ↓
Build
    ↓
Execute
    ↓
Test
    ↓
Detect Problems
    ↓
Debug
    ↓
Repair
    ↓
Review
    ↓
Validate
    ↓
Evaluate
    ↓
Deliver
```

The project focuses on making AI-generated software more autonomous, testable, observable, repairable, and useful.

---

# 🔒 Security Notes

AutoDev AI generates and executes software.

Generated code should therefore be treated as potentially unsafe.

The project currently includes security improvements such as AST validation and unsafe dynamic execution checks, but these controls do not replace strong operating-system-level isolation.

For production or untrusted public usage, additional isolation should be considered, including:

- Containerized execution
- Filesystem isolation
- Process restrictions
- Resource limits
- Network restrictions
- Dependency-installation controls
- Secret isolation
- Stronger sandboxing

Never expose development API keys, `.env` files, database secrets, or authentication secrets in generated projects or Git commits.

---

# 🗺️ Development Roadmap

Areas for continued improvement include:

- Stronger generated-code sandboxing
- Broader end-to-end generation coverage
- More generated-project types
- Improved autonomous debugging
- More robust dependency handling
- Better execution isolation
- Expanded security validation
- Improved project evaluation
- More frontend observability
- Production deployment configuration
- Containerized execution
- Performance optimization
- Expanded documentation

---

# 🧪 Verified Development Baseline

At the latest verified checkpoint:

```text
Backend
-------
162 tests passed

Frontend
--------
ESLint passed
Vite production build passed

Repository
----------
main branch
working tree clean before documentation updates
```

The test count represents the current development checkpoint and may increase as new regression tests are added.

---

# ⚠️ Project Maturity

AutoDev AI is under active development.

It is suitable for experimentation, development, learning, and continued research into autonomous software engineering workflows.

It should not yet be treated as a fully isolated production sandbox for executing arbitrary untrusted code.

---

# 👨‍💻 Author

**Santhosh Aryan**

GitHub:

https://github.com/saisanthosharyan

Project Repository:

https://github.com/saisanthosharyan/AutonomousAI

---

# ⭐ Support

If you find AutoDev AI interesting, consider starring the repository.

Contributions, testing, bug reports, and ideas for improving autonomous software engineering workflows are welcome.

---

## 🤖 AutoDev AI

**From requirement to working software through autonomous AI engineering.**

```text
Prompt → Plan → Code → Build → Execute → Test → Repair → Review → Validate → Deliver
```
