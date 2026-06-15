"""Unit tests for embedding provider."""

import pytest
from app.capabilities.embedding.openai_compat import (
    MockEmbeddingProvider,
    _truncate_text,
)
from app.capabilities.embedding.factory import create_embedding_provider
from app.core.config import EmbeddingSettings


class TestTruncateText:
    def test_short_text_passes_through(self):
        text = "Hello world"
        result = _truncate_text(text, max_tokens=100)
        assert result == text

    def test_long_text_truncated(self):
        # Create text that exceeds token limit
        text = "这是一个很长的测试文本。" * 3000
        result = _truncate_text(text, max_tokens=100)
        assert len(result) < len(text)


class TestMockEmbeddingProvider:
    @pytest.mark.asyncio
    async def test_provider_name(self):
        provider = MockEmbeddingProvider()
        assert provider.provider_name == "mock"

    @pytest.mark.asyncio
    async def test_dimensions(self):
        provider = MockEmbeddingProvider()
        assert provider.dimensions == 1536

    @pytest.mark.asyncio
    async def test_embed_single(self):
        provider = MockEmbeddingProvider()
        result = await provider.embed(["Hello world"])
        assert len(result) == 1
        assert len(result[0]) == 1536
        assert all(v == 0.0 for v in result[0])

    @pytest.mark.asyncio
    async def test_embed_multiple(self):
        provider = MockEmbeddingProvider()
        texts = ["Text 1", "Text 2", "Text 3"]
        result = await provider.embed(texts)
        assert len(result) == 3
        for vec in result:
            assert len(vec) == 1536

    @pytest.mark.asyncio
    async def test_embed_empty_list(self):
        provider = MockEmbeddingProvider()
        result = await provider.embed([])
        assert result == []


class TestEmbeddingFactory:
    def test_factory_mock(self):
        settings = EmbeddingSettings(provider="mock")
        provider = create_embedding_provider(settings)
        assert provider.provider_name == "mock"

    def test_factory_mock_when_no_key(self):
        settings = EmbeddingSettings(provider="openai", api_key="")
        provider = create_embedding_provider(settings)
        assert provider.provider_name == "mock"
