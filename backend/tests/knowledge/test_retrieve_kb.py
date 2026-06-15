"""Unit tests for retrieve_kb orchestrator node."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from app.orchestrator.state import ChatState
from app.orchestrator.nodes.retrieve_kb import retrieve_kb, CONFIDENCE_THRESHOLD


class TestRetrieveKb:
    @pytest.mark.asyncio
    async def test_no_knowledge_service_passthrough(self):
        """When knowledge_service is None, node is a no-op."""
        state = ChatState(
            session_id="s1",
            user_id="1",
            user_text="西湖在哪里？",
            retrieved_chunks=["existing"],
        )
        result = await retrieve_kb(state, knowledge_service=None)

        assert result["retrieval_meta"]["skipped"] is True
        assert result["need_web_search"] is False
        assert result["retrieved_chunks"] == ["existing"]

    @pytest.mark.asyncio
    async def test_empty_query_skips(self):
        """Empty user_text skips retrieval."""
        state = ChatState(session_id="s1", user_id="1", user_text="")
        mock_svc = MagicMock()

        result = await retrieve_kb(state, knowledge_service=mock_svc)

        assert result["need_web_search"] is False
        mock_svc.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_high_confidence_no_web_search(self):
        """When top score >= threshold, no web search needed."""
        from app.domain.knowledge.service import SearchResult

        state = ChatState(session_id="s1", user_id="1", user_text="西湖")
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(return_value=[
            SearchResult(
                chunk_id=1, document_id=1,
                content="西湖位于杭州。",
                score=0.82,
                metadata={"filename": "guide.txt"},
            ),
        ])

        result = await retrieve_kb(state, knowledge_service=mock_svc)

        assert result["need_web_search"] is False
        assert len(result["retrieved_chunks"]) == 1
        assert result["retrieval_meta"]["top_score"] == 0.82

    @pytest.mark.asyncio
    async def test_low_confidence_triggers_web_search(self):
        """When top score < threshold, need_web_search is True."""
        from app.domain.knowledge.service import SearchResult

        state = ChatState(session_id="s1", user_id="1", user_text="奇怪的问题")
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(return_value=[
            SearchResult(
                chunk_id=1, document_id=1,
                content="无关内容。",
                score=0.45,
                metadata={"filename": "guide.txt"},
            ),
        ])

        result = await retrieve_kb(state, knowledge_service=mock_svc)

        assert result["need_web_search"] is True
        # Low-confidence chunks are filtered out
        assert len(result["retrieved_chunks"]) == 0
        assert len(result["knowledge_sources"]) == 0

    @pytest.mark.asyncio
    async def test_no_results_triggers_web_search(self):
        """Empty results trigger web search."""
        state = ChatState(session_id="s1", user_id="1", user_text="query")
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(return_value=[])

        result = await retrieve_kb(state, knowledge_service=mock_svc)

        assert result["need_web_search"] is True
        assert result["retrieval_meta"]["top_score"] == 0.0

    @pytest.mark.asyncio
    async def test_error_falls_back_to_web_search(self):
        """On error, fall through to web search."""
        state = ChatState(session_id="s1", user_id="1", user_text="query")
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(side_effect=RuntimeError("DB down"))

        result = await retrieve_kb(state, knowledge_service=mock_svc)

        assert result["need_web_search"] is True
        assert "error" in result["retrieval_meta"]

    @pytest.mark.asyncio
    async def test_boundary_threshold(self):
        """Test exact threshold boundary: 0.65 >= threshold passes."""
        from app.domain.knowledge.service import SearchResult

        state = ChatState(session_id="s1", user_id="1", user_text="query")
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(return_value=[
            SearchResult(
                chunk_id=1, document_id=1,
                content="刚好过线。",
                score=0.65,
                metadata={"filename": "doc.txt"},
            ),
        ])

        result = await retrieve_kb(state, knowledge_service=mock_svc)

        # 0.65 >= 0.65 → no web search
        assert result["need_web_search"] is False
        assert len(result["retrieved_chunks"]) == 1
