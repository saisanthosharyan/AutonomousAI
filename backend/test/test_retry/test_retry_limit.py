import pytest

from app.services.retry.retry_manager import RetryManager


@pytest.mark.asyncio
async def test_retry_manager_respects_max_retries(monkeypatch, tmp_path):

    manager = RetryManager(max_retries=3)

    calls = {
        "executions": 0,
        "repairs": 0,
    }

    class FakeExecutor:

        def run(self, project_path):
            calls["executions"] += 1

            return {
                "success": False,
                "stdout": "",
                "stderr": "forced test failure",
                "return_code": 1,
                "execution_time": 0,
            }

    async def fake_fixer_run(*args, **kwargs):

        calls["repairs"] += 1

        return (
            "FILE: app.py\n\n"
            "def test_function():\n"
            "    return 1"
        )

    manager.executor = FakeExecutor()
    manager.fixer.run = fake_fixer_run

    project_path = tmp_path / "project"
    project_path.mkdir()

    project = {
        "project_path": str(project_path),
        "title": "Retry Limit Test",
    }

    result = await manager.execute_with_retry(
        project=project,
        code=(
            "FILE: app.py\n\n"
            "def test_function():\n"
            "    return 1"
        ),
    )

    retry_stats = result[4]

    assert retry_stats["attempts"] <= 3
    assert calls["executions"] <= 3
    assert calls["repairs"] <= 2