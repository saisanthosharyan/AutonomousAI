import sys
from pathlib import Path
import asyncio

# ============================================================
# BACKEND PATH
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parents[2]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.services.retry.retry_manager import RetryManager
from app.builders.project_builder import ProjectBuilder


# ============================================================
# HELPERS
# ============================================================

def print_section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def print_repair_history(history) -> None:
    """
    Print only a compact summary of repair attempts.

    Do NOT print the complete error/pytest traceback because
    repair history can contain very large diagnostic output.
    """

    print_section("REPAIR HISTORY")

    if not history:
        print("No repairs performed.")
        return

    for item in history:

        attempt = item.get(
            "attempt",
            "?",
        )

        category = item.get(
            "category",
            "Unknown",
        )

        similarity = item.get(
            "similarity",
            "N/A",
        )

        print(
            f"Attempt {attempt}: "
            f"{category} "
            f"(similarity={similarity})"
        )


# ============================================================
# MAIN
# ============================================================

async def main():

    # --------------------------------------------------------
    # Intentionally broken project
    # --------------------------------------------------------

    code = """FILE: app.py

def multiply(a, b):
    return a + "hello"

FILE: requirements.txt

pytest

FILE: tests/test_app.py

from app import multiply

def test_multiply():
    assert multiply(2, 3) == 6
"""

    # --------------------------------------------------------
    # Create project
    # --------------------------------------------------------

    builder = ProjectBuilder()

    project_result = builder.build(
        project_name="test_protection",
        llm_output=code,
    )

    project_path = project_result["project_path"]

    print_section("INITIAL PROJECT CREATED")
    print(project_path)

    # --------------------------------------------------------
    # Test file
    # --------------------------------------------------------

    test_file = (
        Path(project_path)
        / "tests"
        / "test_app.py"
    )

    if not test_file.exists():
        raise FileNotFoundError(
            f"Test file was not created: {test_file}"
        )

    original_test = test_file.read_text(
        encoding="utf-8"
    )

    print_section("ORIGINAL TEST")
    print(original_test)

    # --------------------------------------------------------
    # Retry manager
    # --------------------------------------------------------

    retry_manager = RetryManager(
        max_retries=3
    )

    project = {
        "project_path": project_path,
        "title": "Test Protection",
    }

    # --------------------------------------------------------
    # Autonomous repair
    # --------------------------------------------------------

    result = await retry_manager.execute_with_retry(
        project=project,
        code=code,
    )

    # --------------------------------------------------------
    # Validate return structure
    # --------------------------------------------------------

    if not isinstance(result, tuple):
        raise RuntimeError(
            "RetryManager returned an unexpected result."
        )

    if len(result) < 5:
        raise RuntimeError(
            "RetryManager returned fewer than 5 results."
        )

    execution_result = result[0]

    debug_report = result[3]

    retry_stats = result[4]

    if not isinstance(
        execution_result,
        dict,
    ):
        execution_result = {}

    if not isinstance(
        debug_report,
        dict,
    ):
        debug_report = {}

    if not isinstance(
        retry_stats,
        dict,
    ):
        retry_stats = {}

    # --------------------------------------------------------
    # Repair history
    # --------------------------------------------------------

    repair_history = retry_stats.get(
        "repair_history",
        [],
    )

    if not isinstance(
        repair_history,
        list,
    ):
        repair_history = []

    # --------------------------------------------------------
    # Read test after repair
    # --------------------------------------------------------

    if not test_file.exists():
        raise FileNotFoundError(
            "Test file disappeared after repair."
        )

    repaired_test = test_file.read_text(
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # Compare test
    # --------------------------------------------------------

    test_unchanged = (
        original_test == repaired_test
    )

    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------

    print_section("TEST PROTECTION RESULT")

    success = execution_result.get(
        "success",
        False,
    )

    attempts = retry_stats.get(
        "attempts",
        0,
    )

    repairs = retry_stats.get(
        "repairs",
        0,
    )

    print(
        f"Execution success: {success}"
    )

    print(
        f"Attempts: {attempts}"
    )

    print(
        f"Repairs: {repairs}"
    )

    print(
        f"Test unchanged: {test_unchanged}"
    )

    # --------------------------------------------------------
    # Protection result
    # --------------------------------------------------------

    if test_unchanged:

        print()
        print(
            "PASS: Fixer did not modify "
            "the test file."
        )

    else:

        print()
        print(
            "FAIL: Fixer modified "
            "the test file."
        )

    # --------------------------------------------------------
    # Repaired test
    # --------------------------------------------------------

    print_section("REPAIRED TEST")

    print(repaired_test)

    # --------------------------------------------------------
    # Repair history
    # --------------------------------------------------------

    print_repair_history(
        repair_history
    )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    print_section("FINAL RESULT")

    if success and test_unchanged:

        print(
            "PASS: Autonomous repair succeeded "
            "and test protection is working."
        )

    elif success and not test_unchanged:

        print(
            "FAIL: Repair succeeded, "
            "but the test file was modified."
        )

    elif not success and test_unchanged:

        print(
            "FAIL: Test protection passed, "
            "but autonomous repair failed."
        )

    else:

        print(
            "FAIL: Autonomous repair failed "
            "and the test file was modified."
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())