from pathlib import Path

from app.services.execution.execution_manager import ExecutionManager


def create_project(tmp_path: Path, files: dict[str, str]) -> Path:
    project = tmp_path / "project"
    project.mkdir()

    for name, content in files.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return project


def test_python_project_executes(tmp_path):
    project = create_project(
        tmp_path,
        {
            "main.py": 'print("hello from autodev")',
        },
    )

    manager = ExecutionManager()

    result = manager.run(str(project))

    assert result.project_type == "python"
    assert result.success is True
    assert "hello from autodev" in result.stdout
    assert result.return_code == 0


def test_python_project_with_tests(tmp_path):
    project = create_project(
        tmp_path,
        {
            "app.py": """
def add(a, b):
    return a + b
""",
            "tests/test_app.py": """
from app import add


def test_add():
    assert add(2, 3) == 5
""",
        },
    )

    manager = ExecutionManager()

    result = manager.run(str(project))

    assert result.project_type == "python"
    assert result.success is True
    assert result.return_code == 0


def test_python_syntax_error_is_detected(tmp_path):
    project = create_project(
        tmp_path,
        {
            "main.py": """
def broken(
    print("broken")
""",
        },
    )

    manager = ExecutionManager()

    result = manager.run(str(project))

    assert result.success is False
    assert result.return_code != 0
    assert result.stderr


def test_unknown_project_returns_failure(tmp_path):
    project = create_project(
        tmp_path,
        {
            "README.md": "# Nothing runnable here",
        },
    )

    manager = ExecutionManager()

    result = manager.run(str(project))

    assert result.success is False
    assert result.project_type == "unknown"


def test_missing_project_fails(tmp_path):
    manager = ExecutionManager()

    result = manager.run(
        str(tmp_path / "does_not_exist")
    )

    assert result.success is False
    assert result.return_code == -1


def test_available_executors():
    manager = ExecutionManager()

    executors = manager.available_executors()

    assert "python" in executors
    assert "node" in executors
    assert "java" in executors
    assert "cpp" in executors
    assert "docker" in executors