---
name: 2026-05-26-phase2-knowledge-rag
title: Phase 2 · 知识库 Pipeline + RAG + Web Search
date: 2026-05-26
status: draft
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
overview: docs/superpowers/plans/2026-05-26-overview.md
prev: docs/superpowers/plans/2026-05-26-phase1-text-chat.md
---

# Phase 2 实施计划 · 知识库 Pipeline + RAG + Web Search

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户上传文档 → 解析 → 分块 → 向量化（手动触发的"重新向量化"按钮） → 写入 pgvector；对话时检索 Top-K 注入 prompt；知识库未命中或低置信度 → 调用 Web Search Provider 兜底，前端显示来源标注（"知识库" / "互联网"）。

**Architecture:**
- 知识库管线：PDF/DOCX/TXT/MD → text → 滑动窗口 chunk → embedding（OpenAI 兼容 `text-embedding-3-small`）→ pgvector。
- 检索：HNSW 索引 + 余弦相似度；返回 top_k=5；置信度阈值 0.65。
- Web Search：Tavily/Bocha 抽象 Provider，按预算限频。
- Orchestrator 新节点：`retrieve_kb → web_search?(条件) → safety_in → llm_call`。
- 资源管理：所有原文存 OSS（`eira-documents`），DB 仅存元数据 + chunk 文本副本。

**Tech Stack:** `pypdf` + `python-docx` + `markdown-it-py`、`tiktoken`（chunk 估 token）、`pgvector` Python 客户端、`httpx`（Web Search）、Celery 或 RQ（异步管线，本 Phase 用 FastAPI BackgroundTasks 起步）。

**前置条件：** Phase 1 全部 Validation Gate passed。

**本 Phase 不做：** 在线增量学习；多模态文档解析（图片/视频内文字 OCR）；表格抽取；后台管理 UI（Phase 4）；任何 ASR/TTS。

**重述全局约定：** TDD 强制；commit 前缀；密钥不入库；验证门数据归档至 `docs/superpowers/validations/`。

---

## 任务依赖图

```
T2.1 文档存储与元数据 schema（OSS + DB）
  ↓
T2.2 文档解析器（PDF/DOCX/TXT/MD）
  ↓
T2.3 Chunking（滑动窗口 + token 计数）
  ↓
T2.4 Embedding Provider 抽象（OpenAI 兼容）
  ↓
T2.5 向量入库 + HNSW 索引 + 查询服务
  ↓
T2.6 文档 REST 接口（上传 / 列表 / 删除 / 重新向量化）
  ↓
T2.7 检索置信度策略（top_k + 置信阈值）
  ↓
T2.8 Web Search Provider 抽象 + Tavily 适配器
  ↓
T2.9 Orchestrator 接入 retrieve_kb / web_search 节点
  ↓
T2.10 来源标注（前端 source pill）
  ↓
T2.11 异步管线状态机（pending/processing/ready/failed）
  ↓
🚦 G-2.1 / G-2.2 / G-2.3 / G-2.4
```

---

## Task 2.1: 文档存储与元数据 schema

**Files:**
- Create: `backend/app/domain/knowledge/__init__.py`
- Create: `backend/app/domain/knowledge/models.py`
- Create: `backend/app/domain/knowledge/schemas.py`
- Create: `backend/app/domain/knowledge/repository.py`
- Create: `backend/app/infra/alembic/versions/0004_knowledge_tables.py`

> ⚠️ **要点**：`document` 与 `document_chunk` 拆开；前者存元数据 + OSS key，后者存 chunk 文本 + embedding。`embedding vector(1536)` 维度对齐 `text-embedding-3-small`；切换模型时必须做"全量重建"。

- [ ] **Step 1: 迁移**

```python
# 0004_knowledge_tables.py
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "document",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source", sa.String(64), nullable=False, server_default="upload"),
        sa.Column("oss_key", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("uploaded_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding_model", sa.String(64), nullable=True),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_check_constraint("ck_document_status", "document",
        "status IN ('pending','processing','ready','failed')")
    op.create_index("ix_document_status", "document", ["status"])
    op.execute("""
        CREATE TABLE document_chunk (
            id BIGSERIAL PRIMARY KEY,
            document_id BIGINT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
            seq INT NOT NULL,
            text TEXT NOT NULL,
            token_count INT NOT NULL,
            embedding vector(1536),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.create_index("ix_document_chunk_doc_seq", "document_chunk", ["document_id", "seq"])
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_chunk_embedding_hnsw
        ON document_chunk USING hnsw (embedding vector_cosine_ops);
    """)

def downgrade() -> None:
    op.execute("DROP TABLE document_chunk")
    op.drop_table("document")
```

跑迁移：`uv run alembic upgrade head`。

- [ ] **Step 2: 模型与仓储**

```python
# models.py
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, String, Integer, ForeignKey, Text
from app.domain.identity.models import Base

class Document(Base):
    __tablename__ = "document"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(64), default="upload")
    oss_key: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    uploaded_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_model: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)

class DocumentChunk(Base):
    __tablename__ = "document_chunk"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("document.id"))
    seq: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    embedding = mapped_column(Vector(1536), nullable=True)
```

加依赖 `pgvector>=0.3` 已在 Phase 0 引入。

- [ ] **Step 3: 提交**

```
git add backend/
git commit -m "feat(knowledge): document + chunk schema with pgvector hnsw"
```

---

## Task 2.2: 文档解析器

**Files:**
- Create: `backend/app/domain/knowledge/parsers/__init__.py`
- Create: `backend/app/domain/knowledge/parsers/pdf.py`
- Create: `backend/app/domain/knowledge/parsers/docx.py`
- Create: `backend/app/domain/knowledge/parsers/text.py`
- Create: `backend/app/domain/knowledge/parsers/markdown.py`
- Create: `backend/app/domain/knowledge/parsers/registry.py`
- Modify: `backend/pyproject.toml`（加 `pypdf>=4.2`、`python-docx>=1.1`、`markdown-it-py>=3.0`、`tiktoken>=0.7`）
- Create: `backend/tests/unit/test_parsers.py`
- Create: `backend/tests/fixtures/docs/sample.pdf` `sample.docx` `sample.md` `sample.txt`

> ⚠️ **要点**：PDF 中可能含目录页/版权页 → 解析后做"段落最小长度过滤"（< 20 字符的段落丢弃）；DOCX 表格按行拼接（用 `|` 分隔）；Markdown 保留 code fence 内文本但去除 fence；TXT 简单按 `\n\n` 分段。返回结构统一：`list[ParsedSegment(seq, text)]`。

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_parsers.py
from pathlib import Path
import pytest
from app.domain.knowledge.parsers.registry import parse_file

FIX = Path(__file__).parent.parent / "fixtures" / "docs"

@pytest.mark.parametrize("name,kind", [
    ("sample.pdf", "pdf"), ("sample.docx", "docx"),
    ("sample.md", "markdown"), ("sample.txt", "text"),
])
def test_parse_returns_non_empty_segments(name, kind):
    segs = parse_file(FIX / name)
    assert len(segs) > 0
    assert all(len(s.text.strip()) >= 20 for s in segs)
```

- [ ] **Step 2: 验证失败 + 实现**

`registry.py`:

```python
from pathlib import Path
from dataclasses import dataclass
from .pdf import parse_pdf
from .docx import parse_docx
from .text import parse_text
from .markdown import parse_markdown

@dataclass
class ParsedSegment:
    seq: int
    text: str

EXT_MAP = {
    ".pdf": parse_pdf, ".docx": parse_docx,
    ".md": parse_markdown, ".markdown": parse_markdown,
    ".txt": parse_text,
}

def parse_file(path: Path) -> list[ParsedSegment]:
    ext = path.suffix.lower()
    if ext not in EXT_MAP:
        raise ValueError(f"unsupported file type: {ext}")
    raw_segments = EXT_MAP[ext](path)
    out, seq = [], 0
    for t in raw_segments:
        t = (t or "").strip()
        if len(t) < 20:
            continue
        out.append(ParsedSegment(seq=seq, text=t))
        seq += 1
    return out
```

`pdf.py`、`docx.py`、`text.py`、`markdown.py` 见 spec 描述（按 4 种格式分别实现）。**关键**：返回 raw `list[str]` 段落，过滤逻辑统一在 registry 完成。

- [ ] **Step 3: 验证 + 提交**

```
uv run pytest tests/unit/test_parsers.py -v
git add backend/
git commit -m "feat(knowledge): pdf/docx/md/txt document parsers"
```

> ⚠️ **延伸**：PDF 中扫描件无文本层 → 返回空列表 + 不报错。document.status 走到 `failed` 时把 error="empty_text" 暴露给前端。OCR 在 Phase 7 引入（PaddleOCR）。

---

## Task 2.3: Chunking（滑动窗口 + token 计数）

**Files:**
- Create: `backend/app/domain/knowledge/chunker.py`
- Create: `backend/tests/unit/test_chunker.py`

> ⚠️ **参数（spec 锁定 + 后续可调）**：默认 `chunk_size=500 tokens`、`chunk_overlap=80 tokens`、按"句末优先"切分（中文逗号/句号/换行）；最小 chunk = 80 tokens（不够则与下一段合并）。

- [ ] **Step 1: 写测试**

```python
from app.domain.knowledge.chunker import chunk_segments
from app.domain.knowledge.parsers.registry import ParsedSegment

def test_chunk_respects_size_and_overlap():
    long_text = "颐和园是一座皇家园林。" * 200
    segs = [ParsedSegment(seq=i, text=long_text) for i in range(2)]
    chunks = chunk_segments(segs, chunk_size=500, chunk_overlap=80)
    assert all(c.token_count <= 600 for c in chunks)
    assert all(c.token_count >= 80 for c in chunks)
    assert [c.seq for c in chunks] == list(range(len(chunks)))
```

- [ ] **Step 2: 实现**

```python
# chunker.py
from dataclasses import dataclass
import tiktoken
from .parsers.registry import ParsedSegment

_enc = tiktoken.get_encoding("cl100k_base")
SENT_BREAKS = ["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";"]

@dataclass
class Chunk:
    seq: int
    text: str
    token_count: int

def _tokens(text: str) -> int:
    return len(_enc.encode(text))

def _split_sentences(text: str) -> list[str]:
    out, cur = [], ""
    i = 0
    while i < len(text):
        cur += text[i]
        for br in SENT_BREAKS:
            if text[i:i+len(br)] == br:
                out.append(cur); cur = ""
                i += len(br) - 1; break
        i += 1
    if cur:
        out.append(cur)
    return [s for s in out if s.strip()]

def chunk_segments(segments: list[ParsedSegment], *,
                   chunk_size: int = 500, chunk_overlap: int = 80) -> list[Chunk]:
    sents: list[str] = []
    for s in segments:
        sents.extend(_split_sentences(s.text))
    chunks: list[Chunk] = []
    cur, cur_tok = "", 0
    seq = 0
    i = 0
    while i < len(sents):
        sent = sents[i]
        st = _tokens(sent)
        if cur_tok + st <= chunk_size:
            cur += sent; cur_tok += st; i += 1
        else:
            if cur and cur_tok >= 80:
                chunks.append(Chunk(seq=seq, text=cur.strip(), token_count=cur_tok))
                seq += 1
                # 回溯 overlap
                tail, tail_tok = "", 0
                j = i - 1
                while j >= 0 and tail_tok + _tokens(sents[j]) <= chunk_overlap:
                    tail = sents[j] + tail
                    tail_tok += _tokens(sents[j])
                    j -= 1
                cur, cur_tok = tail, tail_tok
            else:
                # 超长单句，强行切
                cur += sent; cur_tok += st; i += 1
    if cur.strip():
        chunks.append(Chunk(seq=seq, text=cur.strip(), token_count=cur_tok))
    return chunks
```

- [ ] **Step 3: 验证 + 提交**

```
uv run pytest tests/unit/test_chunker.py -v
git add backend/
git commit -m "feat(knowledge): sliding-window chunker with overlap"
```

---

## Task 2.4: Embedding Provider 抽象

**Files:**
- Create: `backend/app/capabilities/embedding/__init__.py`
- Create: `backend/app/capabilities/embedding/base.py`
- Create: `backend/app/capabilities/embedding/openai_compat.py`
- Create: `backend/app/capabilities/embedding/factory.py`
- Modify: `backend/app/core/config.py`（追加 `EmbeddingSettings`）
- Create: `backend/tests/unit/test_embedding.py`（VCR）

> ⚠️ **要点**：批量 API 默认 `batch_size=64`；超长文本截断到模型上限（8192 tokens）。失败重试 3 次，与 LLM 同策略。返回 `list[list[float]]`（与输入顺序一一对应）。

- [ ] **Step 1: 实现**

```python
# embedding/base.py
from typing import Protocol

class EmbeddingProvider(Protocol):
    name: str
    dim: int
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...

# embedding/openai_compat.py
import os
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

class OpenAiEmbeddingProvider:
    name = "openai_compat"

    def __init__(self, base_url: str, api_key_env: str, model_id: str, dim: int):
        api_key = os.environ.get(api_key_env, "")
        if not api_key:
            raise RuntimeError(f"missing {api_key_env}")
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self._model = model_id
        self.dim = dim

    @retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(0.5, 4), reraise=True)
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 64):
            batch = texts[i:i+64]
            r = await self._client.embeddings.create(model=self._model, input=batch)
            out.extend([d.embedding for d in r.data])
        return out
```

- [ ] **Step 2: 测试 + VCR + 验证**

```python
import pytest
from app.capabilities.embedding.factory import build_embedding

@pytest.mark.vcr
@pytest.mark.asyncio
async def test_embed_returns_correct_dim():
    p = build_embedding("openai-emb-3-small")
    vecs = await p.embed_batch(["hello", "你好"])
    assert len(vecs) == 2 and len(vecs[0]) == p.dim == 1536
```

- [ ] **Step 3: 提交**

```
git add backend/
git commit -m "feat(embedding): provider abstraction with openai-compat batch"
```

---

## Task 2.5: 向量入库 + 查询服务

**Files:**
- Create: `backend/app/domain/knowledge/service.py`
- Modify: `backend/app/domain/knowledge/repository.py`（追加 `replace_chunks` / `knn_search` / `mark_*`）
- Create: `backend/tests/integration/test_knowledge_pipeline.py`

> ⚠️ **要点**：单文档管线 = parse → chunk → embed_batch → bulk insert → status='ready'。失败任意一步：status='failed'，error 写原因。**重新向量化** = 删除 chunk → 重跑（保留原文 oss_key）。**事务**：`replace_chunks` 必须 DELETE + bulk INSERT 在同一事务。

- [ ] **Step 1: service 实现**

```python
# knowledge/service.py
class KnowledgeService:
    def __init__(self, repo, embedder, oss):
        self.repo = repo
        self.embedder = embedder
        self.oss = oss

    async def process(self, document_id: int):
        doc = await self.repo.get(document_id)
        await self.repo.set_status(document_id, "processing")
        try:
            local = await self._download_to_temp(doc.oss_key)
            segs = parse_file(local)
            if not segs:
                raise ValueError("empty_text")
            chunks = chunk_segments(segs)
            vecs = await self.embedder.embed_batch([c.text for c in chunks])
            await self.repo.replace_chunks(document_id, list(zip(chunks, vecs)))
            await self.repo.mark_ready(document_id, model=self.embedder.name,
                                       chunk_count=len(chunks))
        except Exception as e:
            await self.repo.mark_failed(document_id, str(e)[:500])
            raise

    async def reprocess(self, document_id: int):
        await self.repo.delete_chunks(document_id)
        await self.process(document_id)

    async def search(self, query: str, top_k: int = 5,
                     min_score: float = 0.65) -> list[dict]:
        [qvec] = await self.embedder.embed_batch([query])
        return await self.repo.knn_search(qvec, top_k=top_k, min_score=min_score)
```

`repository.knn_search` SQL：

```sql
SELECT c.id, c.document_id, c.text,
       1 - (c.embedding <=> :qvec) AS score,
       d.title
  FROM document_chunk c
  JOIN document d ON c.document_id = d.id
 WHERE d.status = 'ready'
 ORDER BY c.embedding <=> :qvec ASC
 LIMIT :k
```

应用层保留 `score >= min_score` 的结果。

- [ ] **Step 2: 集成测试**

```python
@pytest.mark.asyncio
async def test_full_pipeline_with_sample_doc(svc, sample_txt):
    doc_id = await svc.create_document_from_local(sample_txt, title="颐和园.txt")
    await svc.process(doc_id)
    hits = await svc.search("颐和园门票多少", top_k=3)
    assert hits and hits[0]["score"] >= 0.7
```

- [ ] **Step 3: 提交**

```
git add backend/
git commit -m "feat(knowledge): processing pipeline + knn search"
```

---

## Task 2.6: 文档 REST 接口

**Files:**
- Create: `backend/app/api/rest/documents.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/integration/test_documents_api.py`

接口：

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/documents/upload` | multipart 上传，返回 document_id + status=pending |
| GET | `/documents` | 列表（admin 才能看全部，visitor 看自己上传） |
| GET | `/documents/{id}` | 详情含 chunk_count / status / error |
| DELETE | `/documents/{id}` | admin 才能删；同时删 OSS 对象 + chunks |
| POST | `/documents/{id}/reprocess` | 触发"重新向量化"，admin only |

- [ ] **Step 1/2/3: 实现 + 测试 + 提交**

```python
@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload(file: UploadFile = File(...),
                 svc: KnowledgeService = Depends(_svc),
                 u: User = Depends(get_current_user),
                 bg: BackgroundTasks = None):
    if file.size and file.size > 50 * 1024 * 1024:
        raise HTTPException(413, "file_too_large")
    oss_key = f"docs/{uuid4().hex}/{file.filename}"
    get_oss_client().upload_fileobj(file.file, "eira-documents", oss_key)
    doc_id = await svc.create_document(
        title=file.filename, oss_key=oss_key,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=file.size or 0, uploaded_by=u.id)
    bg.add_task(svc.process, doc_id)
    return await svc.get(doc_id)

@router.post("/{id}/reprocess", response_model=DocumentOut)
async def reprocess(id: int, bg: BackgroundTasks,
                    svc: KnowledgeService = Depends(_svc),
                    _: User = Depends(require_admin)):
    bg.add_task(svc.reprocess, id)
    return await svc.get(id)
```

提交：`feat(knowledge): document upload/list/reprocess endpoints`。

> ⚠️ **延伸**：`BackgroundTasks` 在多副本部署时不持久化；Phase 3 改 Celery + Redis broker。`document.status` 已最终一致，重跑安全。

---

## Task 2.7: 检索置信度策略

**Files:**
- Create: `backend/app/orchestrator/nodes/retrieve_kb.py`
- Modify: `backend/app/orchestrator/state.py`（追加 `retrieval_meta` / `need_web_search` / `web_results`）
- Create: `backend/tests/unit/test_retrieve_kb.py`

```python
async def retrieve_kb(state: ChatState, *, svc: KnowledgeService) -> dict:
    hits = await svc.search(state.user_text, top_k=5)
    state.retrieved_chunks = [h["text"] for h in hits]
    top = max((h["score"] for h in hits), default=0.0)
    state.retrieval_meta = {
        "top_score": top,
        "sources": [{"doc_id": h["document_id"], "title": h["title"]} for h in hits],
        "kind": "knowledge_base",
    }
    state.need_web_search = top < 0.65
    return {"state": state}
```

提交：`feat(orchestrator): kb retrieval node with confidence threshold`。

---

## Task 2.8: Web Search Provider + Tavily 适配器

**Files:**
- Create: `backend/app/capabilities/search/__init__.py`
- Create: `backend/app/capabilities/search/base.py`
- Create: `backend/app/capabilities/search/tavily.py`
- Create: `backend/app/capabilities/search/factory.py`
- Modify: `backend/app/core/config.py`（追加 SearchSettings + 日预算）
- Create: `backend/tests/unit/test_search.py`（VCR）

> ⚠️ **要点**：
> - 接口：`async def search(query: str, top_k: int = 3) -> list[SearchHit{title, url, snippet, published_at?}]`。
> - 限频：Redis 计数 key=`search:budget:YYYYMMDD`，超 `daily_limit`（默认 200）后返回空 + state.error="search_quota_exhausted"（不抛异常，让流程继续）。
> - 必填日志字段 `provider/query/cost_estimate/latency_ms`；URL 不记录原始 user_text 之外内容。

实现按 LLM Provider 同模板（base→adapter→factory）。提交：`feat(search): web search provider abstraction with tavily adapter`。

---

## Task 2.9: Orchestrator 接入 RAG 节点

**Files:**
- Modify: `backend/app/orchestrator/graph.py`
- Create: `backend/app/orchestrator/nodes/web_search.py`
- Modify: `backend/app/orchestrator/nodes/llm_call.py`（合并 KB + web 上下文）
- Create: `backend/tests/integration/test_orchestrator_rag.py`

新图：

```
load_context → safety_in → retrieve_kb
                              │
                              ├─ need_web_search=True → web_search → llm_call
                              │
                              └─ need_web_search=False ─────────→ llm_call
                                                                   ↓
                                              safety_out → persist → emit
```

`llm_call._build_messages` 修改：

```python
ctx_parts = []
for c in state.retrieved_chunks:
    ctx_parts.append(f"<context source='knowledge_base'>{c}</context>")
for h in (state.web_results or []):
    ctx_parts.append(
        f"<context source='web' title='{h['title']}' url='{h['url']}'>{h['snippet']}</context>"
    )
if ctx_parts:
    sys += "\n\n参考资料（请优先使用，不能臆测）：\n" + "\n".join(ctx_parts)
sys += "\n\n回答末尾用一行注明来源类型，例如：来源：知识库 / 互联网 / 通用知识。"
```

集成测试覆盖：
- (a) KB 命中 → 不调用 web_search
- (b) KB 未命中 → 调用 web_search
- (c) 配额耗尽 → 仍出回复（标 source=通用知识）

提交：`feat(orchestrator): rag pipeline with web search fallback`。

---

## Task 2.10: 来源标注（前端 source pill）

**Files:**
- Modify: `apps/web-user/src/composables/useChatSession.ts`（接收 `sources` 帧）
- Modify: `apps/web-user/src/pages/Chat.vue`（在助手气泡下方显示来源 pill）
- Modify: `backend/app/api/ws/chat.py`（在 done 帧之前发送 sources 帧）

WS Server 帧扩展：

```json
{"type":"sources","items":[
  {"kind":"knowledge_base","title":"颐和园介绍.pdf"},
  {"kind":"web","title":"百度百科 - 颐和园","url":"https://..."}
]}
```

Chat.vue：

```vue
<div v-if="m.sources?.length" class="src-pills">
  <a v-for="s in m.sources" :key="s.title"
     :href="s.url" target="_blank" rel="noopener noreferrer"
     class="pill" :class="s.kind">
    {{ s.kind === "web" ? "🌐 互联网" : "📚 知识库" }} · {{ s.title }}
  </a>
</div>
```

提交：`feat(frontend): source pills for kb/web answers`。

> ⚠️ **要点**：来源链接外部跳转必须加 `noopener noreferrer`；如安全策略禁止离站，可走中间跳转页 `/r?u=base64`。

---

## Task 2.11: 异步管线状态机

**Files:**
- Modify: `backend/app/api/rest/documents.py`（轮询接口；可选 SSE 进度）
- Create: `backend/app/workers/__init__.py`
- Create: `backend/app/workers/knowledge_worker.py`（Phase 3 时切 Celery 留 hook）
- Create: `backend/tests/integration/test_pipeline_failure_recovery.py`

> ⚠️ **要点**：失败可恢复必须测：(a) embedding 5xx → status=failed，前端可点"重试"；(b) PG 写一半挂了 → `replace_chunks` 必须 DELETE + INSERT 同事务。

提交：`feat(knowledge): processing state machine with retry semantics`。

---

## 🚦 Validation Gate G-2.1 · 知识库管线吞吐与正确性

| 项 | 内容 |
|---|---|
| 指标 | 上传 30 页示范资料包（约 10MB PDF）→ status=ready 总耗时；chunk 数；embedding 调用数 |
| 阈值 | 总耗时 ≤ 60s；chunk 数 ≥ 50 且 ≤ 200；每个 chunk token ∈ [80, 700] |
| 测试方法 | `scripts/bench_kb_ingest.py` 上传后轮询 `/documents/{id}` 直到 ready；记录 wall-clock；查 DB 统计 chunk 分布 |
| 数据源 | 脚本输出 + DB 查询；归档 `docs/superpowers/validations/G-2.1.md` |
| 通过分支 | 进入 G-2.2 |
| 不通过分支 | 耗时超：先看 embedding 是否在用 batch；> 120s：考虑加 batch_size 或并发管线（多文档时拆任务）；chunk 分布异常：调 `chunk_size/overlap` 参数（在 spec 修订段记入选定值） |

---

## 🚦 Validation Gate G-2.2 · RAG 召回质量

| 项 | 内容 |
|---|---|
| 指标 | 在示范资料包上人工标注 30 个问答对（Q + 期望命中的 chunk_id），统计 Recall@5、MRR、首位命中率 |
| 阈值 | Recall@5 ≥ 80%；MRR ≥ 0.6；首位命中 ≥ 50% |
| 测试方法 | `scripts/eval_rag_recall.py` 跑标注集，对每个问题检索 top-5，比对期望 chunk_id；输出 csv |
| 数据源 | 标注集 `docs/superpowers/validations/datasets/rag-eval-30.json`（一并 commit）+ 评测脚本输出 `docs/superpowers/validations/G-2.2.md` |
| 通过分支 | 进入 G-2.3 |
| 不通过分支 | Recall@5 ∈ [60%, 80%)：(a) 增大 chunk_overlap 至 120；(b) 改用 `text-embedding-3-large`（dim 3072，需迁移）；< 60%：回 T2.3 重审 chunk 策略，考虑分层（句级 + 段落级）双索引；如仍不达标，升级 spec："是否引入 BM25 + 向量混排" |

---

## 🚦 Validation Gate G-2.3 · 端到端 RAG 路径首响延迟

| 项 | 内容 |
|---|---|
| 指标 | 命中 KB 路径：从用户提交到首 token 时间；不命中 → web_search → llm 路径同测 |
| 阈值 | KB 命中：P95 ≤ 2.5s；Web fallback：P95 ≤ 4s |
| 测试方法 | `scripts/bench_rag_e2e.py` 30 条 mix 标注问题（20 KB 命中 + 10 KB 不命中），各跑 5 轮 |
| 数据源 | 脚本输出；归档 `docs/superpowers/validations/G-2.3.md` |
| 通过分支 | 进入 G-2.4 |
| 不通过分支 | KB 命中超：检查 `embed query` 是否每次都新算（应启用 LRU cache，TTL 5 min）；HNSW 命中 > 100ms：调 `ef_search`；Web 路径超：把 web_search 改并行（两路 provider 任一返回即用） |

---

## 🚦 Validation Gate G-2.4 · 来源标注与回答可追溯

| 项 | 内容 |
|---|---|
| 指标 | 在 G-2.2 评测集上抽 20 条人工检视：(a) 回答末尾的"来源"标签与实际使用的上下文一致；(b) 来源 pill 与点击链接可达 |
| 阈值 | 一致率 ≥ 90%；链接可达率 100%（web 类） |
| 测试方法 | 人工检视并记录 |
| 数据源 | 检视记录归档 `docs/superpowers/validations/G-2.4.md` |
| 通过分支 | 合入，进入 Phase 3 |
| 不通过分支 | 一致率低：调 prompt 末尾"严格按 context 标注"；链接不达：检查 search provider 返回的 url 是否做了正确 URL escape |

---

## 完成状态

Phase 2 完成 ⇔ G-2.1 / 2.2 / 2.3 / 2.4 全部 passed。
