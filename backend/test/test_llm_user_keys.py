import pytest

from app.services.llm.router import LLMRouter


class FakeGeminiService:
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key
        self.model = model


class FakeOpenAIService:
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key
        self.model = model


def test_user_gemini_key_creates_request_scoped_provider(monkeypatch):
    monkeypatch.setitem(
        LLMRouter.PROVIDERS,
        "gemini",
        FakeGeminiService,
    )

    result = LLMRouter.get_llm(
        provider="gemini",
        api_key="TEST_USER_GEMINI_KEY",
        model="gemini-test-model",
    )

    assert isinstance(result, FakeGeminiService)
    assert result.api_key == "TEST_USER_GEMINI_KEY"
    assert result.model == "gemini-test-model"


def test_user_openai_key_creates_request_scoped_provider(monkeypatch):
    monkeypatch.setitem(
        LLMRouter.PROVIDERS,
        "openai",
        FakeOpenAIService,
    )

    result = LLMRouter.get_llm(
        provider="openai",
        api_key="TEST_USER_OPENAI_KEY",
        model="gpt-test-model",
    )

    assert isinstance(result, FakeOpenAIService)
    assert result.api_key == "TEST_USER_OPENAI_KEY"
    assert result.model == "gpt-test-model"


def test_user_key_without_provider_is_rejected():
    with pytest.raises(
        ValueError,
        match="Provider is required",
    ):
        LLMRouter.get_llm(
            api_key="TEST_USER_GEMINI_KEY",
        )


def test_unsupported_provider_is_rejected():
    with pytest.raises(
        ValueError,
        match="Unsupported",
    ):
        LLMRouter.get_llm(
            provider="unsupported",
            api_key="TEST_USER_KEY",
        )


def test_user_provider_is_not_cached(monkeypatch):
    monkeypatch.setitem(
        LLMRouter.PROVIDERS,
        "gemini",
        FakeGeminiService,
    )

    LLMRouter._instances.clear()

    first = LLMRouter.get_llm(
        provider="gemini",
        api_key="TEST_USER_GEMINI_KEY_1",
        model="gemini-test-model",
    )

    second = LLMRouter.get_llm(
        provider="gemini",
        api_key="TEST_USER_GEMINI_KEY_2",
        model="gemini-test-model",
    )

    assert first is not second

    assert first.api_key == "TEST_USER_GEMINI_KEY_1"
    assert second.api_key == "TEST_USER_GEMINI_KEY_2"

    assert "gemini" not in LLMRouter._instances


def test_user_key_path_does_not_use_cached_application_instance(monkeypatch):
    class TrackingGeminiService:
        instances = []

        def __init__(self, api_key=None, model=None):
            self.api_key = api_key
            self.model = model
            TrackingGeminiService.instances.append(self)

    monkeypatch.setitem(
        LLMRouter.PROVIDERS,
        "gemini",
        TrackingGeminiService,
    )

    LLMRouter._instances.clear()

    result = LLMRouter.get_llm(
        provider="gemini",
        api_key="TEST_USER_GEMINI_KEY",
        model="gemini-test-model",
    )

    assert isinstance(result, TrackingGeminiService)
    assert result.api_key == "TEST_USER_GEMINI_KEY"

    assert len(TrackingGeminiService.instances) == 1
    assert "gemini" not in LLMRouter._instances
