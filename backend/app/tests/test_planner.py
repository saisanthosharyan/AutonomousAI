import pytest

from app.agents.planner import PlannerAgent


@pytest.mark.asyncio
async def test_planner_generates_plan():

    planner = PlannerAgent()

    plan = await planner.run("Build a Todo App")

    assert plan is not None
    assert plan != ""