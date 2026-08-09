import asyncio

from pydantic import BaseModel, Field

from app.services.llm.router import LLMRouter


class PlanSchema(BaseModel):
    project_name: str = Field(
        description="Name of the project"
    )

    language: str = Field(
        description="Programming language"
    )

    description: str = Field(
        description="Short project description"
    )

    features: list[str] = Field(
        description="List of project features"
    )


async def main():

    print("=" * 60)
    print("AUTODEV AI - STRUCTURED LLM TEST")
    print("=" * 60)

    llm = LLMRouter.get_llm()

    print(
        f"Service: {type(llm).__name__}"
    )

    print()
    print("Requesting structured response...")
    print()

    prompt = """
Create a simple Python calculator CLI application.

The application should support:

1. Addition
2. Subtraction
3. Multiplication
4. Division
5. Division-by-zero handling
6. User-friendly CLI interaction
"""

    result = await llm.generate_structured(
        prompt,
        PlanSchema,
    )

    print("=" * 60)
    print("STRUCTURED RESPONSE")
    print("=" * 60)

    print(result)

    print()
    print("=" * 60)
    print("TYPE")
    print("=" * 60)

    print(type(result))

    print()
    print("=" * 60)
    print("FIELDS")
    print("=" * 60)

    print(
        "Project:",
        result.project_name,
    )

    print(
        "Language:",
        result.language,
    )

    print(
        "Description:",
        result.description,
    )

    print(
        "Features:",
        result.features,
    )

    print()
    print("=" * 60)
    print("STRUCTURED TEST PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())