import re

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.core.logger import logger
from app.services.llm.base import BaseLLMService
from app.utils.retry import retry


class OpenAIService(BaseLLMService):
    """
    Service for interacting with OpenAI models.

    Supports both application-level credentials and
    request-scoped user-provided API keys.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):

        resolved_api_key = (
            api_key.strip()
            if api_key
            else settings.OPENAI_API_KEY
        )

        if not resolved_api_key:
            raise ValueError(
                "OPENAI_API_KEY is not configured."
            )

        self.client = AsyncOpenAI(
            api_key=resolved_api_key
        )

        self.model = (
            model.strip()
            if model
            else settings.OPENAI_MODEL
        )

        if not self.model:
            raise ValueError(
                "OpenAI model is not configured."
            )

        self.is_user_provided = bool(api_key)

        logger.info(
            "Initialized OpenAIService with model: %s "
            "(credentials=%s)",
            self.model,
            "user-provided"
            if self.is_user_provided
            else "application",
        )

    # --------------------------------------------------
    # SECURITY
    # --------------------------------------------------

    @staticmethod
    def _sanitize_error(
        error: Exception,
    ) -> str:
        """
        Prevent credentials from being exposed through
        provider/network exception messages.
        """

        error_text = str(error)

        error_text = re.sub(
            r"(?i)(api[-_ ]?key\s*[=:]\s*)[^\s,;]+",
            r"\1[REDACTED]",
            error_text,
        )

        error_text = re.sub(
            r"(?i)(key\s*[=:]\s*)[A-Za-z0-9_\-]{20,}",
            r"\1[REDACTED]",
            error_text,
        )

        return error_text

    # --------------------------------------------------
    # Generate Text
    # --------------------------------------------------

    @retry(max_retries=3, delay=2)
    async def generate(
        self,
        prompt: str,
    ) -> str:

        if not prompt.strip():
            raise ValueError(
                "Prompt cannot be empty."
            )

        try:

            logger.info(
                "Generating response using OpenAI (%s)...",
                self.model,
            )

            response = await self.client.responses.create(
                model=self.model,
                input=prompt,
            )

            if not response.output_text:

                raise RuntimeError(
                    "OpenAI returned an empty response."
                )

            logger.info(
                "OpenAI text generation completed successfully."
            )

            return response.output_text

        except Exception as error:

            safe_error = self._sanitize_error(
                error
            )

            logger.error(
                "OpenAI text generation failed: %s",
                safe_error,
            )

            raise RuntimeError(
                f"OpenAI request failed: {safe_error}"
            ) from error

    # --------------------------------------------------
    # Chat
    # --------------------------------------------------

    @retry(max_retries=3, delay=2)
    async def chat(
        self,
        messages: list,
    ) -> str:

        if not messages:
            raise ValueError(
                "Messages cannot be empty."
            )

        try:

            logger.info(
                "Generating chat response using OpenAI (%s)...",
                self.model,
            )

            response = await self.client.responses.create(
                model=self.model,
                input=messages,
            )

            if not response.output_text:

                raise RuntimeError(
                    "OpenAI returned an empty chat response."
                )

            logger.info(
                "OpenAI chat completed successfully."
            )

            return response.output_text

        except Exception as error:

            safe_error = self._sanitize_error(
                error
            )

            logger.error(
                "OpenAI chat request failed: %s",
                safe_error,
            )

            raise RuntimeError(
                f"OpenAI chat failed: {safe_error}"
            ) from error

    # --------------------------------------------------
    # Structured Output
    # --------------------------------------------------

    @retry(max_retries=3, delay=2)
    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
    ):

        if not prompt.strip():
            raise ValueError(
                "Prompt cannot be empty."
            )

        try:

            logger.info(
                "Generating structured response using OpenAI (%s)...",
                self.model,
            )

            response = await self.client.responses.parse(
                model=self.model,
                input=prompt,
                text_format=schema,
            )

            if response.output_parsed is None:

                raise RuntimeError(
                    "Failed to parse structured response."
                )

            logger.info(
                "OpenAI structured generation completed successfully."
            )

            return response.output_parsed

        except Exception as error:

            safe_error = self._sanitize_error(
                error
            )

            logger.error(
                "OpenAI structured generation failed: %s",
                safe_error,
            )

            raise RuntimeError(
                "OpenAI structured request failed: "
                f"{safe_error}"
            ) from error