"""Unit tests for knowledge models and schemas."""

import pytest
from app.domain.knowledge.models import Document, DocumentChunk
from app.domain.knowledge.schemas import (
    DocumentOut,
    DocumentUploadOut,
    ChunkOut,
    ProgressOut,
    DeleteOut,
)


class TestDocumentModel:
    def test_document_required_fields(self):
        """Document model can be instantiated with required fields."""
        doc = Document(
            filename="test.pdf",
            oss_key="eira-documents/1/test.pdf",
            mime_type="application/pdf",
            file_size=1024,
            uploader_id=1,
            status="pending",
            chunk_count=0,
        )
        assert doc.filename == "test.pdf"
        assert doc.oss_key == "eira-documents/1/test.pdf"
        assert doc.mime_type == "application/pdf"
        assert doc.status == "pending"
        assert doc.chunk_count == 0
        assert doc.error is None

    def test_document_table_name(self):
        assert Document.__tablename__ == "documents"

    def test_document_chunk_table_name(self):
        assert DocumentChunk.__tablename__ == "knowledge_chunks"

    def test_document_chunk_embedding_dimension(self):
        """Embedding column should be Vector(1536) for text-embedding-3-small."""
        from pgvector.sqlalchemy import Vector
        col = DocumentChunk.__table__.columns["embedding"]
        assert isinstance(col.type, Vector)
        assert col.type.dim == 1536


class TestDocumentSchemas:
    def test_document_upload_out(self):
        out = DocumentUploadOut(document_id=1, filename="test.pdf", status="pending")
        assert out.document_id == 1
        assert "等待处理" in out.message

    def test_progress_out_defaults(self):
        out = ProgressOut(document_id=1, status="pending")
        assert out.progress == 0.0
        assert out.stage is None
        assert out.error is None

    def test_delete_out(self):
        out = DeleteOut()
        assert out.success is True

    def test_document_out_from_attributes_config(self):
        assert DocumentOut.model_config.get("from_attributes") is True
