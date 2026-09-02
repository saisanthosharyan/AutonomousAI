from pathlib import Path

import pytest

from app.agents.fixer_agent import FixerAgent
from app.services.debugger.debug_manager import DebugManager
from app.services.execution.execution_manager import ExecutionManager
from app.services.retry.retry_manager import RetryManager


class FakeLLM:
    """Deterministic LLM used only for the integration test."""

    async def generate(self, prompt: str) -> str:
        return """FILE: main.py

def main():
    print("Hello AutoDev self healing")

if __name__ == "__main__":
    main()
"""


@pytest.mark.asyncio
async def test_real_self_healing_pipeline(tmp_path: Path):
    """
    Verify the real self-healing pipeline:

    ExecutionManager
        -> DebugManager
        -> FixerAgent
        -> ProjectBuilder
        -> ExecutionManager
    """

    project = tmp_path / "broken_project"
    project.mkdir()

    main_file = project / "main.py"

    # Deliberately broken program.
    main_file.write_text(
        'print(undefined_variable)\n',
        encoding="utf-8",
    )

    # Use the real RetryManager and its real dependencies,
    # but replace only the LLM with a deterministic fake.
    retry_manager = RetryManager(max_retries=3)

    retry_manager.fixer = FixerAgent(
        llm=FakeLLM()
    )

    execution_result, project_path, final_code, debug_report, retry_stats = (
    await retry_manager.execute_with_retry(
        project={
            "project_path": str(project),
            "project_name": project.name,
        },
        code='FILE: main.py\n\nprint(undefined_variable)\n',
    )
)

    # ------------------------------------------------------
    # Final execution
    # ------------------------------------------------------

    assert execution_result["success"] is True

    assert "Hello AutoDev self healing" in execution_result["stdout"]

    # ------------------------------------------------------
    # Retry statistics
    # ------------------------------------------------------

    assert retry_stats["attempts"] == 2
    assert retry_stats["execution_failures"] == 1
    assert retry_stats["repairs"] == 1

    # ------------------------------------------------------
    # Repair history
    # ------------------------------------------------------

    assert len(debug_report["repair_history"]) == 1

    # ------------------------------------------------------
    # Verify the real file was actually rebuilt
    # ------------------------------------------------------

    final_source = main_file.read_text(
        encoding="utf-8"
    )

    assert "undefined_variable" not in final_source
    assert "Hello AutoDev self healing" in final_source