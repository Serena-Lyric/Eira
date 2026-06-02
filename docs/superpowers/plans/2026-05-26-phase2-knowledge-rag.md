---
name: 2026-05-26-phase2-knowledge-rag
title: Phase 2 · 知识库 Pipeline + RAG + Web Search（后端）
date: 2026-05-26
status: draft
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
overview: docs/superpowers/plans/2026-05-26-overview.md
prev: docs/superpowers/plans/2026-05-26-phase1-text-chat.md
revision: 2026-06-02 — UI 冻结，移除来源标注前端任务，聚焦后端 Pipeline
---

# Phase 2 实施计划 · 知识库 Pipeline + RAG + Web Search

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现文档上传 → 解析 → 分块 → 向量化 → pgvector 检索 → Web Search 兜底的后端 Pipeline。前端 Chat.vue 的对话气泡已预留 `sources` 显示位置，后续数据对接时启用。

## 🔒 前端 UI 状态

- Chat.vue 中对话气泡已预留来源标注区域（`src-pills`），当前隐藏。
- 管理端 Knowledge.vue 已完成（NDataTable + NUpload + 模拟数据），仅需数据对接。
- 本 Phase **不做前端 UI 修改**，仅在后端实现知识库 REST API 和检索逻辑。

**Architecture:**
- 知识库管线：PDF/DOCX/TXT/MD → text → 滑动窗口 chunk → embedding（OpenAI 兼容 `text-embedding-3-small`）→ pgvector HNSW 索引。
- 检索：余弦相似度 top_k=5；置信度阈值 0.65。
- Web Search：Tavily/Bocha 抽象 Provider，按预算限频。
- Orchestrator 新节点：`retrieve_kb → web_search?(条件) → safety_in → llm_call`。
- 资源管理：所有原文存 OSS（`eira-documents`），DB 仅存元数据 + chunk 文本副本。

**Tech Stack:** `pypdf` + `python-docx` + `markdown-it-py`、`tiktoken`、`pgvector` Python 客户端、`httpx`（Web Search）、FastAPI BackgroundTasks（MVP 阶段）。

**前置条件：** Phase 1 全部 Validation Gate passed。

**本 Phase 不做：** 在线增量学习；多模态文档解析（OCR 留 Phase 7）；管理端知识库 UI（已完成）；前端来源标注 UI（已完成，数据对接在 Phase 4 统一处理）。

**重述全局约定：** TDD 强制；commit 前缀；密钥不入库；🔒 禁止修改 .vue 文件的 template/style；验证门数据归档。

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
T2.10 异步管线状态机（pending/processing/ready/failed）
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

> ⚠️ **要点**：`document` 与 `document_chunk` 拆开；embedding 维度 vector(1536) 对齐 `text-embedding-3-small`。

---

## Task 2.2: 文档解析器

**Files:**
- Create: `backend/app/domain/knowledge/parsers/`（pdf.py / docx.py / text.py / markdown.py / registry.py）
- Modify: `backend/pyproject.toml`（加 `pypdf>=4.2`、`python-docx>=1.1`、`markdown-it-py>=3.0`、`tiktoken>=0.7`）
- Create: `backend/tests/unit/test_parsers.py`
- Create: `backend/tests/fixtures/docs/`

> ⚠️ **要点**：PDF 扫描件无文本层 → 返回空列表 + status=failed, error="empty_text"。段落最小 20 字符过滤。DOCX 表格按行拼接。

---

## Task 2.3: Chunking（滑动窗口 + token 计数）

**Files:**
- Create: `backend/app/domain/knowledge/chunker.py`
- Create: `backend/tests/unit/test_chunker.py`

参数：`chunk_size=500 tokens`、`chunk_overlap=80 tokens`、按句末优先切分、最小 chunk 80 tokens。

---

## Task 2.4: Embedding Provider 抽象

**Files:**
- Create: `backend/app/capabilities/embedding/`（base.py / openai_compat.py / factory.py）
- Modify: `backend/app/core/config.py`（追加 EmbeddingSettings）
- Create: `backend/tests/unit/test_embedding.py`（VCR）

> ⚠️ **要点**：批量 API `batch_size=64`；超长文本截断到 8192 tokens。失败重试 3 次。

---

## Task 2.5: 向量入库 + 查询服务

**Files:**
- Create: `backend/app/domain/knowledge/service.py`
- Modify: `backend/app/domain/knowledge/repository.py`
- Create: `backend/tests/integration/test_knowledge_pipeline.py`

管线：parse → chunk → embed_batch → bulk insert → status='ready'。事务保证 replace_chunks 原子性。KNN 查询：`ORDER BY embedding <=> :qvec ASC`，应用层过滤 score ≥ min_score。

---

## Task 2.6: 文档 REST 接口

**Files:**
- Create: `backend/app/api/rest/documents.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/integration/test_documents_api.py`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/documents/upload` | multipart 上传，返回 document_id |
| GET | `/documents` | 列表（admin 全量，visitor 自己上传的） |
| GET | `/documents/{id}` | 详情含 chunk_count / status / error |
| DELETE | `/documents/{id}` | admin only；删 OSS + DB |
| POST | `/documents/{id}/reprocess` | "重新向量化"，admin only |

---

## Task 2.7: 检索置信度策略

**Files:**
- Create: `backend/app/orchestrator/nodes/retrieve_kb.py`
- Modify: `backend/app/orchestrator/state.py`（追加 `retrieval_meta` / `need_web_search` / `web_results`）
- Create: `backend/tests/unit/test_retrieve_kb.py`

top_k=5 检索 → 最高分 < 0.65 → 触发 need_web_search。

---

## Task 2.8: Web Search Provider + Tavily 适配器

**Files:**
- Create: `backend/app/capabilities/search/`（base.py / tavily.py / factory.py）
- Modify: `backend/app/core/config.py`（追加 SearchSettings + 日预算）
- Create: `backend/tests/unit/test_search.py`（VCR）

> ⚠️ **要点**：Redis 计数 key=`search:budget:YYYYMMDD`，超 daily_limit 返回空。必填日志字段 provider/query/latency_ms。

---

## Task 2.9: Orchestrator 接入 RAG 节点

**Files:**
- Modify: `backend/app/orchestrator/graph.py`
- Create: `backend/app/orchestrator/nodes/web_search.py`
- Modify: `backend/app/orchestrator/nodes/llm_call.py`（合并 KB + web 上下文）
- Create: `backend/tests/integration/test_orchestrator_rag.py`

新图：`load_context → safety_in → retrieve_kb → (web_search? → llm_call) → safety_out → persist → emit`。

---

## Task 2.10: 异步管线状态机

**Files:**
- Modify: `backend/app/api/rest/documents.py`（轮询接口）
- Create: `backend/app/workers/__init__.py`
- Create: `backend/app/workers/knowledge_worker.py`
- Create: `backend/tests/integration/test_pipeline_failure_recovery.py`

> ⚠️ **要点**：失败可恢复（status=failed → 重试）；replace_chunks 必须 DELETE + INSERT 同事务。MVP 用 BackgroundTasks，Phase 3 升级 Celery。

---

## 🚦 Validation Gates

### G-2.1 · 知识库管线吞吐与正确性
- 上传 30 页 PDF → status=ready 总耗时 ≤ 60s；chunk 数 ≥ 50 且 ≤ 200。

### G-2.2 · RAG 召回质量
- 标注 30 个问答对 → Recall@5 ≥ 80%；MRR ≥ 0.6。

### G-2.3 · 端到端 RAG 路径首响延迟
- KB 命中 P95 ≤ 2.5s；Web fallback P95 ≤ 4s。

### G-2.4 · 来源标注与回答可追溯
- 人工检视 20 条：一致率 ≥ 90%；web 链接可达率 100%。

---

## 完成状态

Phase 2 完成 ⇔ G-2.1 / 2.2 / 2.3 / 2.4 全部 passed。

## Revision 2026-06-02

- **移除 T2.10 前端来源标注任务**（原计划编号，现合并入 Task 2.9）：Chat.vue 已预留来源 pill UI，数据对接在 Orchestrator 接入 RAG 后通过 WS `sources` 帧自动生效。
- 管理端知识库 UI（Knowledge.vue）已完成，仅需数据对接（Phase 4 统一处理）。
- 任务编号重排：原 T2.11（异步管线）→ T2.10。
