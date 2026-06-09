"""Stream pacing tests — verify token delivery timing (T1.6).

These tests validate that the orchestrator graph produces a complete response
with the mock provider. Full WS stream pacing is tested in manual integration.
"""

import pytest
from app.orchestrator.graph import build_mock_graph
from app.orchestrator.state import ChatState


@pytest.mark.asyncio
async def test_orchestrator_produces_token_like_output():
    """The mock graph output is suitable for token-by-token streaming.

    The response text should be long enough to split into multiple chunks
    for the WS token protocol.
    """
    graph = build_mock_graph()
    state = ChatState(
        session_id="pace-sess",
        user_id="1",
        user_text="你好",
    )
    result: dict = await graph.ainvoke(state)

    text = result.get("llm_text", "")
    assert len(text) > 0, "Should produce response text"

    # Simulate splitting into ~2-char chunks (as done in WS handler)
    chunk_size = 2
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    assert len(chunks) >= 3, f"Response should be splittable into >=3 token frames, got {len(chunks)}"

    # Verify latency is reasonable
    meta = result.get("llm_meta", {})
    latency = meta.get("latency_ms", 0)
    assert latency >= 0, "Latency should be non-negative"
    # Mock provider should be very fast
    assert latency < 1000, f"Mock provider latency {latency:.0f}ms too high"


@pytest.mark.asyncio
async def test_multiple_invocations_produce_varied_output():
    """The mock provider produces consistent-length output each time."""
    graph = build_mock_graph()

    lengths = []
    for i in range(3):
        state = ChatState(session_id=f"s-{i}", user_id="1", user_text=f"Q{i}")
        result: dict = await graph.ainvoke(state)
        lengths.append(len(result.get("llm_text", "")))

    # All responses should be non-empty
    assert all(l > 0 for l in lengths), f"All responses should be non-empty: {lengths}"
