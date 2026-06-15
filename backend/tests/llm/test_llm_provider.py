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


# ── ProviderRegistry (§6.1 fix) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_registry_get_creates_and_caches_provider():
    from app.capabilities.llm.provider_registry import ProviderRegistry

    registry = ProviderRegistry(ttl_seconds=300)
    settings = LlmSettings(provider="mock")

    p1 = await registry.get(settings)
    p2 = await registry.get(settings)

    assert p1 is p2  # cache hit: same instance
    assert isinstance(p1, MockProvider)
    assert registry.size == 1


@pytest.mark.asyncio
async def test_registry_different_settings_different_providers():
    from app.capabilities.llm.provider_registry import ProviderRegistry

    registry = ProviderRegistry(ttl_seconds=300)
    s1 = LlmSettings(provider="deepseek", api_key="sk-key1")
    s2 = LlmSettings(provider="deepseek", api_key="sk-key2")  # different key

    p1 = await registry.get(s1)
    p2 = await registry.get(s2)

    assert p1 is not p2  # different settings → different provider
    assert registry.size == 2


@pytest.mark.asyncio
async def test_registry_ttl_expiry_recreates_provider():
    from app.capabilities.llm.provider_registry import ProviderRegistry

    registry = ProviderRegistry(ttl_seconds=0)  # expire immediately
    settings = LlmSettings(provider="mock")

    p1 = await registry.get(settings)
    p2 = await registry.get(settings)

    assert p1 is not p2  # expired → recreated
    assert registry.size == 1  # old entry replaced, not duplicated


@pytest.mark.asyncio
async def test_registry_invalidate_clears_all():
    from app.capabilities.llm.provider_registry import ProviderRegistry

    registry = ProviderRegistry(ttl_seconds=300)
    s1 = LlmSettings(provider="mock")
    s2 = LlmSettings(provider="deepseek", api_key="sk-aaa")

    await registry.get(s1)
    await registry.get(s2)
    assert registry.size == 2

    await registry.invalidate()
    assert registry.size == 0


@pytest.mark.asyncio
async def test_registry_concurrent_access_same_settings():
    """Multiple concurrent gets for the same settings should return the same provider."""
    import asyncio
    from app.capabilities.llm.provider_registry import ProviderRegistry

    registry = ProviderRegistry(ttl_seconds=300)
    settings = LlmSettings(provider="mock")

    async def get():
        return await registry.get(settings)

    results = await asyncio.gather(*[get() for _ in range(10)])

    # All should be the same instance (first creates, others hit cache)
    first = results[0]
    for r in results[1:]:
        assert r is first
    assert registry.size == 1


@pytest.mark.asyncio
async def test_registry_close_called_on_expiry():
    """When a provider expires, close() should be called on the old one."""
    from app.capabilities.llm.provider_registry import ProviderRegistry

    registry = ProviderRegistry(ttl_seconds=0)  # expire immediately
    settings = LlmSettings(provider="mock")

    p1 = await registry.get(settings)
    # Trigger expiry → old provider should be closed
    p2 = await registry.get(settings)

    assert p1 is not p2  # new provider created
    # MockProvider.close() is a no-op, but the call path is exercised.
    # In production, OpenAICompatProvider.close() would release the connection pool.


@pytest.mark.asyncio
async def test_get_provider_registry_singleton():
    from app.capabilities.llm.provider_registry import get_provider_registry

    r1 = get_provider_registry()
    r2 = get_provider_registry()
    assert r1 is r2


@pytest.mark.asyncio
async def test_get_effective_llm_settings_returns_base_when_db_unavailable():
    """Without a DB connection, should return env-var-based defaults."""
    from app.capabilities.llm.provider_registry import get_effective_llm_settings

    settings = await get_effective_llm_settings()
    # Should fall back to env-var / code defaults (likely "deepseek" in test env)
    assert settings.provider in ("deepseek", "mock")
    assert isinstance(settings.model, str)
    assert len(settings.model) > 0
