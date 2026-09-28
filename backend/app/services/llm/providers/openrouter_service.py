from typing import Any

import httpx

from app.core.config import settings
from app.core.logger import logger
from app.services.llm.base import BaseLLMService


class OpenRouterService(BaseLLMService):

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        resolved_api_key = (
            api_key.strip()
            if api_key
            else settings.OPENROUTER_API_KEY
        )

        if not resolved_api_key:
            raise ValueError("OpenRouter API key is not configured.")

        self.api_key = resolved_api_key
        self.model = (
            model.strip()
            if model
            else settings.OPENROUTER_MODEL
        )

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "AutoDev-AI",
        }

        logger.info(
            f"Initialized OpenRouterService with model: {self.model}"
        )

    async def _request(
        self,
        messages: list[dict[str, str]],
    ) -> str:

        payload = {
            "model": self.model,
            "messages": messages,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers=self.headers,
                json=payload,
            )

        if response.status_code >= 400:
            error_text = response.text

            logger.error(
                f"OpenRouter API error "
                f"{response.status_code}: {error_text}"
            )

            raise RuntimeError(
                f"OpenRouter API error {response.status_code}: "
                f"{error_text}"
            )

        data = response.json()

        choices = data.get("choices", [])

        if not choices:
            raise RuntimeError(
                "OpenRouter returned no choices."
            )

        content = choices[0].get("message", {}).get("content")

        if not content:
            raise RuntimeError(
                "OpenRouter returned an empty response."
            )

        return content

    async def generate(self, prompt: str) -> str:

        return await self._request(
            [
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
    ) -> str:

        return await self._request(messages)

    async def generate_structured(
        self,
        prompt: str,
        schema: type[Any],
    ) -> Any:

        schema_json = schema.model_json_schema()

        structured_prompt = f"""
Return a JSON object that strictly follows this schema:

{schema_json}

Task:

{prompt}

Return only valid JSON.
"""

        result = await self.generate(structured_prompt)

        import json

        parsed = json.loads(result)

        return schema.model_validate(parsed)