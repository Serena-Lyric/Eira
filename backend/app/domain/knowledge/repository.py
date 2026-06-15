"""Repository for knowledge documents and chunks."""

from sqlalchemy import select, func, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from .models import Document, DocumentChunk


class KnowledgeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Document ────────────────────────────────────────────

    async def create_document(self, doc: Document) -> Document:
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def get_document(self, document_id: int) -> Document | None:
        return await self.session.get(Document, document_id)

    async def list_documents(
        self,
        uploader_id: int | None = None,
        status_filter: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        q = select(Document)
        count_q = select(func.count(Document.id))

        if uploader_id is not None:
            q = q.where(Document.uploader_id == uploader_id)
            count_q = count_q.where(Document.uploader_id == uploader_id)

        if status_filter:
            q = q.where(Document.status.in_(status_filter))
            count_q = count_q.where(Document.status.in_(status_filter))

        q = q.order_by(Document.created_at.desc()).offset(offset).limit(limit)

        rows = (await self.session.execute(q)).scalars().all()
        total = (await self.session.execute(count_q)).scalar_one()
        return list(rows), total

    async def update_document_status(
        self, document_id: int, status: str, error: str | None = None
    ) -> Document | None:
        doc = await self.get_document(document_id)
        if doc is None:
            return None
        doc.status = status
        if error is not None:
            doc.error = error
        await self.session.flush()
        return doc

    async def update_chunk_count(self, document_id: int, count: int) -> None:
        doc = await self.get_document(document_id)
        if doc:
            doc.chunk_count = count
            await self.session.flush()

    async def delete_document(self, document_id: int) -> None:
        doc = await self.get_document(document_id)
        if doc:
            await self.session.delete(doc)
            await self.session.flush()

    # ── Chunk ───────────────────────────────────────────────

    async def replace_chunks(
        self, document_id: int, chunks: list[DocumentChunk]
    ) -> None:
        """Atomic replace: DELETE all chunks for document, then INSERT new ones."""
        await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        for chunk in chunks:
            self.session.add(chunk)
        await self.session.flush()

    async def get_chunks(self, document_id: int) -> list[DocumentChunk]:
        q = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list((await self.session.execute(q)).scalars().all())

    async def search_similar(
        self, embedding: list[float], top_k: int = 5, min_score: float = 0.0
    ) -> list[tuple[DocumentChunk, float]]:
        """KNN search using cosine distance. Returns (chunk, similarity_score)."""
        # pgvector cosine distance: <=> operator. Convert to similarity: 1 - distance.
        stmt = text(
            """
            SELECT
                kc.id,
                kc.document_id,
                kc.chunk_index,
                kc.content,
                kc.metadata_json,
                kc.created_at,
                1 - (kc.embedding <=> :qvec) AS similarity
            FROM knowledge_chunks kc
            JOIN documents d ON d.id = kc.document_id
            WHERE kc.embedding IS NOT NULL
            ORDER BY kc.embedding <=> :qvec
            LIMIT :k
            """
        )

        # Vector needs to be formatted as a string for pgvector
        vec_str = f"[{','.join(str(v) for v in embedding)}]"

        result = await self.session.execute(
            stmt, {"qvec": vec_str, "k": top_k}
        )
        rows = result.fetchall()

        chunks: list[tuple[DocumentChunk, float]] = []
        for row in rows:
            similarity = row.similarity
            if similarity < min_score:
                continue
            chunk = DocumentChunk(
                id=row.id,
                document_id=row.document_id,
                chunk_index=row.chunk_index,
                content=row.content,
                metadata_json=row.metadata_json,
            )
            # set created_at separately since it's not in __init__ when passed this way
            chunk.created_at = row.created_at
            chunks.append((chunk, similarity))

        return chunks
