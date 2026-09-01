from pathlib import Path

from app.services.execution.java_executor import JavaExecutor


def create_project(tmp_path: Path, files: dict[str, str]) -> Path:
    project = tmp_path / "project"
    project.mkdir()

    for name, content in files.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return project


def test_simple_java_project(tmp_path):
    project = create_project(
        tmp_path,
        {
            "Main.java": """
public class Main {
    public static void main(String[] args) {
        System.out.println("hello java");
    }
}
"""
        },
    )

    result = JavaExecutor().run(str(project))

    assert result["success"] is True
    assert "hello java" in result["stdout"]
    assert result["return_code"] == 0


def test_java_project_with_multiple_classes(tmp_path):
    project = create_project(
        tmp_path,
        {
            "Main.java": """
public class Main {
    public static void main(String[] args) {
        System.out.println(Greeter.message());
    }
}
""",
            "Greeter.java": """
public class Greeter {
    public static String message() {
        return "multiple classes work";
    }
}
""",
        },
    )

    result = JavaExecutor().run(str(project))

    assert result["success"] is True
    assert "multiple classes work" in result["stdout"]


def test_java_package_project(tmp_path):
    project = create_project(
        tmp_path,
        {
            "src/com/example/Main.java": """
package com.example;

public class Main {
    public static void main(String[] args) {
        System.out.println("package works");
    }
}
"""
        },
    )

    result = JavaExecutor().run(str(project))

    assert result["success"] is True
    assert "package works" in result["stdout"]
    assert result["return_code"] == 0


def test_java_syntax_error(tmp_path):
    project = create_project(
        tmp_path,
        {
            "Main.java": """
public class Main {
    public static void main(String[] args) {
        System.out.println("broken")
    }
}
"""
        },
    )

    result = JavaExecutor().run(str(project))

    assert result["success"] is False
    assert result["return_code"] != 0
    assert result["stderr"]


def test_no_java_files(tmp_path):
    project = create_project(
        tmp_path,
        {
            "README.md": "No Java source here."
        },
    )

    result = JavaExecutor().run(str(project))

    assert result["success"] is False
    assert "No Java source files found" in result["stderr"]


def test_java_without_main_class(tmp_path):
    project = create_project(
        tmp_path,
        {
            "Utility.java": """
public class Utility {
    public static String hello() {
        return "hello";
    }
}
"""
        },
    )

    result = JavaExecutor().run(str(project))

    assert result["success"] is False
    assert "Main class not found" in result["stderr"]


def test_missing_project(tmp_path):
    project = tmp_path / "missing"

    result = JavaExecutor().run(str(project))

    assert result["success"] is False
    assert result["return_code"] == -1
    assert "Project does not exist" in result["stderr"]