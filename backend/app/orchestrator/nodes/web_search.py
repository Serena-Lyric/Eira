"""Web search node — fallback when KB retrieval confidence is low."""

from __future__ import annotations

from typing import Any

import structlog
from app.orchestrator.state import ChatState

logger = structlog.get_logger(__name__)


async def web_search(
    state: ChatState,
    search_provider: Any = None,
) -> dict:
    """Perform web search and format results as context chunks.

    Args:
        state: Current chat state.
        search_provider: BaseSearchProvider instance (optional).
            If None, this node is a no-op.

    Returns:
        Dict with web_results and updated retrieved_chunks.
    """
    if search_provider is None:
        logger.info(
            "orchestrator.node.skip",
            node="web_search",
            reason="no_search_provider",
        )
        return {
            "web_results": [],
        }

    query = state.user_text
    if not query.strip():
        return {"web_results": []}

    try:
        results = await search_provider.search(query, top_k=5)

        web_results: list[dict[str, Any]] = []
        web_chunks: list[str] = []

        for r in results:
            web_results.append({
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "score": r.score,
            })
            web_chunks.append(f"[网络搜索: {r.title}] {r.snippet}\n来源: {r.url}")

        # Append web results to retrieved_chunks
        all_chunks = list(state.retrieved_chunks) + web_chunks

        logger.info(
            "orchestrator.node.end",
            node="web_search",
            result_count=len(results),
            query=query[:100],
        )

        return {
            "web_results": web_results,
            "retrieved_chunks": all_chunks,
        }

    except Exception as exc:
        logger.error(
            "orchestrator.node.error",
            node="web_search",
            error=str(exc),
        )
        return {
            "web_results": [],
        }
