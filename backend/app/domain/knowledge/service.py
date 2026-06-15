"""Knowledge service — document processing pipeline and search."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.infra.oss import get_oss_client
from app.core.config import get_settings
from app.capabilities.embedding.factory import create_embedding_provider
from app.capabilities.embedding import BaseEmbeddingProvider
from .models import Document, DocumentChunk
from .repository import KnowledgeRepository
from .parsers import EmptyTextError, get_parser, ParsedDocument
from .chunker import DocumentChunker

logger = structlog.get_logger(__name__)

OSS_BUCKET = "eira-documents"


@dataclass
class SearchResult:
    """A single search result with chunk and similarity score."""
    chunk_id: int
    document_id: int
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeService:
    """Orchestrates the knowledge pipeline: parse → chunk → embed → index."""

    def __init__(
        self,
        repo: KnowledgeRepository,
        embedding_provider: BaseEmbeddingProvider | None = None,
    ):
        self.repo = repo
        self._embedding_provider = embedding_provider
        self._chunker = DocumentChunker()

    @property
    def embedding_provider(self) -> BaseEmbeddingProvider:
        if self._embedding_provider is None:
            settings = get_settings().embedding
            self._embedding_provider = create_embedding_provider(settings)
        return self._embedding_provider

    async def init_embedding_provider(self) -> BaseEmbeddingProvider:
        """Initialize or re-initialize embedding provider with DB-aware settings.

        Falls back to mock provider if the real API is unreachable (e.g. 403 in dev).
        """
        from app.capabilities.effective_settings import get_effective_embedding_settings
        settings = await get_effective_embedding_settings()
        try:
            provider = create_embedding_provider(settings)
            # Quick connectivity test — if the provider is not mock, verify it works
            if settings.provider != "mock":
                import asyncio
                test_embed = await asyncio.wait_for(
                    provider.embed(["test"]), timeout=5.0
                )
                if not test_embed:
                    raise RuntimeError("Embedding API returned empty result")
            self._embedding_provider = provider
        except Exception as exc:
            logger.warning(
                "embedding.init_fallback_to_mock",
                provider=settings.provider,
                error=str(exc)[:200],
            )
            # Fall back to mock for graceful degradation
            from app.capabilities.embedding.openai_compat import MockEmbeddingProvider
            self._embedding_provider = MockEmbeddingProvider()
        return self._embedding_provider

    async def process_document(self, document_id: int) -> None:
        """Run the full processing pipeline for a document.

        Steps: download from OSS → parse → chunk → embed → store.
        Updates document status through each stage.
        """
        t0 = time.perf_counter()

        # 1. Load document
        doc = await self.repo.get_document(document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        await self.repo.update_document_status(document_id, "processing")

        try:
            # 2. Download from OSS
            oss = get_oss_client()
            response = oss.get_object(Bucket=OSS_BUCKET, Key=doc.oss_key)
            content = response["Body"].read()

            # 3. Parse
            parser_cls = get_parser(doc.mime_type)
            if parser_cls is None:
                raise ValueError(f"No parser for MIME type: {doc.mime_type}")

            parser = parser_cls()
            try:
                parsed: ParsedDocument = await parser.parse(content, doc.filename)
            except EmptyTextError as e:
                await self.repo.update_document_status(
                    document_id, "failed", error=str(e)
                )
                return

            # 4. Chunk
            chunks = self._chunker.chunk(
                parsed.text,
                base_metadata={
                    "filename": doc.filename,
                    "page_count": parsed.page_count,
                    **parsed.metadata,
                },
            )

            if not chunks:
                await self.repo.update_document_status(
                    document_id, "failed", error="No chunks produced from document"
                )
                return

            # 5. Embed
            chunk_texts = [c.text for c in chunks]
            embeddings = await self.embedding_provider.embed(chunk_texts)

            if len(embeddings) != len(chunks):
                raise RuntimeError(
                    f"Embedding count mismatch: {len(embeddings)} != {len(chunks)}"
                )

            # 6. Store chunks (atomic replace)
            doc_chunks = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                doc_chunks.append(
                    DocumentChunk(
                        document_id=document_id,
                        chunk_index=i,
                        content=chunk.text,
                        embedding=embedding,
                        metadata_json=json.dumps(chunk.metadata, ensure_ascii=False),
                    )
                )

            await self.repo.replace_chunks(document_id, doc_chunks)
            await self.repo.update_chunk_count(document_id, len(doc_chunks))
            await self.repo.update_document_status(document_id, "ready")

            latency_ms = (time.perf_counter() - t0) * 1000
            logger.info(
                "knowledge.pipeline.complete",
                document_id=document_id,
                filename=doc.filename,
                chunk_count=len(doc_chunks),
                latency_ms=round(latency_ms, 2),
            )

        except Exception as exc:
            await self.repo.update_document_status(
                document_id, "failed", error=str(exc)
            )
            logger.error(
                "knowledge.pipeline.error",
                document_id=document_id,
                error=str(exc),
            )
            raise

    async def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.65,
    ) -> list[SearchResult]:
        """Search knowledge base by embedding similarity.

        Args:
            query: The search query text.
            top_k: Number of results to return.
            min_score: Minimum cosine similarity threshold.

        Returns:
            List of SearchResult sorted by score descending.
        """
        # Generate query embedding
        embeddings = await self.embedding_provider.embed([query])
        if not embeddings:
            return []

        query_vec = embeddings[0]

        # KNN search
        results = await self.repo.search_similar(query_vec, top_k, min_score)

        search_results = []
        for chunk, score in results:
            metadata = {}
            if chunk.metadata_json:
                try:
                    metadata = json.loads(chunk.metadata_json)
                except json.JSONDecodeError:
                    pass

            search_results.append(
                SearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    score=score,
                    metadata=metadata,
                )
            )

        logger.info(
            "knowledge.search",
            query=query[:100],
            top_k=top_k,
            result_count=len(search_results),
            top_score=search_results[0].score if search_results else 0.0,
        )

        return search_results

    async def reprocess_document(self, document_id: int) -> None:
        """Delete all chunks and re-run the pipeline for a document."""
        doc = await self.repo.get_document(document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        # Reset status
        await self.repo.update_document_status(document_id, "pending")
        await self.repo.replace_chunks(document_id, [])
        await self.repo.update_chunk_count(document_id, 0)

        # Re-run pipeline
        await self.process_document(document_id)
