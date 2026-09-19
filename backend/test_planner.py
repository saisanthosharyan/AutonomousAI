import asyncio
from app.agents.planner import PlannerAgent
from app.services.llm.providers.gemini_service import GeminiService

async def main():
    planner = PlannerAgent(GeminiService())

    result = await planner.run(
        """Create a simple HTML page with the heading "AutoDev AI" and a button that shows an alert saying "Hello from AutoDev AI" when clicked.

Use only index.html, style.css, and script.js."""
    )

    print("\n=== PLANNER RESULT ===")
    print(result.model_dump())

asyncio.run(main())
