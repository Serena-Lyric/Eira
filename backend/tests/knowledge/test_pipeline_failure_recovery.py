"""Integration tests for knowledge pipeline failure recovery."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.domain.knowledge.models import Document
from app.domain.knowledge.service import KnowledgeService
from app.domain.knowledge.repository import KnowledgeRepository
from app.capabilities.embedding.openai_compat import MockEmbeddingProvider


@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=KnowledgeRepository)
    repo.get_document = AsyncMock()
    repo.update_document_status = AsyncMock()
    repo.update_chunk_count = AsyncMock()
    repo.replace_chunks = AsyncMock()
    repo.delete_document = AsyncMock()
    return repo


class TestPipelineFailureRecovery:
    @pytest.mark.asyncio
    async def test_pipeline_marks_failed_on_oss_error(self, mock_repo):
        """When OSS download fails, document should be marked as failed."""
        # Import parsers for registry
        import app.domain.knowledge.parsers.text  # noqa: F401

        svc = KnowledgeService(mock_repo, MockEmbeddingProvider())

        doc = Document(
            id=1, filename="test.txt",
            oss_key="documents/1/test.txt",
            mime_type="text/plain",
            file_size=100, status="pending",
            chunk_count=0, uploader_id=1,
        )
        mock_repo.get_document.return_value = doc

        with patch("app.domain.knowledge.service.get_oss_client") as mock_oss:
            mock_oss.side_effect = RuntimeError("OSS connection failed")

            with pytest.raises(RuntimeError):
                await svc.process_document(1)

            # Should have been marked as processing first, then failed
            status_calls = [
                call[0][1] for call in mock_repo.update_document_status.call_args_list
            ]
            assert "processing" in status_calls
            assert "failed" in status_calls

    @pytest.mark.asyncio
    async def test_pipeline_marks_failed_on_empty_text(self, mock_repo):
        """When parsing yields no text, document should be marked as failed."""
        import app.domain.knowledge.parsers.text  # noqa: F401

        svc = KnowledgeService(mock_repo, MockEmbeddingProvider())

        doc = Document(
            id=1, filename="empty.txt",
            oss_key="documents/1/empty.txt",
            mime_type="text/plain",
            file_size=10, status="pending",
            chunk_count=0, uploader_id=1,
        )
        mock_repo.get_document.return_value = doc

        with patch("app.domain.knowledge.service.get_oss_client") as mock_oss:
            mock_oss_client = MagicMock()
            mock_oss.return_value = mock_oss_client
            mock_body = MagicMock()
            # Return very short text — below 20 char threshold
            mock_body.read.return_value = b"short"
            mock_oss_client.get_object.return_value = {"Body": mock_body}

            await svc.process_document(1)

            # Should be marked as failed with empty_text error
            failed_call = None
            for call in mock_repo.update_document_status.call_args_list:
                if call[0][1] == "failed":
                    failed_call = call
                    break
            assert failed_call is not None
            error_msg = failed_call.kwargs.get("error", "")
            assert "no meaningful content" in error_msg.lower() or "empty" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_reprocess_clears_existing_chunks(self, mock_repo):
        """Reprocess should clear old chunks before re-running."""
        import app.domain.knowledge.parsers.text  # noqa: F401

        svc = KnowledgeService(mock_repo, MockEmbeddingProvider())

        doc = Document(
            id=1, filename="test.txt",
            oss_key="documents/1/test.txt",
            mime_type="text/plain",
            file_size=200, status="ready",
            chunk_count=10, uploader_id=1,
        )
        mock_repo.get_document.return_value = doc

        with patch("app.domain.knowledge.service.get_oss_client") as mock_oss:
            mock_oss_client = MagicMock()
            mock_oss.return_value = mock_oss_client
            mock_body = MagicMock()
            mock_body.read.return_value = (
                "这是第一段测试内容，包含足够多的文字来满足最小段落过滤要求。"
                "我们需要确保这段文本在被分词器处理后能够产生至少八十个令牌。"
                "这是第二段测试内容，提供了更多上下文信息来验证管线恢复功能。"
                "文档处理系统需要足够长的文本才能正确地进行分块和嵌入操作。"
                "这是第三段测试内容，补充额外的文字以确保总令牌数远超最低阈值。"
                "通过提供充足的数据，我们可以验证重新处理功能是否按预期工作。"
                "这是第四段测试内容，继续添加更多段落来满足测试覆盖的要求。"
                "端到端的知识管线测试需要模拟真实的文档处理场景和边界条件。"
            ).encode("utf-8")
            mock_oss_client.get_object.return_value = {"Body": mock_body}

            await svc.reprocess_document(1)

            # First call to replace_chunks should be with empty list (cleanup)
            replace_calls = mock_repo.replace_chunks.call_args_list
            assert len(replace_calls) >= 2  # one for cleanup, one for new chunks
            assert replace_calls[0][0][1] == []  # empty chunks for reset


class TestWorkerFailureRecovery:
    """Tests for the async worker module."""

    @pytest.mark.asyncio
    async def test_worker_handles_error_gracefully(self):
        """Worker should mark document as failed on error, not crash."""
        from app.workers.knowledge_worker import run_knowledge_pipeline

        # This test requires a running DB — skip if not available
        pytest.skip("Requires running PostgreSQL for full integration test")
