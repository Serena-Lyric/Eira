"""Unit tests for web search providers."""

import pytest
from app.capabilities.search import SearchResult
from app.capabilities.search.tavily import MockSearchProvider
from app.capabilities.search.factory import create_search_provider
from app.core.config import SearchSettings


class TestMockSearchProvider:
    @pytest.mark.asyncio
    async def test_provider_name(self):
        provider = MockSearchProvider()
        assert provider.provider_name == "mock"

    @pytest.mark.asyncio
    async def test_search_returns_empty(self):
        provider = MockSearchProvider()
        results = await provider.search("test query")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_respects_top_k_type(self):
        provider = MockSearchProvider()
        results = await provider.search("test", top_k=10)
        assert isinstance(results, list)
        assert len(results) == 0


class TestSearchFactory:
    def test_factory_mock(self):
        settings = SearchSettings(provider="mock")
        provider = create_search_provider(settings)
        assert provider.provider_name == "mock"

    def test_factory_mock_when_no_key(self):
        settings = SearchSettings(provider="tavily", api_key="")
        provider = create_search_provider(settings)
        assert provider.provider_name == "mock"


class TestSearchResult:
    def test_search_result_defaults(self):
        result = SearchResult(
            title="Test",
            url="https://example.com",
            snippet="A test result",
        )
        assert result.score == 1.0
        assert result.title == "Test"
