"""Unit tests for LLM provider abstraction (T1.1)."""

import pytest
from app.capabilities.llm import (
    BaseLLMProvider,
    LlmDelta,
    LlmUsage,
    LlmResult,
    MockProvider,
    OpenAICompatProvider,
    create_llm_provider,
)
from app.core.config import LlmSettings


# ── MockProvider ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mock_provider_stream_yields_chunks():
    provider = MockProvider()
    chunks = [c async for c in provider.stream([{"role": "user", "content": "你好"}])]
    assert len(chunks) > 0
    assert all(isinstance(c, LlmDelta) for c in chunks)
    assert chunks[-1].finish_reason == "stop"
    full_text = "".join(c.text for c in chunks)
    assert len(full_text) > 10  # reasonable response


@pytest.mark.asyncio
async def test_mock_provider_complete_returns_result():
    provider = MockProvider()
    result = await provider.complete([{"role": "user", "content": "你好"}])
    assert isinstance(result, LlmResult)
    assert result.finish_reason == "stop"
    assert result.model == "mock-model"
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_mock_provider_custom_text():
    provider = MockProvider()
    result = await provider.complete(
        [{"role": "user", "content": "?"}], mock_text="Hello!"
    )
    assert result.text == "Hello!"


# ── Factory ───────────────────────────────────────────────────────


def test_factory_creates_mock_when_provider_is_mock():
    settings = LlmSettings(provider="mock")
    provider = create_llm_provider(settings)
    assert isinstance(provider, MockProvider)
    assert provider.provider_name == "mock"


def test_factory_falls_back_to_mock_when_no_api_key():
    settings = LlmSettings(provider="deepseek", api_key="")
    provider = create_llm_provider(settings)
    assert isinstance(provider, MockProvider)


def test_factory_creates_openai_compat_with_api_key():
    settings = LlmSettings(provider="deepseek", api_key="sk-test")
    provider = create_llm_provider(settings)
    assert isinstance(provider, OpenAICompatProvider)
    assert provider.provider_name == "openai_compat"
    assert provider.default_model == "deepseek-chat"


# ── Config ────────────────────────────────────────────────────────


def test_llm_settings_defaults():
    settings = LlmSettings()
    assert settings.provider == "deepseek"
    assert settings.model == "deepseek-chat"
    assert settings.max_tokens == 2048
    assert settings.temperature == 0.7
    assert settings.max_retries == 3
    assert settings.request_timeout == 60


def test_llm_settings_custom():
    settings = LlmSettings(
        provider="openai",
        api_key="sk-xxx",
        api_base="https://api.openai.com/v1",
        model="gpt-4o",
        max_tokens=4096,
        temperature=0.3,
    )
    assert settings.provider == "openai"
    assert settings.model == "gpt-4o"
    assert settings.max_tokens == 4096
    assert settings.temperature == 0.3


# ── Base types ────────────────────────────────────────────────────


def test_llm_delta_defaults():
    d = LlmDelta(index=0, text="你")
    assert d.finish_reason is None
    assert d.text == "你"


def test_llm_usage_defaults():
    u = LlmUsage()
    assert u.prompt_tokens == 0
    assert u.completion_tokens == 0
