import asyncio

from app.agents.fixer_agent import FixerAgent
from app.services.debugger.debug_manager import DebugManager


async def main():

    project_path = r"C:\Users\iamar\OneDrive\Desktop\Autodev-AI\generated_projects\fixer_test_python"

    execution_result = {
        "success": False,
        "return_code": 1,
        "stdout": """E       assert -1 == 5
E        +  where -1 = add(2, 3)
tests/test_app.py:4: AssertionError""",
        "stderr": "",
    }

    debug_manager = DebugManager()

    debug_report = debug_manager.analyze(
        execution_result
    )

    print("=" * 60)
    print("DEBUG REPORT")
    print("=" * 60)

    print(debug_report)

    print()
    print("=" * 60)
    print("STARTING FIXER AGENT")
    print("=" * 60)

    with open(
        project_path + r"\app.py",
        "r",
        encoding="utf-8",
    ) as file:
        app_code = file.read()

    code = f"""FILE: app.py

{app_code}

FILE: requirements.txt

FILE: tests/test_app.py

from app import add

def test_add():
    assert add(2, 3) == 5
"""

    fixer = FixerAgent()

    repaired = await fixer.run(
        code=code,
        review="The generated Python project failed its test.",
        validation="Project structure is valid.",
        tests=execution_result["stdout"],
        execution_error=debug_report,
        retry_history=[],
        project_directory=project_path,
        project_type="python",
        retry_count=0,
        save_debug=True,
    )

    print()
    print("=" * 60)
    print("FIXER RESPONSE")
    print("=" * 60)

    print(repaired)


if __name__ == "__main__":
    asyncio.run(main())
