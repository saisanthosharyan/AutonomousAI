import pytest

from app.agents.planner import PlannerAgent
from app.models.task import Task


class FakeLLM:
    async def generate_structured(self, prompt, schema):
        return Task(
            title="Todo App",
            description="A simple todo application.",
            project_type="Web Application",
            generation_mode="website",
            requested_files=[
                "index.html",
                "style.css",
                "script.js",
            ],
            language="JavaScript",
            framework=None,
            database=None,
            authentication=None,
            deployment=None,
            architecture="Simple frontend architecture",
            testing=None,
            dependencies=[],
            features=[
                "Add todos",
                "Complete todos",
                "Delete todos",
            ],
            steps=[
                "Create the HTML structure",
                "Create responsive styles",
                "Implement todo functionality",
            ],
        )


@pytest.mark.asyncio
async def test_planner_generates_plan():
    planner = PlannerAgent(llm=FakeLLM())

    plan = await planner.run("Build a Todo App")

    assert plan is not None
    assert plan.title == "Todo App"
    assert plan.requested_files == [
        "index.html",
        "style.css",
        "script.js",
    ]
    assert plan.steps
