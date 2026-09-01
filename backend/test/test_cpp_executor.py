from pathlib import Path

from app.services.execution.cpp_executor import CPPExecutor


def create_project(tmp_path: Path, files: dict[str, str]) -> Path:
    project = tmp_path / "project"
    project.mkdir()

    for name, content in files.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return project


def test_simple_cpp_project(tmp_path):
    project = create_project(
        tmp_path,
        {
            "main.cpp": """
#include <iostream>

int main() {
    std::cout << "hello cpp";
    return 0;
}
"""
        },
    )

    result = CPPExecutor().run(str(project))

    assert result["success"] is True
    assert "hello cpp" in result["stdout"]
    assert result["return_code"] == 0


def test_cpp_project_with_multiple_files(tmp_path):
    project = create_project(
        tmp_path,
        {
            "main.cpp": """
#include <iostream>

int add(int a, int b);

int main() {
    std::cout << add(10, 20);
    return 0;
}
""",
            "math.cpp": """
int add(int a, int b) {
    return a + b;
}
""",
        },
    )

    result = CPPExecutor().run(str(project))

    assert result["success"] is True
    assert "30" in result["stdout"]
    assert result["return_code"] == 0


def test_cpp_syntax_error(tmp_path):
    project = create_project(
        tmp_path,
        {
            "main.cpp": """
#include <iostream>

int main() {
    std::cout << "broken"
    return 0;
}
"""
        },
    )

    result = CPPExecutor().run(str(project))

    assert result["success"] is False
    assert result["return_code"] != 0
    assert result["stderr"]


def test_no_cpp_files(tmp_path):
    project = create_project(
        tmp_path,
        {
            "README.md": "No C++ source here."
        },
    )

    result = CPPExecutor().run(str(project))

    assert result["success"] is False
    assert "No C++ source files found" in result["stderr"]


def test_missing_project(tmp_path):
    project = tmp_path / "missing"

    result = CPPExecutor().run(str(project))

    assert result["success"] is False
    assert result["return_code"] == -1
    assert "Project does not exist" in result["stderr"]


def test_cpp_project_with_output(tmp_path):
    project = create_project(
        tmp_path,
        {
            "main.cpp": """
#include <iostream>

int main() {
    for (int i = 1; i <= 3; i++) {
        std::cout << i << " ";
    }

    return 0;
}
"""
        },
    )

    result = CPPExecutor().run(str(project))

    assert result["success"] is True
    assert "1 2 3" in result["stdout"]


def test_cpp_execution_time_is_recorded(tmp_path):
    project = create_project(
        tmp_path,
        {
            "main.cpp": """
#include <iostream>

int main() {
    std::cout << "timed";
    return 0;
}
"""
        },
    )

    result = CPPExecutor().run(str(project))

    assert result["success"] is True
    assert result["execution_time"] >= 0