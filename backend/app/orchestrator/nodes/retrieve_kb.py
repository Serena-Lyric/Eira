"""Retrieve knowledge base chunks via embedding similarity search.

If the top result score is below the confidence threshold,
sets need_web_search to True for downstream fallback.
"""

from __future__ import annotations

import math

from typing import Any

import structlog
from app.orchestrator.state import ChatState

logger = structlog.get_logger(__name__)

# Confidence threshold — if the best match score is below this,
# we trigger a web search fallback.
CONFIDENCE_THRESHOLD = 0.65
DEFAULT_TOP_K = 5


async def retrieve_kb(
    state: ChatState,
    knowledge_service: Any = None,
) -> dict:
    """Retrieve relevant knowledge chunks for the user query.

    Args:
        state: The current chat state containing user_text.
        knowledge_service: KnowledgeService instance (optional).
            If None, this node is a no-op passthrough.

    Returns:
        Dict of state updates with retrieved_chunks, knowledge_sources,
        retrieval_meta, and need_web_search flag.
    """
    if knowledge_service is None:
        logger.info(
            "orchestrator.node.skip",
            node="retrieve_kb",
            reason="no_knowledge_service",
        )
        return {
            "retrieval_meta": {"skipped": True, "reason": "no_knowledge_service"},
            "need_web_search": False,
            "knowledge_sources": state.knowledge_sources,
            "retrieved_chunks": state.retrieved_chunks,
        }

    query = state.user_text
    if not query.strip():
        return {
            "retrieval_meta": {"skipped": True, "reason": "empty_query"},
            "need_web_search": False,
            "knowledge_sources": state.knowledge_sources,
            "retrieved_chunks": [],
        }

    try:
        results = await knowledge_service.search(
            query=query,
            top_k=DEFAULT_TOP_K,
            min_score=0.0,  # Get all results, filter below
        )

        # Determine top score
        top_score = results[0].score if results else 0.0

        # Build retrieved_chunks (formatted for LLM context)
        retrieved_chunks: list[str] = []
        knowledge_sources: list[dict[str, Any]] = []

        for r in results:
            if r.score < CONFIDENCE_THRESHOLD:
                continue

            doc_name = r.metadata.get("filename", f"doc-{r.document_id}")
            retrieved_chunks.append(f"[来源: {doc_name}] {r.content}")
            knowledge_sources.append({
                "document_name": doc_name,
                "document_id": r.document_id,
                "chunk_index": r.metadata.get("chunk_index", 0),
                "score": 0.0 if math.isnan(r.score) else round(r.score, 4),
                "content_snippet": r.content[:200],
            })

        need_web_search = top_score < CONFIDENCE_THRESHOLD

        retrieval_meta = {
            "query": query[:200],
            "top_score": round(top_score, 4),
            "chunk_count": len(results),
            "threshold": CONFIDENCE_THRESHOLD,
            "need_web_search": need_web_search,
        }

        logger.info(
            "orchestrator.node.end",
            node="retrieve_kb",
            result_count=len(retrieved_chunks),
            top_score=round(top_score, 4),
            need_web_search=need_web_search,
        )

        return {
            "retrieved_chunks": retrieved_chunks,
            "knowledge_sources": knowledge_sources,
            "retrieval_meta": retrieval_meta,
            "need_web_search": need_web_search,
        }

    except Exception as exc:
        logger.error(
            "orchestrator.node.error",
            node="retrieve_kb",
            error=str(exc),
        )
        # On failure, fall through gracefully
        return {
            "retrieval_meta": {"error": str(exc)},
            "need_web_search": True,  # Try web search as fallback
            "knowledge_sources": [],
            "retrieved_chunks": state.retrieved_chunks,
        }
