from app.agents.fixer_agent import FixerAgent


def test_fixer_strips_markdown_from_file_path():
    fixer = FixerAgent.__new__(FixerAgent)

    assert fixer.get_file_blocks("FILE: main.py**\n\nprint('hello')")[0][0] == "main.py"
    assert fixer.get_file_blocks("FILE: **main.py**\n\nprint('hello')")[0][0] == "main.py"
    assert fixer.get_file_blocks("FILE: `main.py`\n\nprint('hello')")[0][0] == "main.py"
    assert fixer.get_file_blocks(
        "FILE: tests/test_app.py\n\nprint('hello')"
    )[0][0] == "tests/test_app.py"
