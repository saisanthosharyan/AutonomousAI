import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.planner import PlannerAgent
from app.agents.coder import CoderAgent


async def main():

    print("=" * 60)
    print("AUTODEV AI - CODER AGENT TEST")
    print("=" * 60)

    planner = PlannerAgent()
    coder = CoderAgent()

    request = """
Create a simple Python calculator CLI application.

Requirements:

- Addition
- Subtraction
- Multiplication
- Division
- Division by zero handling
- User-friendly command-line interaction
- Clean project structure
- Include tests
- Include README.md
"""

    print()
    print("STEP 1 - Generating project plan...")
    print()

    plan = await planner.run(request)

    print("=" * 60)
    print("PLAN GENERATED")
    print("=" * 60)

    print(plan)

    print()
    print("=" * 60)
    print("STEP 2 - Generating project code...")
    print("=" * 60)
    print()

    try:

        code = await coder.run(plan)

        print("=" * 60)
        print("CODER RESULT")
        print("=" * 60)

        print(code)

        print()
        print("=" * 60)
        print("RESULT TYPE")
        print("=" * 60)

        print(type(code))

        print()
        print("=" * 60)
        print("CODER TEST PASSED")
        print("=" * 60)

    except Exception as e:

        print()
        print("=" * 60)
        print("CODER TEST FAILED")
        print("=" * 60)

        print(f"Error: {e}")

        raise


if __name__ == "__main__":
    asyncio.run(main())
