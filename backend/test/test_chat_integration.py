from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.task import Task


class FakeLLM:
    async def generate_structured(self, prompt, schema):
        return Task(
            title="Simple Python Application",
            description=(
                "A simple Python application generated "
                "for integration testing."
            ),
            project_type="CLI",
            language="Python",
            framework=None,
            database=None,
            authentication=None,
            deployment=None,
            architecture="Simple modular architecture",
            testing="pytest",
            dependencies=["pytest"],
            features=[
                "Print a greeting",
            ],
            steps=[
                "Create the Python entry point",
                "Create automated tests",
                "Execute the application",
                "Validate the project",
            ],
        )

    async def generate(self, prompt):
        # Reviewer response
        if "Principal Software Architect" in prompt:
            return """
## Overall Summary

The generated Python project is functional, simple,
and suitable for the integration test.

---

## Strengths

- Clear project structure
- Simple executable entry point
- Basic test coverage
- No hardcoded secrets

---

## Problems Found

No significant problems were found.

---

## Possible Runtime Errors

No known runtime errors were identified.

---

## Security Review

No obvious security vulnerabilities were identified.

---

## Performance Review

The project is small and has no meaningful
performance bottlenecks.

---

## Code Quality

The project follows a simple and maintainable structure.

---

## Missing Files

No critical files are missing for this application.

---

## Final Suggestions

Add more automated tests and CI/CD configuration
for production usage.

---

## Final Score

9/10
"""

        # Coder response
        return """
FILE: main.py
def main():
    return "Hello from AutoDev integration"


if __name__ == "__main__":
    print(main())


FILE: test_main.py
from main import main


def test_main():
    assert main() == "Hello from AutoDev integration"


FILE: README.md
# AutoDev Integration Test

A deterministic integration test project.


FILE: requirements.txt
pytest


FILE: .gitignore
__pycache__/
.pytest_cache/
"""


def test_chat_full_pipeline(tmp_path):
    fake_llm = FakeLLM()

    history = []

    with (
        patch(
            "app.agents.planner.LLMRouter.get_llm",
            return_value=fake_llm,
        ),
        patch(
            "app.agents.coder.LLMRouter.get_llm",
            return_value=fake_llm,
        ),
        patch(
            "app.agents.reviewer.LLMRouter.get_llm",
            return_value=fake_llm,
        ),
        patch(
            "app.agents.orchestrator.SessionLocal",
        ),
        patch(
            "app.agents.orchestrator.create_project",
            return_value=None,
        ),
        patch(
            "app.api.chat.get_history",
            return_value=history,
        ),
        patch(
            "app.api.chat.add_message",
        ),
    ):
        client = TestClient(app)

        response = client.post(
            "/chat",
            json={
                "session_id": "integration-test-session",
                "message": (
                    "Create a simple Python application "
                    "that prints a greeting."
                ),
            },
        )

    # ------------------------------------------------------------------
    # HTTP response
    # ------------------------------------------------------------------

    assert response.status_code == 200

    data = response.json()

    # ------------------------------------------------------------------
    # Basic response
    # ------------------------------------------------------------------

    assert data["session_id"] == "integration-test-session"

    # ------------------------------------------------------------------
    # Complete pipeline response sections
    # ------------------------------------------------------------------

    assert "plan" in data
    assert "project" in data
    assert "execution" in data
    assert "validation" in data
    assert "tests" in data
    assert "debug_report" in data
    assert "retry_stats" in data
    assert "review" in data
    assert "evaluation" in data
    assert "improved_code" in data
    assert "metrics" in data

    # ------------------------------------------------------------------
    # Project creation
    # ------------------------------------------------------------------

    assert data["project"]["project_path"]

    # ------------------------------------------------------------------
    # Pipeline stage results
    # ------------------------------------------------------------------

    assert data["plan"] is not None
    assert data["execution"] is not None
    assert data["validation"] is not None
    assert data["tests"] is not None
    assert data["review"]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    assert data["execution"]["success"] is True
    assert data["execution"]["return_code"] == 0

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    assert data["validation"]["valid"] is True

    # ------------------------------------------------------------------
    # Automated tests
    # ------------------------------------------------------------------

    assert data["tests"]["success"] is True
    assert data["tests"]["return_code"] == 0

    # ------------------------------------------------------------------
    # Reviewer
    # ------------------------------------------------------------------

    assert isinstance(data["review"], str)
    assert len(data["review"].strip()) > 0
    assert "Final Score" in data["review"]
    assert "9/10" in data["review"]

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    assert data["evaluation"] is not None

    # ------------------------------------------------------------------
    # Entire autonomous pipeline
    # ------------------------------------------------------------------

    assert data["success"] is True