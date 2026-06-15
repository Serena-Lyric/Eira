"""Unit tests for KnowledgeService pipeline and search."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.domain.knowledge.service import KnowledgeService, SearchResult
from app.domain.knowledge.models import Document, DocumentChunk
from app.domain.knowledge.repository import KnowledgeRepository
from app.capabilities.embedding.openai_compat import MockEmbeddingProvider

# Import parsers to trigger registry registration
import app.domain.knowledge.parsers.text  # noqa: F401
import app.domain.knowledge.parsers.pdf  # noqa: F401
import app.domain.knowledge.parsers.docx  # noqa: F401
import app.domain.knowledge.parsers.markdown  # noqa: F401


@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=KnowledgeRepository)
    repo.get_document = AsyncMock()
    repo.update_document_status = AsyncMock()
    repo.update_chunk_count = AsyncMock()
    repo.replace_chunks = AsyncMock()
    repo.search_similar = AsyncMock()
    repo.delete_document = AsyncMock()
    return repo


@pytest.fixture
def embedding_provider():
    return MockEmbeddingProvider()


@pytest.fixture
def sample_document():
    return Document(
        id=1,
        filename="test.pdf",
        oss_key="eira-documents/1/test.pdf",
        mime_type="text/plain",
        file_size=1024,
        status="pending",
        chunk_count=0,
        uploader_id=1,
    )


class TestKnowledgeServiceSearch:
    @pytest.mark.asyncio
    async def test_search_returns_results(self, mock_repo, embedding_provider):
        svc = KnowledgeService(mock_repo, embedding_provider)

        # Mock search_similar to return a result
        mock_chunk = DocumentChunk(
            id=1,
            document_id=1,
            chunk_index=0,
            content="西湖位于杭州。",
            metadata_json=json.dumps({"filename": "test.txt"}),
        )
        mock_repo.search_similar.return_value = [(mock_chunk, 0.85)]

        results = await svc.search("西湖在哪里？", top_k=5, min_score=0.65)

        assert len(results) == 1
        assert results[0].score == 0.85
        assert "西湖" in results[0].content
        assert results[0].document_id == 1
        mock_repo.search_similar.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_filters_below_threshold(self, mock_repo, embedding_provider):
        svc = KnowledgeService(mock_repo, embedding_provider)

        mock_repo.search_similar.return_value = []  # No results meet threshold

        results = await svc.search("query", top_k=5, min_score=0.65)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_passes_correct_top_k(self, mock_repo, embedding_provider):
        svc = KnowledgeService(mock_repo, embedding_provider)

        mock_chunk = DocumentChunk(
            id=1, document_id=1, chunk_index=0, content="test",
            metadata_json="{}",
        )
        mock_repo.search_similar.return_value = [(mock_chunk, 0.9)]

        await svc.search("query", top_k=3, min_score=0.5)
        # Verify top_k was passed to repo
        call_kwargs = mock_repo.search_similar.call_args
        assert call_kwargs[0][1] == 3  # top_k


class TestKnowledgeServiceReprocess:
    @pytest.mark.asyncio
    async def test_reprocess_resets_status(self, mock_repo, embedding_provider):
        svc = KnowledgeService(mock_repo, embedding_provider)

        doc = Document(
            id=1,
            filename="test.pdf",
            oss_key="eira-documents/1/test.pdf",
            mime_type="text/plain",
            file_size=1024,
            status="ready",
            chunk_count=5,
            uploader_id=1,
        )
        mock_repo.get_document.return_value = doc

        # process_document will try to download from OSS, so we mock it too
        with patch("app.domain.knowledge.service.get_oss_client") as mock_oss:
            # Mock OSS to return text content
            mock_oss_client = MagicMock()
            mock_oss.return_value = mock_oss_client
            mock_body = MagicMock()
            mock_body.read.return_value = (
                "这是一段测试文档内容。包含足够多的字符来满足最小段落过滤要求。"
                "第二段内容也提供了更多信息来验证管线是否正常运行。"
            ).encode("utf-8")
            mock_oss_client.get_object.return_value = {"Body": mock_body}

            await svc.reprocess_document(1)

            # Check status was reset to pending
            assert mock_repo.update_document_status.call_count >= 1
            # First call should reset to pending
            first_call = mock_repo.update_document_status.call_args_list[0]
            assert first_call[0][0] == 1
            assert first_call[0][1] == "pending"

            # replace_chunks should be called with empty list first
            replace_calls = mock_repo.replace_chunks.call_args_list
            assert len(replace_calls) >= 1
            assert replace_calls[0][0][1] == []  # Empty chunks for reset

    @pytest.mark.asyncio
    async def test_reprocess_document_not_found(self, mock_repo, embedding_provider):
        svc = KnowledgeService(mock_repo, embedding_provider)
        mock_repo.get_document.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await svc.reprocess_document(999)
