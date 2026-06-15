"""LangGraph orchestrator graph builder.

Node sequence (Phase 2 with RAG):
    load_context → safety_in → retrieve_kb → (need_web_search? → web_search) → llm_call → safety_out → persist → emit → END

RAG retrieval and web search are inserted between safety_in and llm_call.
Both are optional — pass knowledge_service=None / search_provider=None to disable.
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
    return "emit" if not state.safety_in_ok else "retrieve_kb"


def _after_retrieve(state: ChatState) -> str:
    """After retrieve_kb: go to web_search if needed, otherwise llm_call."""
    return "web_search" if state.need_web_search else "llm_call"


def _after_web_search(state: ChatState) -> str:
    """After web_search: always proceed to llm_call."""
    return "llm_call"


def _after_llm(state: ChatState) -> str:
    """After llm_call: skip to emit if there's a hard error."""
    return "emit" if state.error else "safety_out"


def build_graph(
    provider: BaseLLMProvider,
    safety_in_fn: NodeFunc | None = None,
    safety_out_fn: NodeFunc | None = None,
    knowledge_service: Any = None,
    search_provider: Any = None,
) -> StateGraph:
    """Build and compile the LangGraph orchestrator graph.

    Args:
        provider: LLM provider instance injected into llm_call node.
        safety_in_fn: Optional custom safety_in node.
        safety_out_fn: Optional custom safety_out node.
        knowledge_service: Optional KnowledgeService for RAG (tests).
            When None, each invocation auto-instantiates from DB-aware settings.
        search_provider: Optional BaseSearchProvider (tests).
            When None, each invocation auto-instantiates from DB-aware settings.
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

    # Wrap retrieve_kb — uses injected service or auto-instantiates (§2 fix)
    async def _retrieve_kb(state: ChatState) -> dict:
        from app.orchestrator.nodes.retrieve_kb import retrieve_kb

        if knowledge_service is not None:
            return await retrieve_kb(state, knowledge_service)

        # Auto-instantiate with DB-aware settings
        from app.infra.db import get_session_factory
        from app.domain.knowledge.repository import KnowledgeRepository
        from app.domain.knowledge.service import KnowledgeService

        try:
            factory = get_session_factory()
            async with factory() as session:
                repo = KnowledgeRepository(session)
                svc = KnowledgeService(repo)
                await svc.init_embedding_provider()
                return await retrieve_kb(state, svc)
        except Exception as exc:
            import structlog
            structlog.get_logger(__name__).warning(
                "retrieve_kb.init_error", error=str(exc)
            )
            return await retrieve_kb(state, None)

    # Wrap web_search — uses injected provider or auto-instantiates (§2 fix)
    async def _web_search(state: ChatState) -> dict:
        from app.orchestrator.nodes.web_search import web_search

        if search_provider is not None:
            return await web_search(state, search_provider)

        # Auto-instantiate with DB-aware settings
        from app.capabilities.effective_settings import get_effective_search_settings
        from app.capabilities.search.factory import create_search_provider

        try:
            search_settings = await get_effective_search_settings()
            provider = create_search_provider(search_settings)
            return await web_search(state, provider)
        except Exception as exc:
            import structlog
            structlog.get_logger(__name__).warning(
                "web_search.init_error", error=str(exc)
            )
            return await web_search(state, None)

    workflow = StateGraph(ChatState)

    # Add nodes
    workflow.add_node("load_context", load_context.load_context)
    workflow.add_node("safety_in", safety_in)
    workflow.add_node("retrieve_kb", _retrieve_kb)
    workflow.add_node("web_search", _web_search)
    workflow.add_node("llm_call", _llm_call)
    workflow.add_node("safety_out", safety_out)
    workflow.add_node("persist", persist.persist)
    workflow.add_node("emit", emit.emit)

    # Edges
    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "safety_in")
    workflow.add_conditional_edges("safety_in", _should_short_circuit, {
        "retrieve_kb": "retrieve_kb",
        "emit": "emit",
    })
    workflow.add_conditional_edges("retrieve_kb", _after_retrieve, {
        "web_search": "web_search",
        "llm_call": "llm_call",
    })
    workflow.add_edge("web_search", "llm_call")
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
