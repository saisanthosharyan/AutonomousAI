import asyncio

from app.agents.orchestrator import AgentOrchestrator


async def main():
    orchestrator = AgentOrchestrator()

    result = await orchestrator.execute(
        task="Build a Python calculator"
    )

    print("\n" + "=" * 70)
    print("PIPELINE FINISHED")
    print("=" * 70)

    print("\nSuccess:", result["success"])

    print("\nProject:")
    print(result["project"])

    print("\nExecution:")
    print(result["execution"])

    print("\nValidation:")
    print(result["validation"])

    print("\nTests:")
    print(result["tests"])

    print("\nReview:")
    print(result["review"])

    print("\nMetrics:")
    print(result["metrics"])


if __name__ == "__main__":
    asyncio.run(main())