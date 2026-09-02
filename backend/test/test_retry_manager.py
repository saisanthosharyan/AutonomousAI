import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.services.retry.retry_manager import (
    RetryManager,
    categorize_error,
)


def create_project(tmp_path):
    project_path = tmp_path / "project"
    project_path.mkdir()

    return {
        "title": "Retry Test Project",
        "project_path": str(project_path),
        "zip_path": str(tmp_path / "project.zip"),
    }


def create_memory():
    memory = MagicMock()
    memory.save = MagicMock()
    return memory


def test_categorize_error():
    assert categorize_error("SyntaxError: invalid syntax") == "SyntaxError"
    assert categorize_error("NameError: name x is not defined") == "NameError"
    assert (
        categorize_error(
            "ModuleNotFoundError: No module named 'requests'"
        )
        == "ModuleNotFoundError"
    )
    assert categorize_error("TypeError: invalid type") == "TypeError"
    assert categorize_error("ValueError: bad value") == "ValueError"
    assert categorize_error("something unexpected") == "RuntimeError"
    assert categorize_error("") == "Unknown"


def test_retry_manager_success_without_repair(tmp_path):
    project = create_project(tmp_path)
    memory = create_memory()

    manager = RetryManager(
        max_retries=3,
        memory=memory,
    )

    manager.executor.run = MagicMock(
        return_value={
            "success": True,
            "stdout": "Hello",
            "stderr": "",
            "return_code": 0,
            "execution_time": 0.01,
        }
    )

    result = asyncio.run(
        manager.execute_with_retry(
            project=project,
            code="print('hello')",
        )
    )

    execution_result = result[0]
    current_project = result[1]
    current_code = result[2]
    debug_report = result[3]
    retry_stats = result[4]

    assert execution_result["success"] is True
    assert current_project == project
    assert current_code == "print('hello')"

    assert retry_stats["attempts"] == 1
    assert retry_stats["repairs"] == 0
    assert retry_stats["execution_failures"] == 0
    assert retry_stats["successful"] is True

    assert debug_report["retry_stats"] == retry_stats

    manager.executor.run.assert_called_once()


def test_retry_manager_repairs_and_retries_successfully(
    tmp_path,
):
    project = create_project(tmp_path)
    memory = create_memory()

    manager = RetryManager(
        max_retries=3,
        memory=memory,
    )

    broken_code = "print(name)"
    fixed_code = "name = 'Santhosh'\nprint(name)"

    execution_results = [
        {
            "success": False,
            "stdout": "",
            "stderr": (
                "NameError: name 'name' is not defined"
            ),
            "return_code": 1,
            "execution_time": 0.01,
        },
        {
            "success": True,
            "stdout": "Santhosh",
            "stderr": "",
            "return_code": 0,
            "execution_time": 0.01,
        },
    ]

    manager.executor.run = MagicMock(
        side_effect=execution_results
    )

    manager.debugger.analyze = MagicMock(
        return_value={
            "category": "NameError",
            "summary": "Variable name is not defined.",
            "stderr": (
                "NameError: name 'name' is not defined"
            ),
        }
    )

    manager.fixer.run = AsyncMock(
        return_value=fixed_code
    )

    manager.builder.rebuild = MagicMock(
        return_value=project
    )

    result = asyncio.run(
        manager.execute_with_retry(
            project=project,
            code=broken_code,
        )
    )

    execution_result = result[0]
    current_project = result[1]
    current_code = result[2]
    debug_report = result[3]
    retry_stats = result[4]

    assert execution_result["success"] is True
    assert current_project == project
    assert current_code == fixed_code

    assert retry_stats["attempts"] == 2
    assert retry_stats["repairs"] == 1
    assert retry_stats["execution_failures"] == 1
    assert retry_stats["repeated_errors_detected"] == 0
    assert retry_stats["successful"] is True

    assert len(
        debug_report["repair_history"]
    ) == 1

    repair = debug_report["repair_history"][0]

    assert repair["attempt"] == 1
    assert repair["category"] == "NameError"
    assert repair["error"] == (
        "NameError: name 'name' is not defined"
    )

    manager.executor.run.assert_called()
    assert manager.executor.run.call_count == 2

    manager.debugger.analyze.assert_called_once()

    manager.fixer.run.assert_awaited_once()

    manager.builder.rebuild.assert_called_once_with(
        project["project_path"],
        fixed_code,
    )


def test_retry_manager_stops_after_max_retries(
    tmp_path,
):
    project = create_project(tmp_path)
    memory = create_memory()

    manager = RetryManager(
        max_retries=3,
        memory=memory,
    )

    manager.executor.run = MagicMock(
        return_value={
            "success": False,
            "stdout": "",
            "stderr": (
                "ValueError: invalid value"
            ),
            "return_code": 1,
            "execution_time": 0.01,
        }
    )

    manager.debugger.analyze = MagicMock(
        return_value={
            "category": "ValueError",
            "summary": "Invalid value.",
        }
    )

    repair_versions = [
        "print('repair 1')",
        "print('repair 2')",
    ]

    manager.fixer.run = AsyncMock(
        side_effect=repair_versions
    )

    manager.builder.rebuild = MagicMock(
        return_value=project
    )

    result = asyncio.run(
        manager.execute_with_retry(
            project=project,
            code="print('broken')",
        )
    )

    execution_result = result[0]
    debug_report = result[3]
    retry_stats = result[4]

    assert execution_result["success"] is False

    assert retry_stats["attempts"] == 2
    assert retry_stats["execution_failures"] == 2
    assert retry_stats["repairs"] == 1
    assert retry_stats["successful"] is False

    assert manager.executor.run.call_count == 2
    assert manager.fixer.run.await_count == 1
    assert manager.builder.rebuild.call_count == 1

    assert len(
        debug_report["repair_history"]
    ) == 1


def test_retry_manager_detects_repeated_error(
    tmp_path,
):
    project = create_project(tmp_path)
    memory = create_memory()

    manager = RetryManager(
        max_retries=3,
        memory=memory,
    )

    repeated_error = (
        "NameError: name 'missing' is not defined"
    )

    manager.executor.run = MagicMock(
        return_value={
            "success": False,
            "stdout": "",
            "stderr": repeated_error,
            "return_code": 1,
            "execution_time": 0.01,
        }
    )

    manager.debugger.analyze = MagicMock(
        return_value={
            "category": "NameError",
            "summary": "Missing variable.",
        }
    )

    manager.fixer.run = AsyncMock(
        return_value=(
            "missing = 'fixed'\n"
            "print(missing)"
        )
    )

    manager.builder.rebuild = MagicMock(
        return_value=project
    )

    result = asyncio.run(
        manager.execute_with_retry(
            project=project,
            code="print(missing)",
        )
    )

    execution_result = result[0]
    debug_report = result[3]
    retry_stats = result[4]

    assert execution_result["success"] is False

    assert retry_stats["attempts"] == 2
    assert retry_stats["execution_failures"] == 2
    assert retry_stats["repairs"] == 1
    assert retry_stats["repeated_errors_detected"] == 1
    assert retry_stats["successful"] is False

    assert len(
        debug_report["repair_history"]
    ) == 1

    assert (
        debug_report["summary"]
        == "Repeated identical error across execution attempts."
    )

    assert manager.executor.run.call_count == 2
    assert manager.fixer.run.await_count == 1
    assert manager.builder.rebuild.call_count == 1


def test_retry_manager_rejects_empty_project():
    manager = RetryManager(
        memory=create_memory()
    )

    try:
        asyncio.run(
            manager.execute_with_retry(
                project={},
                code="print('hello')",
            )
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == (
            "Project information cannot be empty."
        )


def test_retry_manager_rejects_missing_project_path():
    manager = RetryManager(
        memory=create_memory()
    )

    try:
        asyncio.run(
            manager.execute_with_retry(
                project={
                    "title": "Test",
                },
                code="print('hello')",
            )
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == (
            "Project path is missing."
        )


def test_retry_manager_rejects_empty_code(tmp_path):
    manager = RetryManager(
        memory=create_memory()
    )

    project = create_project(tmp_path)

    try:
        asyncio.run(
            manager.execute_with_retry(
                project=project,
                code="",
            )
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == (
            "Generated project code cannot be empty."
        )
