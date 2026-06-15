"""Embedding capability — abstract base and factory."""

from abc import ABC, abstractmethod


class BaseEmbeddingProvider(ABC):
    """Abstract embedding provider.

    All business code must call through this interface; never import
    provider-specific SDKs directly.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def dimensions(self) -> int: ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of input texts to embed.

        Returns:
            List of embedding vectors, each of length self.dimensions.
        """
        ...
