import asyncio
import re

from google import genai
from pydantic import BaseModel

from app.core.config import settings
from app.core.logger import logger
from app.services.llm.base import BaseLLMService
from app.utils.retry import retry


class GeminiQuotaError(RuntimeError):
    """Raised when Gemini API quota is exhausted."""

    pass


class GeminiService(BaseLLMService):
    """
    Gemini LLM Service.

    Supports both:

    1. Application-level credentials from settings/.env
    2. Request-scoped user-provided API keys

    User-provided credentials are never stored in the global
    LLMRouter cache.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):

        resolved_api_key = (
            api_key.strip()
            if api_key
            else settings.GEMINI_API_KEY
        )

        if not resolved_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured."
            )

        self.client = genai.Client(
            api_key=resolved_api_key
        )

        self.model = (
            model.strip()
            if model
            else settings.GEMINI_MODEL
        )

        if not self.model:
            raise ValueError(
                "Gemini model is not configured."
            )

        self.is_user_provided = bool(api_key)

        logger.info(
            "Initialized GeminiService with model: %s "
            "(credentials=%s)",
            self.model,
            "user-provided"
            if self.is_user_provided
            else "application",
        )

    # --------------------------------------------------------
    # SECURITY HELPERS
    # --------------------------------------------------------

    @staticmethod
    def _sanitize_error(
        error: Exception,
    ) -> str:
        """
        Prevent API credentials from appearing in error messages.

        Some SDK/network exceptions can contain request URLs,
        headers, or credential-related information.
        """

        error_text = str(error)

        # We deliberately do not know the user's actual key here.
        # Replace common credential-bearing patterns.
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

    # --------------------------------------------------------
    # Internal Helpers
    # --------------------------------------------------------

    def _extract_text(self, response) -> str:
        """
        Safely extract text from Gemini response.
        """

        try:
            if getattr(response, "text", None):
                return response.text.strip()

        except Exception:
            pass

        try:
            if getattr(response, "candidates", None):

                texts = []

                for candidate in response.candidates:

                    content = getattr(
                        candidate,
                        "content",
                        None,
                    )

                    if content is None:
                        continue

                    parts = getattr(
                        content,
                        "parts",
                        [],
                    )

                    for part in parts:

                        text = getattr(
                            part,
                            "text",
                            None,
                        )

                        if text:
                            texts.append(text)

                if texts:
                    return "\n".join(
                        texts
                    ).strip()

        except Exception:

            logger.exception(
                "Failed extracting candidate text."
            )

        return ""

    def _handle_error(
        self,
        error: Exception,
        operation: str,
    ):
        """
        Convert Gemini errors into meaningful application errors
        without exposing credentials.
        """

        error_text = self._sanitize_error(
            error
        )

        # Gemini quota / rate limit
        if (
            "429" in error_text
            or "RESOURCE_EXHAUSTED" in error_text
            or "quota" in error_text.lower()
        ):

            logger.error(
                "Gemini quota exhausted during %s.",
                operation,
            )

            raise GeminiQuotaError(
                "Gemini API quota has been exhausted. "
                "Please wait for the quota to reset or configure "
                "another LLM provider."
            ) from error

        logger.error(
            "Gemini %s failed: %s",
            operation,
            error_text,
        )

        raise RuntimeError(
            f"Gemini {operation} failed: {error_text}"
        ) from error

    # --------------------------------------------------------
    # TEXT GENERATION
    # --------------------------------------------------------

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
                "Generating response using Gemini (%s)...",
                self.model,
            )

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=prompt,
            )

            text = self._extract_text(
                response
            )

            if not text:

                logger.error(
                    "Gemini returned an empty response."
                )

                raise RuntimeError(
                    "Gemini returned an empty response."
                )

            logger.info(
                "Gemini text generation completed successfully."
            )

            return text

        except GeminiQuotaError:
            raise

        except Exception as error:

            self._handle_error(
                error,
                "text generation",
            )

    # --------------------------------------------------------
    # CHAT
    # --------------------------------------------------------

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
                "Generating chat using Gemini (%s)...",
                self.model,
            )

            prompt = "\n".join(
                f"{message.get('role', 'user').upper()}: "
                f"{message.get('content', '')}"
                for message in messages
            )

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=prompt,
            )

            text = self._extract_text(
                response
            )

            if not text:

                logger.error(
                    "Gemini returned an empty chat response."
                )

                raise RuntimeError(
                    "Gemini returned an empty chat response."
                )

            logger.info(
                "Gemini chat completed successfully."
            )

            return text

        except GeminiQuotaError:
            raise

        except Exception as error:

            self._handle_error(
                error,
                "chat",
            )

    # --------------------------------------------------------
    # STRUCTURED OUTPUT
    # --------------------------------------------------------

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
                "Generating structured response using Gemini (%s)...",
                self.model,
            )

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                },
            )

            text = self._extract_text(
                response
            )

            if not text:

                logger.error(
                    "Gemini returned an empty structured response."
                )

                raise RuntimeError(
                    "Gemini returned an empty structured response."
                )

            parsed = schema.model_validate_json(
                text
            )

            logger.info(
                "Gemini structured generation completed successfully."
            )

            return parsed

        except GeminiQuotaError:
            raise

        except Exception as error:

            self._handle_error(
                error,
                "structured generation",
            )