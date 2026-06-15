"""Smoke test for the LangGraph orchestrator pipeline (T1.2)."""

import pytest
from app.orchestrator.graph import build_mock_graph
from app.orchestrator.state import ChatState


@pytest.mark.asyncio
async def test_mock_graph_runs_end_to_end():
    """The full pipeline (load_context → llm_call → persist → emit) succeeds."""
    graph = build_mock_graph()
    state = ChatState(
        session_id="sess-001",
        user_id="1",
        user_text="你好，请介绍一下今天的路线",
    )
    # LangGraph compiled graph returns a dict (AddableUpdatesDict)
    result: dict = await graph.ainvoke(state)

    assert result.get("llm_text"), "Expected non-empty LLM response"
    assert len(result["llm_text"]) > 10, f"Response too short: {len(result['llm_text'])} chars"
    assert not result.get("error"), f"Unexpected error: {result.get('error')}"
    assert result.get("safety_in_ok") is True
    assert result.get("safety_out_ok") is True


@pytest.mark.asyncio
async def test_mock_graph_preserves_session_metadata():
    """Session id and user id survive the pipeline unchanged."""
    graph = build_mock_graph()
    state = ChatState(session_id="abc-123", user_id="42", user_text="Hello")
    result: dict = await graph.ainvoke(state)
    assert result.get("session_id") == "abc-123"
    assert result.get("user_id") == "42"


@pytest.mark.asyncio
async def test_mock_graph_can_run_multiple_times():
    """The compiled graph is reusable across invocations."""
    graph = build_mock_graph()
    for i in range(3):
        state = ChatState(session_id=f"s-{i}", user_id="1", user_text=f"Q{i}")
        result: dict = await graph.ainvoke(state)
        assert result.get("llm_text"), f"Empty response for iteration {i}"
        assert not result.get("error"), f"Error in iteration {i}: {result.get('error')}"
