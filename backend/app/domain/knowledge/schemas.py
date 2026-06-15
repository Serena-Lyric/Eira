"""Pydantic schemas for knowledge documents and chunks API."""

from datetime import datetime
from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: int
    filename: str
    oss_key: str
    mime_type: str
    file_size: int
    status: str
    chunk_count: int
    error: str | None = None
    uploader_id: int
    created_at: datetime
    updated_at: datetime
    progress: float | None = None  # from Redis, only for 'processing' docs

    model_config = {"from_attributes": True}


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    total: int


class DocumentDetailOut(DocumentOut):
    """Document detail including chunk preview."""
    chunks: list["ChunkOut"] = Field(default_factory=list)


class ChunkOut(BaseModel):
    id: int
    document_id: int
    chunk_index: int
    content: str
    metadata_json: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadOut(BaseModel):
    document_id: int
    filename: str
    status: str
    message: str = "文档已上传，等待处理"


class ReprocessOut(BaseModel):
    document_id: int
    status: str
    message: str = "重新处理已触发"


class DeleteOut(BaseModel):
    success: bool = True
    message: str = "文档已删除"


class ProgressOut(BaseModel):
    document_id: int
    status: str
    stage: str | None = None
    progress: float = 0.0
    error: str | None = None
