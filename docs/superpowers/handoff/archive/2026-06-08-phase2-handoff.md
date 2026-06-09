# Phase 2 移交文档 · 知识库 Pipeline + RAG + Web Search

**日期**: 2026-06-08  
**分支**: `chore/live2d-rewrite-and-handoff`  
**范围**: 仅后端 — 文档上传→解析→分块→向量化→pgvector 检索→Web Search 兜底  
**状态**: ✅ 全部 10 个任务完成，98 个单元测试通过，0 退化

---

## 一、完成概览

| 任务 | 内容 | 状态 |
|------|------|------|
| T2.1 | 文档存储与元数据 Schema（Document + DocumentChunk ORM、迁移） | ✅ |
| T2.2 | 文档解析器（PDF/DOCX/TXT/MD + 注册表） | ✅ |
| T2.3 | Chunking 滑动窗口分块器（500/80 token） | ✅ |
| T2.4 | Embedding Provider 抽象（OpenAI 兼容，text-embedding-3-small） | ✅ |
| T2.5 | 向量入库 + KNN 查询服务（parse→chunk→embed→insert 管线） | ✅ |
| T2.6 | 文档 REST 接口（upload/list/detail/delete/reprocess + progress 轮询） | ✅ |
| T2.7 | 检索置信度策略（top_k=5, threshold=0.65, 触发 need_web_search） | ✅ |
| T2.8 | Web Search Provider + Tavily 适配器（Redis 日预算限频） | ✅ |
| T2.9 | Orchestrator 接入 RAG 节点（新图结构 + 条件路由） | ✅ |
| T2.10 | 异步管线状态机（BackgroundTasks + Redis 进度 + 失败恢复） | ✅ |

---

## 二、文件清单

### 新建文件（30 个）

```
backend/app/domain/knowledge/
  __init__.py
  models.py              # Document + DocumentChunk ORM
  schemas.py             # Pydantic 出入参
  repository.py          # CRUD + KNN search_similar
  service.py             # 管线编排 + search/reprocess
  chunker.py             # 滑动窗口分块器
  parsers/
    __init__.py          # 注册表 + BaseParser/EmptyTextError
    pdf.py               # pypdf
    docx.py              # python-docx
    text.py              # 纯文本（多编码回退）
    markdown.py          # markdown-it-py + regex 回退

backend/app/capabilities/embedding/
  __init__.py            # BaseEmbeddingProvider (ABC)
  openai_compat.py       # OpenAICompatEmbeddingProvider + Mock
  factory.py

backend/app/capabilities/search/
  __init__.py            # BaseSearchProvider (ABC) + SearchResult
  tavily.py              # TavilySearchProvider + Mock（Redis 日预算）
  factory.py

backend/app/api/rest/
  documents.py           # /documents 路由组（upload/list/detail/delete/reprocess/progress）

backend/app/orchestrator/nodes/
  retrieve_kb.py         # KB 检索节点
  web_search.py          # Web Search 回退节点

backend/app/workers/
  __init__.py
  knowledge_worker.py    # 异步管线 + Redis 进度上报

backend/app/infra/alembic/versions/
  0005_knowledge_tables.py  # documents + knowledge_chunks 表 + HNSW 索引

backend/tests/
  unit/test_knowledge_models.py
  unit/test_parsers.py
  unit/test_chunker.py
  unit/test_embedding.py
  unit/test_knowledge_service.py
  unit/test_retrieve_kb.py
  unit/test_search.py
  integration/test_documents_api.py
  integration/test_orchestrator_rag.py
  integration/test_pipeline_failure_recovery.py
  fixtures/docs/sample.txt
```

### 修改文件（8 个）

| 文件 | 变更 |
|------|------|
| `backend/app/core/config.py` | 新增 `EmbeddingSettings` + `SearchSettings` |
| `backend/pyproject.toml` | 新增依赖: `pypdf`, `python-docx`, `markdown-it-py`, `tiktoken`, `httpx` |
| `backend/app/main.py` | 注册 `documents.router` |
| `backend/app/orchestrator/graph.py` | 新图: `load_context → safety_in → retrieve_kb → web_search(条件) → llm_call → safety_out → persist → emit` |
| `backend/app/orchestrator/state.py` | 新增 4 字段: `retrieval_meta`, `need_web_search`, `web_results`, `knowledge_sources` |
| `backend/app/orchestrator/nodes/load_context.py` | 从 Phase 1 stub 升级为真实 DB 历史加载 |
| `backend/app/orchestrator/nodes/llm_call.py` | 注入 `<context>...</context>` 包裹的 RAG chunks |
| `backend/app/api/ws/messages.py` | `DoneOut` 新增可选 `sources: list[dict]` |
| `backend/app/api/ws/chat.py` | DoneOut 透传 `knowledge_sources` |

---

## 三、关键架构决策

### 3.1 数据模型

```
documents (id, filename, oss_key, mime_type, file_size, status, chunk_count, error, uploader_id, created_at, updated_at)
knowledge_chunks (id, document_id FK CASCADE, chunk_index, content, embedding Vector(1536), metadata_json, created_at)
  INDEX hnsw (embedding vector_cosine_ops)
```

- status 约束: `pending | processing | ready | failed`
- embedding 维度 1536，对齐 `text-embedding-3-small`
- HNSW 索引提供快速余弦相似度搜索

### 3.2 管线流程

```
upload → OSS (eira-documents/<id>/<filename>)
       → INSERT documents (status=pending)
       → BackgroundTask: run_knowledge_pipeline(doc_id)
            ├── status=processing
            ├── OSS download
            ├── Parser (MIME type → 注册表)
            ├── Chunker (500 tokens, 80 overlap, 句末优先)
            ├── Embedding (batch_size=64, tenacity retry 3次)
            ├── replace_chunks (DELETE + INSERT 同一事务)
            └── status=ready | failed
```

### 3.3 Orchestrator 新图

```
入口 → load_context → safety_in
                          ├── blocked → emit
                          └── ok → retrieve_kb
                                      ├── top_score >= 0.65 → llm_call
                                      └── top_score < 0.65 → web_search → llm_call
                                                                              ├── error → emit
                                                                              └── ok → safety_out → persist → emit
```

### 3.4 Provider 抽象模式

全部 3 个 capability（LLM / Embedding / Search）统一采用 `ABC → 实现 → Factory` 三层：

```python
# Embedding
BaseEmbeddingProvider.embed(texts) → list[list[float]]
  ├── OpenAICompatEmbeddingProvider (批量64, tiktoken截断8192)
  └── MockEmbeddingProvider (零向量)

# Search
BaseSearchProvider.search(query, top_k) → list[SearchResult]
  ├── TavilySearchProvider (httpx + Redis日预算)
  └── MockSearchProvider (空结果)
```

无 API key 时自动 fallback 到 Mock，保障 dev 环境可用。

---

## 四、API 接口总览

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/documents/upload` | 登录用户 | multipart 上传，自动触发后台处理 |
| GET | `/documents` | admin全量/visitor自己 | 分页列表，`?status=pending,ready` |
| GET | `/documents/{id}` | 登录用户(own或admin) | 详情含 chunk 列表 |
| GET | `/documents/{id}/progress` | 登录用户(own或admin) | 处理进度(Redis) |
| DELETE | `/documents/{id}` | admin only | 删 OSS + DB cascade |
| POST | `/documents/{id}/reprocess` | admin only | 重置状态 + 重跑管线 |

---

## 五、测试覆盖

| 层级 | 文件 | 用例数 | 覆盖范围 |
|------|------|--------|---------|
| 单元 | test_knowledge_models | 8 | ORM 模型 + Schema 校验 |
| 单元 | test_parsers | 10 | Text/Markdown/PDF 解析 + 注册表 + 边界 |
| 单元 | test_chunker | 8 | 滑动窗口 / 最小chunk / 索引连续 / token准确 |
| 单元 | test_embedding | 8 | truncate / MockProvider / Factory / 空列表 |
| 单元 | test_knowledge_service | 5 | search / reprocess / 阈值过滤 |
| 单元 | test_retrieve_kb | 7 | 直通 / 高置信 / 低置信 / 错误回退 / 边界 |
| 单元 | test_search | 6 | MockProvider / Factory / SearchResult |
| 集成 | test_documents_api | 7 | 上传/列表/详情/删除权限 |
| 集成 | test_orchestrator_rag | 5 | 完整图 / sources保留 / safety短路 |
| 集成 | test_pipeline_failure_recovery | 3 | OSS失败 / 空文本 / reprocess清理 |
| **合计** | | **67 新增 + 31 原有 = 98** | |

---

## 六、待办与后续衔接

### 需要真实环境验证

- [ ] **pgvector 环境**: 运行 `alembic upgrade head` 创建 knowledge 表 + HNSW 索引
- [ ] **OSS 配置**: 确保 `eira-documents` bucket 存在且有读写权限
- [ ] **Embedding API key**: 设置 `EIRA_EMBEDDING__API_KEY` 环境变量
- [ ] **Tavily API key**: 设置 `EIRA_SEARCH__API_KEY` 环境变量
- [ ] **Redis**: 确保可用（Web Search 日预算依赖）

### 数据对接（后续 Phase）

- [ ] **前端 React 来源标注**: Chat.vue 的 `src-pills` 区域已预留，当 WS `done` 消息携带 `sources` 时显示
- [ ] **管理端 Knowledge.vue**: NDataTable 已就绪，对接 `/documents` API
- [ ] **检索预览**: 管理端输入 query → 调 `KnowledgeService.search()` 看 chunk 列表

### Validation Gates 待执行

- [ ] **G-2.1**: 上传 30 页 PDF → status=ready ≤ 60s, chunk 数 50-200
- [ ] **G-2.2**: 30 个 QA 对 → Recall@5 ≥ 80%, MRR ≥ 0.6
- [ ] **G-2.3**: KB 命中 P95 ≤ 2.5s, Web fallback P95 ≤ 4s
- [ ] **G-2.4**: 20 条人工检视 → 一致率 ≥ 90%, web 链接可达率 100%

### 已知局限

1. **PDF 扫描件**: 无 OCR 支持（计划 Phase 7），当前返回 `status=failed, error="empty_text"`
2. **Celery**: MVP 使用 FastAPI BackgroundTasks，高负载时需升级（Phase 3+）
3. **Mock Embedding**: 无 API key 时返回零向量，搜索结果不可用
4. **Tavily 限频**: 日预算 100 次，超限返回空 — 前端应提示用户
5. **无在线增量学习**: 新文档需手动上传+向量化

---

## 七、快速启动

```bash
# 1. 安装依赖
cd backend && uv pip install -e ".[dev]"

# 2. 数据库迁移
alembic upgrade head

# 3. 设置环境变量（示例）
export EIRA_EMBEDDING__API_KEY=sk-xxx
export EIRA_EMBEDDING__PROVIDER=openai
export EIRA_SEARCH__API_KEY=tvly-xxx
export EIRA_SEARCH__PROVIDER=tavily

# 4. 运行测试
python -m pytest --ignore=tests/integration -v

# 5. 启动服务
uvicorn app.main:app --reload
```

---

**签出**: 本 Phase 由 Claude Opus 4.8 执行，遵循 TDD、密钥不入库、commit 前缀约定。  
**下一步**: Phase 3（语音与多模态）或 Phase 4（管理后台 + 角色卡）。
