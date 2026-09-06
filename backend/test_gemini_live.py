import asyncio

from app.services.llm.providers.gemini_service import GeminiService


async def main():
    service = GeminiService()

    result = await service.generate(
        "Reply with exactly: GEMINI_OK"
    )

    print("=" * 50)
    print(result)
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
