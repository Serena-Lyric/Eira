"""ChatState — the shared state object flowing through LangGraph nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatState:
    """Mutable state propagated through the orchestrator graph.

    Fields are populated by nodes in pipeline order:
        load_context → safety_in → llm_call → safety_out → persist → emit
    """

    # ── request identity ──
    session_id: str = ""
    user_id: str = ""
    request_id: str = ""

    # ── input ──
    user_text: str = ""

    # ── context (from DB / external sources) ──
    history: list[dict[str, Any]] = field(default_factory=list)
    persona_prompt: str = ""
    retrieved_chunks: list[str] = field(default_factory=list)

    # ── safety gates ──
    safety_in_ok: bool = True
    safety_in_reason: str = ""
    safety_out_ok: bool = True
    safety_out_reason: str = ""

    # ── LLM output ──
    llm_text: str = ""
    llm_meta: dict[str, Any] = field(default_factory=dict)

    # ── RAG / retrieval (Phase 2) ──
    retrieval_meta: dict[str, Any] = field(default_factory=dict)
    need_web_search: bool = False
    web_results: list[dict[str, Any]] = field(default_factory=list)
    knowledge_sources: list[dict[str, Any]] = field(default_factory=list)

    # ── final error ──
    error: str = ""
