"""Background worker for knowledge pipeline processing.

MVP: Runs as asyncio task triggered by API endpoints.
Phase 3: Will be upgraded to Celery for persistent task queues.

§6.2 fix: Retry transient failures (network timeout, API rate limit) with
exponential backoff via tenacity. Non-retryable errors (invalid format,
empty text) fail immediately.
"""

from __future__ import annotations

import json
import traceback

import structlog
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.infra.db import get_session_factory
from app.infra.redis import get_redis
from app.domain.knowledge.repository import KnowledgeRepository
from app.domain.knowledge.service import KnowledgeService

logger = structlog.get_logger(__name__)

OSS_BUCKET = "eira-documents"

# ── Retry configuration ────────────────────────────────────────────────────

MAX_RETRIES = 3  # 1 initial attempt + 2 retries

RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,  # network-level errors
)


def _is_retryable(exc: Exception) -> bool:
    """Decide whether a pipeline failure should be retried.

    Transient (retryable): network errors, timeouts, HTTP 429 / 5xx.
    Permanent (fatal): invalid file, parse errors, empty text.
    """
    if isinstance(exc, RETRYABLE_EXCEPTIONS):
        return True

    # Check for HTTP-level retryable status codes (embedding API, OSS, etc.)
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is not None and status in {429, 500, 502, 503, 504}:
        return True

    return False


async def _report_retry_attempt(document_id: int, attempt: int) -> None:
    """Write retry progress to Redis so the frontend can show status."""
    try:
        redis = get_redis()
        data = {
            "document_id": document_id,
            "stage": "retrying",
            "progress": 0.05 * attempt,
            "attempt": attempt,
            "max_attempts": MAX_RETRIES,
        }
        await redis.set(
            f"knowledge:job:{document_id}",
            json.dumps(data, ensure_ascii=False),
            ex=3600,
        )
    except Exception as exc:
        # Redis progress reporting is best-effort
        logger.debug("redis.progress_report_failed", document_id=document_id, error=str(exc))


# ── Pipeline runner ────────────────────────────────────────────────────────


async def run_knowledge_pipeline(document_id: int) -> None:
    """Run the full knowledge pipeline for a document asynchronously.

    This function:
    1. Downloads the document from OSS
    2. Parses the content
    3. Chunks the text
    4. Generates embeddings
    5. Stores everything in pgvector
    6. Reports progress to Redis
    7. Updates document status on completion/failure
    8. Retries on transient failures (§6.2)
    """
    logger.info("knowledge.worker.start", document_id=document_id)

    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = KnowledgeRepository(session)
        svc = KnowledgeService(repo)
        # Initialize with DB-aware embedding settings (§3 fix)
        await svc.init_embedding_provider()

        # Update status to processing
        await repo.update_document_status(document_id, "processing")
        await _report_progress(document_id, "parsing", 0.1)

        try:
            # ── Retry wrapper (§6.2) ───────────────────────────────────
            # Transient failures (network, timeout, HTTP 429/5xx) are retried
            # up to MAX_RETRIES with exponential backoff: 2s → 4s → 8s.
            # Non-retryable errors (ValueError, EmptyTextError) fail immediately.

            @retry(
                retry=retry_if_exception(_is_retryable),
                stop=stop_after_attempt(MAX_RETRIES),
                wait=wait_exponential(multiplier=2, min=2, max=30),
                reraise=True,
                after=lambda retry_state: logger.info(
                    "knowledge.worker.retry",
                    document_id=document_id,
                    attempt=retry_state.attempt_number,
                    wait=retry_state.idle_for,
                ) if retry_state.outcome and retry_state.outcome.failed else None,
            )
            async def _run_with_retry():
                await svc.process_document(document_id)

            await _run_with_retry()

            # ── Success ───────────────────────────────────────────────
            await _report_progress(document_id, "done", 1.0)
            await session.commit()
            logger.info("knowledge.worker.complete", document_id=document_id)

        except Exception as exc:
            # ── Failure (after all retries exhausted, or non-retryable) ──
            error_detail = f"{type(exc).__name__}: {exc}"
            trace = traceback.format_exc()
            logger.error(
                "knowledge.worker.error",
                document_id=document_id,
                error=error_detail,
                traceback=trace,
            )

            await repo.update_document_status(
                document_id, "failed", error=error_detail
            )
            await _report_progress(document_id, "failed", 0.0, error=error_detail)

            # Commit the failed status
            await session.commit()


# ── Progress reporting ─────────────────────────────────────────────────────


async def _report_progress(
    document_id: int,
    stage: str,
    progress: float,
    error: str | None = None,
) -> None:
    """Write pipeline progress to Redis for polling."""
    try:
        redis = get_redis()
        data = {
            "document_id": document_id,
            "stage": stage,
            "progress": progress,
        }
        if error:
            data["error"] = error
        await redis.set(
            f"knowledge:job:{document_id}",
            json.dumps(data, ensure_ascii=False),
            ex=3600,  # TTL 1 hour
        )
    except Exception as exc:
        # Redis progress reporting is best-effort
        logger.debug("redis.progress_write_failed", document_id=document_id, error=str(exc))
