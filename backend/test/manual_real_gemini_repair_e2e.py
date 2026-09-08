from pathlib import Path

import pytest

from app.agents.fixer_agent import FixerAgent
from app.services.retry.retry_manager import RetryManager


@pytest.mark.asyncio
async def test_real_gemini_autonomous_repair(tmp_path: Path):
    """
    Real autonomous repair E2E.

    Uses:
        real ExecutionManager
        real DebugManager
        real FixerAgent
        real Gemini LLM
        real ProjectBuilder
        real retry loop

    The project is intentionally broken.
    Gemini must repair it autonomously.
    """

    project = tmp_path / "broken_gemini_project"
    project.mkdir()

    main_file = project / "main.py"

    # Deliberately broken source.
    main_file.write_text(
        'print(undefined_variable)\n',
        encoding="utf-8",
    )

    broken_code = """FILE: main.py

print(undefined_variable)
"""

    retry_manager = RetryManager(
        max_retries=3,
    )

    # Explicitly use the application-configured Gemini provider.
    # This is a real Gemini request, not a fake LLM.
    from app.services.llm.router import LLMRouter

    retry_manager.fixer = FixerAgent(
        llm=LLMRouter.get_llm(
            provider="gemini",
        )
    )

    (
        execution_result,
        final_project,
        final_code,
        debug_report,
        retry_stats,
    ) = await retry_manager.execute_with_retry(
        project={
            "project_path": str(project),
            "project_name": project.name,
        },
        code=broken_code,
    )

    print("\n========== REAL GEMINI REPAIR E2E ==========")
    print("Execution success:", execution_result["success"])
    print("Retry stats:", retry_stats)
    print("Repair history:", debug_report.get("repair_history"))
    print("Final project:", final_project)
    print("============================================\n")

    assert execution_result["success"] is True

    assert retry_stats["attempts"] >= 2
    assert retry_stats["execution_failures"] >= 1
    assert retry_stats["repairs"] >= 1

    final_source = main_file.read_text(
        encoding="utf-8"
    )

    assert "undefined_variable =" in final_source
    assert "print(undefined_variable)" in final_source
    assert final_source.strip()

    assert "FILE:" not in final_source

    assert final_code.strip()

    assert debug_report.get("repair_history")


