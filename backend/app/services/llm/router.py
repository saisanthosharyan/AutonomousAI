from __future__ import annotations

from app.core.config import settings
from app.core.logger import logger

from app.services.llm.base import BaseLLMService
from app.services.llm.fallback_service import FallbackLLMService

from app.services.llm.providers.gemini_service import GeminiService
from app.services.llm.providers.openai_service import OpenAIService
from app.services.llm.providers.ollama_service import OllamaService


class LLMRouter:

    _instances: dict[str, BaseLLMService] = {}

    PROVIDERS = {
        "ollama": OllamaService,
        "gemini": GeminiService,
        "openai": OpenAIService,
    }

    DEFAULT_PROVIDER_ORDER = ["gemini", "openai", "ollama"]

    @classmethod
    def _providers(cls) -> list[str]:

        priority = getattr(
            settings,
            "LLM_PRIORITY",
            "",
        )

        providers = []

        for name in priority.split(","):

            name = name.strip().lower()

            if not name:
                continue

            if name not in cls.PROVIDERS:

                logger.warning(
                    "Ignoring unsupported LLM provider: '%s'",
                    name,
                )

                continue

            if name not in providers:
                providers.append(name)

        if not providers:

            logger.warning(
                "LLM_PRIORITY not configured. Using default provider order."
            )

            providers = list(cls.DEFAULT_PROVIDER_ORDER)

        return providers

    @classmethod
    def _get_provider(
        cls,
        provider: str,
    ) -> BaseLLMService:

        provider = provider.strip().lower()

        if provider in cls._instances:

            return cls._instances[
                provider
            ]

        provider_class = cls.PROVIDERS.get(
            provider
        )

        if provider_class is None:

            raise ValueError(
                f"Unsupported LLM provider: {provider}"
            )

        logger.info(
            "Initializing LLM provider '%s'...",
            provider,
        )

        instance = provider_class()

        cls._instances[
            provider
        ] = instance

        logger.info(
            "LLM provider '%s' initialized successfully.",
            provider,
        )

        return instance

    @classmethod
    def get_llm(
        cls,
    ) -> BaseLLMService:

        provider_names = cls._providers()

        logger.info(
            "Configured LLM providers: "
            + ", ".join(provider_names)
        )

        providers = []

        for name in provider_names:

            try:

                provider = cls._get_provider(
                    name
                )

                providers.append(
                    (
                        name,
                        provider,
                    )
                )

            except Exception:

                logger.exception(
                    "Failed to initialize LLM provider '%s'.",
                    name,
                )

        if not providers:

            raise RuntimeError(
                "No configured LLM providers are available."
            )

        if len(providers) == 1:

            logger.info(
                "Using single LLM provider: %s",
                providers[0][0],
            )

            return providers[0][1]

        logger.info(
            "Using FallbackLLMService with providers: %s",
            ", ".join(name for name, _ in providers),
        )

        return FallbackLLMService(
            providers
        )