from pathlib import Path

from app.services.execution.python_executor import PythonExecutor


def create_project(tmp_path: Path, files: dict[str, str]) -> Path:
    project = tmp_path / "project"
    project.mkdir()

    for name, content in files.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return project


def test_simple_python_script(tmp_path):
    project = create_project(
        tmp_path,
        {
            "main.py": 'print("hello")',
        },
    )

    result = PythonExecutor().run(str(project))

    assert result["success"] is True
    assert "hello" in result["stdout"]
    assert result["return_code"] == 0


def test_python_project_with_pytest(tmp_path):
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

    result = PythonExecutor().run(str(project))

    assert result["success"] is True
    assert result["return_code"] == 0


def test_argparse_project(tmp_path):
    project = create_project(
        tmp_path,
        {
            "main.py": """
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--name")

args = parser.parse_args()

if args.name:
    print(args.name)
""",
        },
    )

    result = PythonExecutor().run(str(project))

    assert result["success"] is True
    assert result["return_code"] == 0


def test_sys_argv_calculator(tmp_path):
    project = create_project(
        tmp_path,
        {
            "main.py": """
import sys

operation = sys.argv[1]
a = int(sys.argv[2])
b = int(sys.argv[3])

if operation == "add":
    print(a + b)
elif operation == "subtract":
    print(a - b)
elif operation == "multiply":
    print(a * b)
elif operation == "divide":
    print(a / b)
""",
        },
    )

    result = PythonExecutor().run(str(project))

    assert result["success"] is True
    assert "5" in result["stdout"]
    assert result["return_code"] == 0


def test_interactive_project_is_skipped(tmp_path):
    project = create_project(
        tmp_path,
        {
            "main.py": """
name = input("Name: ")
print(name)
""",
        },
    )

    result = PythonExecutor().run(str(project))

    assert result["success"] is True
    assert result["return_code"] == 0
    assert "Interactive application detected" in result["stderr"]


def test_web_project_is_skipped(tmp_path):
    project = create_project(
        tmp_path,
        {
            "main.py": """
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Hello"
""",
        },
    )

    result = PythonExecutor().run(str(project))

    assert result["success"] is True
    assert result["return_code"] == 0
    assert "Web application detected" in result["stderr"]


def test_gui_project_is_skipped(tmp_path):
    project = create_project(
        tmp_path,
        {
            "main.py": """
import tkinter

root = tkinter.Tk()
root.mainloop()
""",
        },
    )

    result = PythonExecutor().run(str(project))

    assert result["success"] is True
    assert result["return_code"] == 0
    assert "Gui application detected" in result["stderr"]


def test_syntax_error(tmp_path):
    project = create_project(
        tmp_path,
        {
            "main.py": """
def broken(
    print("hello")
""",
        },
    )

    result = PythonExecutor().run(str(project))

    assert result["success"] is False
    assert result["return_code"] != 0
    assert result["stderr"]


def test_missing_project(tmp_path):
    project = tmp_path / "missing"

    result = PythonExecutor().run(str(project))

    assert result["success"] is False
    assert result["return_code"] == -1
    assert "does not exist" in result["stderr"]