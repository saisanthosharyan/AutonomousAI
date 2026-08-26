import pytest

from app.agents.fixer_agent import FixerAgent


def test_existing_source_file_cannot_be_deleted():

    fixer = FixerAgent.__new__(FixerAgent)

    original_files = {
        "app.py": "def add(a, b):\n    return a + b",
        "utils.py": "def helper():\n    return True",
        "tests/test_app.py": (
            "from app import add\n\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5"
        ),
    }

    # LLM forgot to return utils.py.
    generated_keys = {
        "app.py",
        "tests/test_app.py",
    }

    with pytest.raises(RuntimeError, match="utils.py"):
        fixer._check_source_files_preserved(
            generated_keys,
            original_files,
        )