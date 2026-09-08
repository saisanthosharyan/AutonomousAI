import logging

import pytest

from app.services.llm.router import LLMRouter


class FakeGeminiService:
    instances = []

    def __init__(self, api_key=None, model=None):
        self.api_key = api_key
        self.model = model
        FakeGeminiService.instances.append(self)


def test_user_key_is_used_without_application_fallback(monkeypatch):
    monkeypatch.setitem(
        LLMRouter.PROVIDERS,
        "gemini",
        FakeGeminiService,
    )

    LLMRouter._instances.clear()
    FakeGeminiService.instances.clear()

    result = LLMRouter.get_llm(
        provider="gemini",
        api_key="USER_SECRET_KEY",
        model="gemini-user-model",
    )

    assert result.api_key == "USER_SECRET_KEY"
    assert result.model == "gemini-user-model"
    assert len(FakeGeminiService.instances) == 1
    assert "gemini" not in LLMRouter._instances


def test_user_key_requests_create_separate_instances(monkeypatch):
    monkeypatch.setitem(
        LLMRouter.PROVIDERS,
        "gemini",
        FakeGeminiService,
    )

    LLMRouter._instances.clear()
    FakeGeminiService.instances.clear()

    first = LLMRouter.get_llm(
        provider="gemini",
        api_key="USER_KEY_ONE",
    )

    second = LLMRouter.get_llm(
        provider="gemini",
        api_key="USER_KEY_TWO",
    )

    assert first is not second
    assert first.api_key == "USER_KEY_ONE"
    assert second.api_key == "USER_KEY_TWO"
    assert len(FakeGeminiService.instances) == 2
    assert "gemini" not in LLMRouter._instances


def test_user_key_without_provider_cannot_fallback():
    with pytest.raises(
        ValueError,
        match="Provider is required",
    ):
        LLMRouter.get_llm(
            api_key="USER_SECRET_KEY",
        )


def test_unsupported_user_provider_cannot_fallback():
    with pytest.raises(
        ValueError,
        match="Unsupported",
    ):
        LLMRouter.get_llm(
            provider="not-a-provider",
            api_key="USER_SECRET_KEY",
        )


def test_application_provider_can_still_be_cached(monkeypatch):
    monkeypatch.setitem(
        LLMRouter.PROVIDERS,
        "gemini",
        FakeGeminiService,
    )

    LLMRouter._instances.clear()
    FakeGeminiService.instances.clear()

    first = LLMRouter.get_llm(provider="gemini")
    second = LLMRouter.get_llm(provider="gemini")

    assert first is second
    assert first.api_key is None
    assert "gemini" in LLMRouter._instances
    assert len(FakeGeminiService.instances) == 1


def test_user_key_is_not_written_to_logs(monkeypatch, caplog):
    monkeypatch.setitem(
        LLMRouter.PROVIDERS,
        "gemini",
        FakeGeminiService,
    )

    LLMRouter._instances.clear()
    FakeGeminiService.instances.clear()

    secret = "SUPER_SECRET_USER_API_KEY"

    with caplog.at_level(logging.INFO):
        LLMRouter.get_llm(
            provider="gemini",
            api_key=secret,
            model="gemini-test-model",
        )

    assert secret not in caplog.text