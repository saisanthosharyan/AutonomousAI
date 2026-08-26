from app.agents.fixer_agent import FixerAgent


def test_missing_original_source_file_is_rejected():

    fixer = FixerAgent.__new__(FixerAgent)

    original_files = {
        "app.py": "def add(a, b):\n    return a + b",
        "requirements.txt": "pytest",
        "tests/test_app.py": (
            "from app import add\n\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5"
        ),
    }

    generated_keys = {
        "app.py",
        "requirements.txt",
    }

    try:
        fixer._check_source_files_preserved(
            generated_keys,
            original_files,
        )

        assert False, (
            "Expected missing source file protection "
            "to reject the repair."
        )

    except RuntimeError as exc:

        assert "tests/test_app.py" in str(exc)