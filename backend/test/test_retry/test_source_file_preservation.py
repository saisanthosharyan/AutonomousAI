from app.agents.fixer_agent import FixerAgent


def test_new_source_files_are_allowed():

    fixer = FixerAgent.__new__(FixerAgent)

    original_files = {
        "app.py": "def add(a, b):\n    return a + b",
        "tests/test_app.py": (
            "from app import add\n\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5"
        ),
    }

    generated_keys = {
        "app.py",
        "tests/test_app.py",
        "utils.py",
    }

    fixer._check_source_files_preserved(
        generated_keys,
        original_files,
    )