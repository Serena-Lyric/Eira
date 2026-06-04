"""LangGraph orchestrator graph builder.

Node sequence (MVP):
    load_context → safety_in → llm_call → safety_out → persist → emit → END

Safety nodes are inserted between load_context and llm_call / after llm_call.
RAG retrieval will be inserted in Phase 2.
"""

from __future__ import annotations

from typing import Any, Callable, Coroutine

from langgraph.graph import StateGraph, END

from app.capabilities.llm.base import BaseLLMProvider
from app.orchestrator.state import ChatState
from app.orchestrator.nodes import load_context, llm_call, persist, emit

NodeFunc = Callable[[ChatState], Coroutine[Any, Any, dict]]


def _should_short_circuit(state: ChatState) -> str:
    """After safety_in: if the input is blocked, skip straight to emit."""
    return "emit" if not state.safety_in_ok else "llm_call"


def _after_llm(state: ChatState) -> str:
    """After llm_call: skip to emit if there's a hard error."""
    return "emit" if state.error else "safety_out"


def build_graph(
    provider: BaseLLMProvider,
    safety_in_fn: NodeFunc | None = None,
    safety_out_fn: NodeFunc | None = None,
) -> StateGraph:
    """Build and compile the LangGraph orchestrator graph.

    Args:
        provider: LLM provider instance injected into llm_call node.
        safety_in_fn: Optional custom safety_in node. Defaults to real safety_in.
        safety_out_fn: Optional custom safety_out node. Defaults to real safety_out.
    """
    if safety_in_fn is None:
        from app.orchestrator.nodes.safety_in import safety_in as _sin
        safety_in_fn = _sin
    if safety_out_fn is None:
        from app.orchestrator.nodes.safety_out import safety_out as _sout
        safety_out_fn = _sout

    safety_in = safety_in_fn
    safety_out = safety_out_fn

    # Wrap llm_call so it receives the provider without the graph needing to know
    async def _llm_call(state: ChatState) -> dict:
        return await llm_call.llm_call(state, provider)

    workflow = StateGraph(ChatState)

    # Add nodes
    workflow.add_node("load_context", load_context.load_context)
    workflow.add_node("safety_in", safety_in)
    workflow.add_node("llm_call", _llm_call)
    workflow.add_node("safety_out", safety_out)
    workflow.add_node("persist", persist.persist)
    workflow.add_node("emit", emit.emit)

    # Edges
    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "safety_in")
    workflow.add_conditional_edges("safety_in", _should_short_circuit, {
        "llm_call": "llm_call",
        "emit": "emit",
    })
    workflow.add_conditional_edges("llm_call", _after_llm, {
        "safety_out": "safety_out",
        "emit": "emit",
    })
    workflow.add_edge("safety_out", "persist")
    workflow.add_edge("persist", "emit")
    workflow.add_edge("emit", END)

    return workflow.compile()


# Convenience: build a graph with mock provider for tests
def build_mock_graph() -> Any:
    """Build a compiled graph backed by MockProvider (for tests)."""
    from app.capabilities.llm.mock import MockProvider
    return build_graph(MockProvider())
