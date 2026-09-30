import pytest

from app.agents.coder import CoderAgent


def test_python_validator_rejects_eval():
    coder = CoderAgent()

    files = [
        (
            "main.py",
            'expression = input("Enter: ")\n'
            "result = eval(expression)\n"
            "print(result)\n",
        )
    ]

    with pytest.raises(
        RuntimeError,
        match="Unsafe Python dynamic execution detected",
    ):
        coder._validate_python_files(files)


def test_python_validator_rejects_exec():
    coder = CoderAgent()

    files = [
        (
            "main.py",
            'code = input("Enter code: ")\n'
            "exec(code)\n",
        )
    ]

    with pytest.raises(
        RuntimeError,
        match="Unsafe Python dynamic execution detected",
    ):
        coder._validate_python_files(files)


def test_python_validator_accepts_safe_code():
    coder = CoderAgent()

    files = [
        (
            "main.py",
            "def add(a, b):\n"
            "    return a + b\n"
            "\n"
            "print(add(2, 3))\n",
        )
    ]

    coder._validate_python_files(files)
