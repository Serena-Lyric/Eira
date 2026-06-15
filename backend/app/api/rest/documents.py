"""REST endpoints for document upload, list, delete, and reprocess."""

import structlog
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db_session, get_current_user, require_admin, check_upload_rate_limit
from app.domain.identity.models import User
from app.domain.knowledge.models import Document
from app.domain.knowledge.repository import KnowledgeRepository
from app.domain.knowledge.schemas import (
    DocumentOut,
    DocumentListOut,
    DocumentDetailOut,
    DocumentUploadOut,
    ReprocessOut,
    DeleteOut,
    ProgressOut,
    ChunkOut,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
OSS_BUCKET = "eira-documents"


def _to_document_out(doc: Document) -> DocumentOut:
    return DocumentOut.model_validate(doc)


# ── Schemas ──────────────────────────────────────────────────────────


class DocumentListParams(BaseModel):
    status: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ── Upload ───────────────────────────────────────────────────────────


@router.post("/upload", status_code=201, response_model=DocumentUploadOut)
async def upload_document(
    file: UploadFile = File(...),
    bg_tasks: BackgroundTasks = BackgroundTasks(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    _rate: None = Depends(check_upload_rate_limit),
) -> DocumentUploadOut:
    """Upload a document for knowledge base processing.

    Supported formats: PDF, DOCX, TXT, MD. Max size: 50 MB.
    Processing starts automatically in the background after upload.
    """
    if not file.filename:
        raise HTTPException(400, "文件名不能为空")

    # Validate MIME type
    mime = file.content_type or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            400,
            f"不支持的文件类型: {mime}。支持: {', '.join(sorted(ALLOWED_MIME_TYPES))}",
        )

    # Read file content
    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"文件大小超过限制 ({MAX_FILE_SIZE // 1024 // 1024} MB)")

    if len(content) == 0:
        raise HTTPException(400, "文件内容为空")

    # Validate magic number
    from app.core.file_validation import validate_magic
    if not validate_magic(content, mime):
        raise HTTPException(400, "文件内容与声明的格式不匹配")

    # Upload to OSS
    from app.infra.oss import get_oss_client

    repo = KnowledgeRepository(db)
    doc = Document(
        filename=file.filename,
        oss_key="",  # placeholder, set after generating key
        mime_type=mime,
        file_size=len(content),
        status="pending",
        chunk_count=0,
        uploader_id=user.id,
    )
    doc = await repo.create_document(doc)

    # Generate OSS key and upload
    oss_key = f"documents/{doc.id}/{file.filename}"
    oss = get_oss_client()
    oss.put_object(Bucket=OSS_BUCKET, Key=oss_key, Body=content)

    # Update OSS key
    doc.oss_key = oss_key
    await db.flush()

    # Commit before triggering background processing so the worker can see the document
    await db.commit()

    # Trigger background processing
    bg_tasks.add_task(_run_pipeline_background, doc.id)

    return DocumentUploadOut(
        document_id=doc.id,
        filename=file.filename,
        status="pending",
    )


async def _run_pipeline_background(document_id: int) -> None:
    """Background task wrapper with safety net (§6.2).

    If the pipeline fails (even before it can update status itself),
    we force-set the document to 'failed' so it doesn't get stuck in
    'pending' / 'processing' forever.
    """
    try:
        from app.workers.knowledge_worker import run_knowledge_pipeline
        await run_knowledge_pipeline(document_id)
    except Exception as exc:
        logger.error("knowledge.pipeline.fatal", document_id=document_id, error=str(exc))
        await _ensure_terminal_status(document_id, str(exc))


async def _ensure_terminal_status(document_id: int, error: str) -> None:
    """If the document is not in a terminal state, force-set it to 'failed'."""
    try:
        from app.infra.db import get_session_factory
        from app.domain.knowledge.repository import KnowledgeRepository

        factory = get_session_factory()
        async with factory() as session:
            repo = KnowledgeRepository(session)
            doc = await repo.get_document(document_id)
            if doc is None:
                return
            if doc.status in ("ready", "failed"):
                return
            await repo.update_document_status(
                document_id, "failed", error=f"Fatal: {error}"
            )
            await session.commit()
            logger.info(
                "knowledge.pipeline.safety_net",
                document_id=document_id,
                previous_status=doc.status,
            )
    except Exception as inner_exc:
        logger.error(
            "knowledge.pipeline.safety_net_failed",
            document_id=document_id,
            error=str(inner_exc),
        )


# ── List ─────────────────────────────────────────────────────────────


@router.get("", response_model=DocumentListOut)
async def list_documents(
    status: str | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DocumentListOut:
    """List documents. Admins see all; visitors see only their own uploads."""
    repo = KnowledgeRepository(db)

    if user.role == "admin":
        uploader_id = None
    else:
        uploader_id = user.id

    status_filter = [s.strip() for s in status.split(",")] if status else None

    offset = (page - 1) * page_size
    items, total = await repo.list_documents(
        uploader_id=uploader_id,
        status_filter=status_filter,
        limit=page_size,
        offset=offset,
    )

    return DocumentListOut(
        items=[_to_document_out(d) for d in items],
        total=total,
    )


# ── Detail ───────────────────────────────────────────────────────────


@router.get("/{document_id}", response_model=DocumentDetailOut)
async def get_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DocumentDetailOut:
    """Get document details including chunk list."""
    repo = KnowledgeRepository(db)
    doc = await repo.get_document(document_id)

    if doc is None:
        raise HTTPException(404, "文档不存在")

    # Permission: admin or owner
    if user.role != "admin" and doc.uploader_id != user.id:
        raise HTTPException(404, "文档不存在")

    chunks = await repo.get_chunks(document_id)
    chunk_outs = [ChunkOut.model_validate(c) for c in chunks]

    detail = DocumentDetailOut.model_validate(doc)
    detail.chunks = chunk_outs
    return detail


# ── Progress ─────────────────────────────────────────────────────────


@router.get("/{document_id}/progress", response_model=ProgressOut)
async def get_document_progress(
    document_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ProgressOut:
    """Get document processing progress."""
    repo = KnowledgeRepository(db)
    doc = await repo.get_document(document_id)

    if doc is None:
        raise HTTPException(404, "文档不存在")

    if user.role != "admin" and doc.uploader_id != user.id:
        raise HTTPException(404, "文档不存在")

    # Try reading progress from Redis
    stage = None
    progress = 0.0
    try:
        from app.infra.redis import get_redis
        redis = get_redis()
        job_data = await redis.get(f"knowledge:job:{document_id}")
        if job_data:
            import json
            job = json.loads(job_data)
            stage = job.get("stage")
            progress = job.get("progress", 0.0)
    except Exception as exc:
        logger.debug("redis.progress_read_failed", document_id=document_id, error=str(exc))

    return ProgressOut(
        document_id=document_id,
        status=doc.status,
        stage=stage,
        progress=progress,
        error=doc.error,
    )


# ── Delete ───────────────────────────────────────────────────────────


@router.delete("/{document_id}", response_model=DeleteOut)
async def delete_document(
    document_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> DeleteOut:
    """Delete a document and its OSS file. Admin only."""
    repo = KnowledgeRepository(db)
    doc = await repo.get_document(document_id)

    if doc is None:
        raise HTTPException(404, "文档不存在")

    # Delete from OSS
    try:
        from app.infra.oss import get_oss_client
        oss = get_oss_client()
        oss.delete_object(Bucket=OSS_BUCKET, Key=doc.oss_key)
    except Exception as exc:
        logger.warning("oss.delete_failed", oss_key=doc.oss_key, bucket=OSS_BUCKET, error=str(exc))

    await repo.delete_document(document_id)
    return DeleteOut()


# ── Reprocess ────────────────────────────────────────────────────────


@router.post("/{document_id}/reprocess", response_model=ReprocessOut)
async def reprocess_document(
    document_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> ReprocessOut:
    """Trigger re-processing (re-vectorization) of a document. Admin only."""
    repo = KnowledgeRepository(db)
    doc = await repo.get_document(document_id)

    if doc is None:
        raise HTTPException(404, "文档不存在")

    # Reset status
    await repo.update_document_status(document_id, "pending")

    # Fire-and-forget with exception safety net (§6.2 / §6.4)
    import asyncio
    asyncio.create_task(_run_pipeline_background(document_id))

    return ReprocessOut(document_id=document_id, status="pending")
