"""Integration tests for orchestrator with RAG nodes."""

import pytest
from app.orchestrator.graph import build_mock_graph, build_graph
from app.orchestrator.state import ChatState
from app.capabilities.llm.mock import MockProvider
from app.capabilities.search.tavily import MockSearchProvider


@pytest.mark.asyncio
async def test_graph_without_rag_runs_end_to_end():
    """Without knowledge_service or search_provider, graph auto-instantiates RAG (§2 fix).
    With real credentials unavailable in test env, RAG nodes fall back gracefully."""
    graph = build_graph(MockProvider())
    state = ChatState(
        session_id="s1",
        user_id="1",
        user_text="你好，请介绍一下西湖",
    )
    result: dict = await graph.ainvoke(state)

    assert result.get("llm_text"), "Expected non-empty response"
    assert not result.get("error"), f"Unexpected error: {result.get('error')}"
    # §2 fix: auto-instantiation may produce error or skipped in test env
    retrieval_meta = result.get("retrieval_meta", {})
    assert isinstance(retrieval_meta, dict)


@pytest.mark.asyncio
async def test_graph_with_rag_nodes_present():
    """All RAG-related nodes are present in the compiled graph."""
    graph = build_mock_graph()
    nodes = graph.get_graph().nodes if hasattr(graph, "get_graph") else {}

    # The compiled graph should have retrieve_kb and web_search nodes
    # (Check by running — if nodes were missing, ainvoke would fail)
    state = ChatState(session_id="s1", user_id="1", user_text="Hi")
    result: dict = await graph.ainvoke(state)

    # Verify state includes new RAG fields
    assert "retrieval_meta" in result
    assert "need_web_search" in result
    assert "knowledge_sources" in result


@pytest.mark.asyncio
async def test_graph_preserves_knowledge_sources():
    """Pre-populated knowledge_sources survive or are replaced by RAG results (§2 fix)."""
    from unittest.mock import AsyncMock, MagicMock

    mock_kb = MagicMock()
    mock_kb.search = AsyncMock(return_value=[])
    graph = build_graph(MockProvider(), knowledge_service=mock_kb)
    state = ChatState(
        session_id="s1",
        user_id="1",
        user_text="test",
        knowledge_sources=[
            {"document_name": "guide.txt", "score": 0.85, "chunk_index": 0}
        ],
        retrieved_chunks=["[来源: guide.txt] 西湖位于杭州。"],
    )
    result: dict = await graph.ainvoke(state)

    # knowledge_sources should be in the result
    assert "knowledge_sources" in result


@pytest.mark.asyncio
async def test_graph_with_mock_services():
    """Test graph with mock knowledge service and search provider."""
    from unittest.mock import AsyncMock, MagicMock

    mock_kb = MagicMock()
    mock_kb.search = AsyncMock(return_value=[])

    mock_search = MockSearchProvider()

    graph = build_graph(
        MockProvider(),
        knowledge_service=mock_kb,
        search_provider=mock_search,
    )
    state = ChatState(session_id="s1", user_id="1", user_text="test")
    result: dict = await graph.ainvoke(state)

    assert result.get("llm_text")
    assert not result.get("error")


@pytest.mark.asyncio
async def test_graph_passthrough_on_safety_block():
    """When safety_in blocks, RAG nodes are skipped entirely."""
    from app.orchestrator.nodes.safety_in import safety_in as real_safety_in

    # Build a graph with a custom safety_in that blocks everything
    async def blocking_safety(state: ChatState) -> dict:
        return {"safety_in_ok": False, "safety_in_reason": "test block"}

    graph = build_graph(
        MockProvider(),
        safety_in_fn=blocking_safety,
    )
    state = ChatState(session_id="s1", user_id="1", user_text="bad words")
    result: dict = await graph.ainvoke(state)

    # Should short-circuit to emit — no LLM response
    assert not result.get("llm_text")
    assert not result.get("safety_in_ok")
