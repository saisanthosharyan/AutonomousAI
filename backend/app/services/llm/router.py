from __future__ import annotations

from app.core.config import settings
from app.core.logger import logger

from app.services.llm.base import BaseLLMService
from app.services.llm.fallback_service import FallbackLLMService

from app.services.llm.providers.gemini_service import GeminiService
from app.services.llm.providers.openai_service import OpenAIService
from app.services.llm.providers.ollama_service import OllamaService


class LLMRouter:

    # --------------------------------------------------
    # IMPORTANT
    #
    # Only application/.env provider instances are cached.
    #
    # User-provided API-key instances are NEVER placed
    # into this dictionary.
    # --------------------------------------------------

    _instances: dict[str, BaseLLMService] = {}

    PROVIDERS = {
        "ollama": OllamaService,
        "gemini": GeminiService,
        "openai": OpenAIService,
    }

    DEFAULT_PROVIDER_ORDER = [
        "gemini",
        "openai",
        "ollama",
    ]

    # --------------------------------------------------
    # PROVIDER CONFIGURATION
    # --------------------------------------------------

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

                providers.append(
                    name
                )

        if not providers:

            logger.warning(
                "LLM_PRIORITY not configured. "
                "Using default provider order."
            )

            providers = list(
                cls.DEFAULT_PROVIDER_ORDER
            )

        return providers

    # --------------------------------------------------
    # APPLICATION PROVIDER
    # --------------------------------------------------

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
            "Initializing application LLM provider '%s'...",
            provider,
        )

        instance = provider_class()

        cls._instances[
            provider
        ] = instance

        logger.info(
            "Application LLM provider '%s' initialized successfully.",
            provider,
        )

        return instance

    # --------------------------------------------------
    # USER PROVIDER
    # --------------------------------------------------

    @classmethod
    def _get_user_provider(
        cls,
        provider: str,
        api_key: str | None,
        model: str | None,
    ) -> BaseLLMService:
        """
        Create a request-scoped LLM provider.

        IMPORTANT:

        This instance is deliberately NOT cached.

        Therefore a user's API key cannot accidentally be
        reused by another request.
        """

        provider = provider.strip().lower()

        provider_class = cls.PROVIDERS.get(
            provider
        )

        if provider_class is None:

            raise ValueError(
                f"Unsupported LLM provider: {provider}"
            )

        if provider == "ollama":

            logger.info(
                "Initializing request-scoped Ollama provider."
            )

            # Ollama does not require an API key.
            #
            # The current OllamaService constructor uses
            # application settings, so keep it isolated here.
            return provider_class()

        if not api_key:

            raise ValueError(
                f"An API key is required for provider '{provider}'."
            )

        logger.info(
            "Initializing request-scoped %s provider "
            "with user credentials.",
            provider,
        )

        return provider_class(
            api_key=api_key,
            model=model,
        )

    # --------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------

    @classmethod
    def get_llm(
        cls,
        provider: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> BaseLLMService:
        """
        Resolve an LLM service.

        Modes:

        1. No user credentials
           -> existing application provider fallback.

        2. User API key supplied
           -> request-scoped selected provider.
           -> NO fallback to application credentials.

        3. Provider supplied without user API key
           -> use the configured application provider.
        """

        normalized_provider = (
            provider.strip().lower()
            if provider
            else None
        )

        normalized_api_key = (
            api_key.strip()
            if api_key
            else None
        )

        normalized_model = (
            model.strip()
            if model
            else None
        )

        # --------------------------------------------------
        # USER API KEY MODE
        # --------------------------------------------------

        if normalized_api_key:

            if not normalized_provider:

                raise ValueError(
                    "Provider is required when using a user-provided API key."
                )

            logger.info(
                "Using request-scoped user LLM provider: %s",
                normalized_provider,
            )

            return cls._get_user_provider(
                provider=normalized_provider,
                api_key=normalized_api_key,
                model=normalized_model,
            )

        # --------------------------------------------------
        # EXPLICIT APPLICATION PROVIDER
        # --------------------------------------------------

        if normalized_provider:

            logger.info(
                "Using configured application LLM provider: %s",
                normalized_provider,
            )

            return cls._get_provider(
                normalized_provider
            )

        # --------------------------------------------------
        # EXISTING FALLBACK MODE
        # --------------------------------------------------

        provider_names = cls._providers()

        logger.info(
            "Configured LLM providers: "
            + ", ".join(provider_names)
        )

        providers = []

        for name in provider_names:

            try:

                provider_instance = (
                    cls._get_provider(name)
                )

                providers.append(
                    (
                        name,
                        provider_instance,
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
            ", ".join(
                name
                for name, _ in providers
            ),
        )

        return FallbackLLMService(
            providers
        )