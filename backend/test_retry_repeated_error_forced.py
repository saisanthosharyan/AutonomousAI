import asyncio

from app.services.retry.retry_manager import RetryManager
from app.builders.project_builder import ProjectBuilder


class FakeFixerAgent:

    async def run(
        self,
        code,
        review=None,
        execution_error=None,
        memory=None,
        project_directory=None,
        project_type=None,
        retry_history=None,
        retry_count=None,
        save_debug=False,
    ):

        print()
        print("=" * 70)
        print("FAKE FIXER CALLED")
        print("=" * 70)

        fixed_code = code.replace(
            "return a + c",
            "return a + d",
        )

        print("Original:")
        print("    return a + c")

        print("Fake repair:")
        print("    return a + d")

        return fixed_code
async def main():

    code = '''FILE: app.py

def add(a, b):
    return a + c

FILE: requirements.txt

pytest

FILE: tests/test_app.py

from app import add

def test_add():
    assert add(2, 3) == 5
'''

    # ----------------------------------------------------------
    # Create project
    # ----------------------------------------------------------

    builder = ProjectBuilder()

    project_result = builder.build(
        project_name="fixer_repeated_error_forced",
        llm_output=code,
    )

    project_path = project_result["project_path"]

    print()
    print("=" * 70)
    print("INITIAL PROJECT CREATED")
    print("=" * 70)
    print(project_path)

    # ----------------------------------------------------------
    # Create RetryManager
    # ----------------------------------------------------------

    retry_manager = RetryManager(
        max_retries=3
    )

    # ----------------------------------------------------------
    # Replace real AI fixer with fake fixer
    # ----------------------------------------------------------

    retry_manager.fixer = FakeFixerAgent()

    project = {
        "project_path": project_path,
        "title": "Forced Repeated Error Test",
    }

    # ----------------------------------------------------------
    # Run
    # ----------------------------------------------------------

    result = await retry_manager.execute_with_retry(
        project=project,
        code=code,
    )

    execution_result = result[0]
    debug_report = result[3]
    retry_stats = result[4]

    # ----------------------------------------------------------
    # Results
    # ----------------------------------------------------------

    print()
    print("=" * 70)
    print("FINAL RESULT")
    print("=" * 70)

    print("SUCCESS:", execution_result.get("success"))
    print("RETURN CODE:", execution_result.get("return_code"))

    print()
    print("--- RETRY STATS ---")
    print(retry_stats)

    print()
    print("--- REPAIR HISTORY ---")
    print(debug_report.get("repair_history"))

    print()
    print("--- DEBUG REPORT ---")
    print(debug_report)


if __name__ == "__main__":
    asyncio.run(main())