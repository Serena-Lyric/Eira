"""Web Search capability — abstract base and factory."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SearchResult:
    """A single web search result."""
    title: str
    url: str
    snippet: str
    score: float = 1.0


class BaseSearchProvider(ABC):
    """Abstract web search provider.

    All business code must call through this interface; never import
    provider-specific SDKs directly.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search the web for the given query."""
        ...
