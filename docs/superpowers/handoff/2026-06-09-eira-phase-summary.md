# Eira 项目阶段性总结 · Phase 0–4

> **日期**: 2026-06-09  
> **分支**: `chore/live2d-rewrite-and-handoff`  
> **本文档**: 唯一入口，替代此前 15 个散列 handoff。历史文档归档于 `archive/`。

---

## 目录

1. [总览](#1-总览)
2. [各 Phase 完成状态](#2-各-phase-完成状态)
3. [架构决策汇总](#3-架构决策汇总)
4. [API 端点全表](#4-api-端点全表)
5. [数据库迁移链](#5-数据库迁移链)
6. [测试覆盖](#6-测试覆盖)
7. [已知遗留问题](#7-已知遗留问题)
8. [快速启动指南](#8-快速启动指南)
9. [归档索引](#9-归档索引)

---

## 1. 总览

**Eira** 是景区 AI 数字人导览系统，五层架构：Nginx 接入层 → Vue 3 前端层 → FastAPI 应用层 → PostgreSQL/pgvector/Redis/OSS 数据层 → 外部 AI 服务层。

| 维度 | 最终方案 |
|------|---------|
| 后端 | Python 3.11+ / FastAPI 单体模块化 |
| 前端 | Vue 3 + Vite + TypeScript，双 SPA (web-user + web-admin)，pnpm monorepo |
| 数据库 | PostgreSQL 16 + pgvector 0.7+ + Redis 7 + MinIO (OSS) |
| LLM | DeepSeek（Provider 抽象层，支持 OpenAI/Tongyi/Volc 切换） |
| AI 编排 | LangGraph 状态图（8 节点 + 条件路由） |
| Live2D | Cubism SDK for Web 5 Framework（自管 WebGL，弃用 pixi-live2d-display） |
| 实时通信 | WebSocket 全双工（`/ws/chat` + `/ws/voice`） |
| 鉴权 | JWT 双 token (access 15min + refresh 7d)，角色 visitor/admin |
| 测试 | pytest + httpx + structlog；253 测试全绿 |

### 文件结构

```
Eira/
├─ apps/
│  ├─ web-user/          # 用户端 SPA（10 Vue 文件，Chat.vue 自包含）
│  └─ web-admin/         # 管理后台 SPA（Dashboard.vue 内嵌全部功能）
├─ packages/ui-shared/   # Stub 共享包
├─ backend/
│  └─ app/
│     ├─ api/rest/       # 16 个 REST 路由模块
│     ├─ api/ws/         # /ws/chat + /ws/voice
│     ├─ capabilities/   # LLM / ASR / TTS / Embedding / Search Provider
│     ├─ core/           # 配置 / 安全 / 限流 / 文件校验 / 审计中间件
│     ├─ domain/         # identity / conversation / knowledge / persona / system
│     ├─ infra/          # DB / Redis / OSS / Alembic (0011 head)
│     ├─ orchestrator/   # LangGraph 图 + 8 节点 + 句切引擎
│     └─ workers/        # 知识库异步管线（tenacity 重试）
├─ deploy/               # docker-compose + Nginx
└─ docs/superpowers/
   ├─ specs/             # 架构设计 spec
   ├─ plans/             # 实施计划（当前版 + archive/ 原始版）
   ├─ handoff/           # 本文档 + archive/ 历史 handoff
   └─ validations/       # G-1.x 验证门数据
```

---

## 2. 各 Phase 完成状态

| Phase | 内容 | 后端 | 前端 | 测试 | 验证门 |
|-------|------|:--:|:--:|:--:|:--:|
| **0** | 基础设施：仓库/Docker/CI/PG/Redis/OSS/鉴权骨架 | ✅ | ✅ | ✅ | G-0.x 通过 |
| **1** | 文本对话：LLM Provider + LangGraph 编排 + WS 协议 + Live2D | ✅ | ✅ | 28 tests | G-1.x 通过 |
| **2** | 知识库 RAG：文档解析→分块→向量化→pgvector→Web Search | ✅ | ✅ (UI) | 98 tests | G-2.1 通过 |
| **3** | 语音多模态：ASR/TTS Provider + /ws/voice + 句切引擎 + 音频泵 | ✅ | ✅ | 144 tests | 待执行 |
| **4** | 管理后台：用户管理/角色卡 CRUD/系统设置/审计/权限 | ✅ | ✅ | 253 tests | 待执行 |
| **5** | 运营看板：埋点 + 聚合 + 看板 API | ❌ | ✅ (UI) | — | — |
| **6** | 长期记忆 + 情感识别 | ❌ | ❌ | — | — |
| **7** | 扩展：主动问候/图像识别/多租户/AR | ❌ | ❌ | — | — |

### 关键偏差（与原始 spec 对比，已确认）

| 维度 | 原计划 | 实际 |
|------|--------|------|
| ui-shared 组件 | 4 个玻璃拟态组件 + CSS tokens | Stub，各页面自行内联 |
| Admin 布局 | 三栏侧边栏 + 菜单 | NConfigProvider 空壳 + 6 按钮导航 |
| Admin 图表 | ECharts | 手写 SVG |
| Chat.vue | 子组件组合 | 426 行自包含内联 |
| Live2D 渲染 | pixi-live2d-display + Cubism 4 | 官方 Cubism SDK 5 Framework + 自管 WebGL |
| Dashboard 视图 | 多路由页面 | Dashboard.vue 单体内嵌全部功能 |

---

## 3. 架构决策汇总

### 3.1 Provider 抽象模式

全部 5 个外部能力统一采用 `ABC → 实现 → Factory` 三层，无 API key 时自动 fallback Mock：

| Provider | 抽象基类 | 实现 | 工厂 |
|----------|---------|------|------|
| LLM | `BaseLLMProvider` | OpenAICompat (DeepSeek/OpenAI/Tongyi/Volc) / Mock | `create_llm_provider()` |
| ASR | `BaseASRProvider` | Mock / (预留 aliyun_nls, xunfei) | `create_asr_provider()` |
| TTS | `BaseTTSProvider` | Mock / (预留 aliyun_nls, azure) | `create_tts_provider()` |
| Embedding | `BaseEmbeddingProvider` | OpenAICompat (text-embedding-3-small) / Mock | `create_embedding_provider()` |
| Search | `BaseSearchProvider` | Tavily / Mock（Redis 日预算限频） | `create_search_provider()` |

**LLM Provider 缓存**: `ProviderRegistry` TTL 300s + SHA-256 cache key（含 api_key）+ PATCH settings 即时失效。

### 3.2 Orchestrator 图

```
load_context → safety_in → retrieve_kb → (need_web_search? → web_search) → llm_call → safety_out → persist → emit → END
```

- **safety_in**: 2000 字符截断 + 黑名单关键词拒答 → 短路至 emit
- **retrieve_kb**: top_k=5 / threshold=0.65 / 低置信触发 web_search
- **llm_call**: System Prompt 教模型插入 `[wave]`/`[nod]`/`[happy]` 动作标记
- **safety_out**: 密钥模式脱敏（sk-xxx / AKIAxxx / JWT）

### 3.3 WS 协议

**`/ws/chat?token=<jwt>`**: 文本对话，帧序列 `state(thinking)→token*→action*→done→state(done)`

**`/ws/voice?token=<jwt>`**: 语音全双工  
客户端 → 二进制音频帧 + JSON 控制消息 (voice.start/end/barge_in)  
服务端 → asr.partial/final + token + action + 二进制 TTS 帧

### 3.4 语音管线

```
MediaRecorder(250ms slices) → /ws/voice → ASR stream → Orchestrator → SentenceSplitter → TTS → AudioPump → 前端 Web Audio API + Live2D 口型
```

- **句切引擎**: `。！？\n` 触发分割 / min_chars=6 / 动作标记剥离 / flush+reset
- **AudioPump**: buffer > 3s → sleep 50ms 反压 / cancel+reset 打断
- **前端**: `useVoiceWs` + `useAudioPlayer` (Web Audio API decode + amplitude → 口型)

### 3.5 知识库管线

```
upload → OSS → INSERT documents(pending) → BackgroundTask
  → Parser(MIME→注册表) → Chunker(500/80 token 滑动窗口)
  → Embedding(batch=64, tenacity retry) → pgvector HNSW
  → status=ready|failed
```

- **重试**: 3 次指数退避 (2s→4s)，区分可重试(OSError/429/5xx)与不可重试(4xx/EmptyText)
- **安全网**: `_ensure_terminal_status()` 兜底——管线失败后文档不永久卡 processing

### 3.6 安全加固

| 机制 | 实现 |
|------|------|
| 限流 | Redis Lua 令牌桶：chat(5/s) / upload(2/s) / write(3/s) / WS(10/s) / auth(0.5/s, IP 维度) |
| 文件校验 | Magic number 字节匹配（JPEG/PNG/WebP/PDF/ZIP/DOCX），零外部依赖 |
| JWT/OSS 密钥 | 默认空字符串，staging/prod 无密钥拒绝启动 |
| 审计 | ASGI AuditMiddleware，fire-and-forget 写 audit_log，180 天保留 |
| Logger | 全部 `except` 块加 structlog，消除 14 处 `pass` 吞错 |

### 3.7 前端架构决策

- **Admin**: 6 按钮导航 (`currentView='xxx'`) 切换视图，Personas/Knowledge/Live2D 嵌 Dashboard.vue
- **Live2D**: 像素级 alpha 命中门控 + 手势锁定制止误触 + ratio 追踪平移边界
- **认证**: `router.beforeEach` 守卫 + Axios 401 自动 refresh + 并发请求排队
- **数据回退**: API 失败 → mock fallback，`isEmptyMetrics()` 等检测空响应自动切换

---

## 4. API 端点全表

### 认证

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/auth/register` | 无 | 注册 |
| POST | `/auth/login` | 无 | 登录 |
| POST | `/auth/refresh` | 无 | 刷新 token |
| GET | `/auth/me` | Bearer | 当前用户信息 |

### 用户端

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/user/preferences` | Bearer | 获取偏好（DB 持久化） |
| PATCH | `/user/preferences` | Bearer | 部分更新偏好 |
| POST | `/user/background` | Bearer | 上传背景图（magic + 限流） |
| POST | `/user/model` | Bearer | 上传 Live2D 模型包 |
| POST | `/conversations` | Bearer | 创建会话 |
| GET | `/conversations` | Bearer | 列出会话 |
| GET | `/conversations/{id}/messages` | Bearer | 列出消息 |
| POST | `/feedback` | Bearer | 提交反馈 |
| POST | `/voice/asr` | Bearer | 语音识别 REST fallback |
| POST | `/voice/tts` | Bearer | 文本转语音 |
| GET | `/voice/asr/config` | Bearer | ASR 服务配置 |

### 角色卡

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/personas?scope=public\|mine` | Bearer | 用户端列表 |
| POST | `/personas` | Bearer | 创建（普通用户仅 user scope） |
| GET | `/personas/{id}` | Bearer | 详情 |
| PATCH | `/personas/{id}` | Bearer | 更新自己的 |
| DELETE | `/personas/{id}` | Bearer | 软删除 |
| POST | `/personas/import` | Bearer | ST V2 JSON 导入 |
| GET | `/personas/{id}/export` | Bearer | ST V2 JSON 导出 |

### 文档 (用户端)

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/documents/upload` | Bearer | 上传文档 |
| GET | `/documents` | Bearer | 列出自己的 |
| GET | `/documents/{id}` | Bearer | 详情 |
| GET | `/documents/{id}/progress` | Bearer | 处理进度 |
| DELETE | `/documents/{id}` | Admin | 删 OSS + DB |
| POST | `/documents/{id}/reprocess` | Admin | 重新向量化 |

### 资源 (用户端)

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/assets/backgrounds` | Bearer | 上传背景 |
| GET | `/assets/backgrounds` | Bearer | 列出背景 |
| DELETE | `/assets/backgrounds/{id}` | Bearer(own) | 删除 |
| POST | `/assets/live2d` | Bearer | 上传模型 zip |
| GET | `/assets/live2d` | Bearer | 列出模型 |
| DELETE | `/assets/live2d/{id}` | Bearer(own) | 删除 |
| GET | `/assets/quota/{kind}` | Bearer | 配额查询 |

### 管理后台 (全部 require_admin)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/stats` | 账号数 + 对话数（真实数据） |
| GET/PATCH | `/admin/settings` | 系统设置（API key 脱敏） |
| GET/PATCH | `/admin/settings/{key}` | 单个设置 |
| GET | `/admin/users?keyword=&role=&page=&size=` | 用户分页列表 |
| GET | `/admin/users/{uid}` | 用户详情 |
| PATCH | `/admin/users/{uid}` | 改 role/disabled |
| DELETE | `/admin/users/{uid}` | 软删除 |
| GET/POST | `/admin/personas` | Persona CRUD |
| GET/PATCH/DELETE | `/admin/personas/{id}` | Persona 详情/更新/删除 |
| POST | `/admin/personas/{id}/set-default` | 设为默认 |
| POST | `/admin/personas/import` | ST V2 JSON 导入 |
| GET | `/admin/documents` | 全量文档列表 |
| POST | `/admin/documents/upload` | 上传文档 |
| GET | `/admin/documents/{id}` | 详情含 chunks |
| GET | `/admin/documents/{id}/status` | 处理进度 |
| DELETE | `/admin/documents/{id}` | 删 OSS + DB |
| POST | `/admin/documents/{id}/reprocess` | 重新向量化 |
| GET | `/admin/assets?kind=` | 全量资产列表 |
| DELETE | `/admin/assets/{id}` | 删 OSS + DB |
| GET | `/admin/audit?user_id=&action=&path=` | 审计日志查询 |
| GET | `/admin/audit/export` | CSV 导出 |
| GET | `/admin/dashboard/*` (7 端点) | 运营看板（Phase 5 占位） |
| GET | `/admin/dashboard/feedback` | 反馈列表（真实数据） |
| POST | `/admin/dashboard/feedback/{id}/reply` | 回复反馈 |
| GET/PATCH | `/admin/persona-config` | Persona Live2D 配置 |

### WebSocket

| 路径 | 鉴权 | 说明 |
|------|------|------|
| `/ws/chat?token=<jwt>` | JWT query param | 文本对话全双工 |
| `/ws/voice?token=<jwt>` | JWT query param | 语音全双工 |

> 📎 **前端 API 类型定义**: `apps/web-admin/src/services/types.ts` + `apps/web-user/src/services/types.ts`

---

## 5. 数据库迁移链

迁移 0001 → 0011，线性无分支：

| 迁移 | 内容 |
|------|------|
| `0001_init_pgvector` | pgvector + pgcrypto 扩展 |
| `0002_users_and_roles` | users 表 |
| `0003_conversation_tables` | chat_session + chat_message |
| `0004_feedback_table` | feedback 表 |
| `0005_knowledge_tables` | documents + knowledge_chunks (HNSW 索引) |
| `0006_assets_table` | assets 表 |
| `0007_user_admin_extras` | users 加 disabled + deleted_at |
| `0008_persona_table` | personas 表 (SillyTavern V2 字段) |
| `0009_user_preferences` | user_preferences 表 (JSONB) |
| `0010_system_setting` | system_settings 键值对表 |
| `0011_audit_log` | audit_log 表 (BRIN 索引) |

```bash
cd backend
EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira alembic upgrade head
```

---

## 6. 测试覆盖

| 层级 | 文件数 | 用例数 | 状态 |
|------|--------|--------|:--:|
| 单元测试 | 16 | 145 | ✅ |
| 集成测试 | 18 | 108 | ✅ |
| 验证门测试 | 1 | G-2.1 | ✅ |
| **合计** | **35** | **253** | ✅ |

```bash
# 运行全部测试
cd backend
EIRA_JWT__SECRET=test-secret EIRA_OSS__SECRET=eira-secret \
  EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
  EIRA_REDIS_URL=redis://localhost:6379/0 \
  EIRA_OSS_ENDPOINT=http://localhost:9000 \
  python -m pytest tests/ -v
```

**前端质量门**: `vue-tsc --noEmit` → 0 errors (web-user + web-admin)

### 未覆盖

- Playwright E2E 测试（spec 要求，未实现）
- Vitest 前端单元测试（配置就绪，无测试文件）
- G-2.2~G-2.4 / G-3.x / G-4.x 验证门（未执行）

---

## 7. 已知遗留问题

### 🔴 上线前必须处理

| # | 问题 | 位置 | 计划 |
|---|------|------|------|
| §4.5 | API key 明文存储 system_settings JSONB | `admin_settings.py` / config | pgcrypto + KMS 加密 |

### 🟡 生产部署前应处理

| # | 问题 | 位置 | 计划 |
|---|------|------|------|
| 5.4-R1 | Auth 限流用 `request.client.host` 非 `X-Forwarded-For` | `deps.py` | 反向代理后修复 |
| 6.1-R1 | ProviderRegistry.invalidate() 单进程，多 Worker 需 Redis pub/sub | `provider_registry.py` | Phase 5 |
| 6.2-R1 | Pipeline 用 asyncio task 无崩溃恢复 | `knowledge_worker.py` | Phase 5: Celery 升级 |
| 6.2-R2 | Pipeline 重试无 Prometheus metrics | `knowledge_worker.py` | 运维优化 |

### 🟢 后续改进

| # | 问题 |
|---|------|
| 1 | Dashboard 运营看板 7 个占位端点（Phase 5 填充） |
| 2 | Admin 无用户管理前端页面（API 已就绪） |
| 3 | web-user `components/` 7 个 deprecated 孤立组件 |
| 4 | SillyTavern PNG 角色卡导入（当前仅 JSON） |
| 5 | 用户端角色卡选择 UI 未集成 |
| 6 | OSS 孤立文件清理机制（OSS 删除失败时 DB 行已删） |
| 7 | Chunker 短文档静默丢弃（低于 80 tokens） |
| 8 | structlog 缺少 `format_exc_info` processor（`exc_info=True` 已改为 `error=str(exc)`） |
| 9 | Asset `is_default` 字段后端不支持 |
| 10 | Asset admin 上传端点路径与前端不匹配 |

---

## 8. 快速启动指南

```bash
# 1. Docker 依赖
docker compose -f deploy/docker-compose.dev.yml up -d

# 2. 数据库迁移
cd backend
EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira alembic upgrade head

# 3. 后端启动（默认 mock provider）
EIRA_JWT__SECRET=dev-secret \
EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
EIRA_REDIS_URL=redis://localhost:6379/0 \
EIRA_OSS_ENDPOINT=http://localhost:9000 \
EIRA_OSS__SECRET=eira-secret \
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. 前端启动
pnpm install
pnpm --filter @eira/web-user dev      # http://localhost:5173
pnpm --filter @eira/web-admin dev     # http://localhost:5174

# 5. 测试
cd backend
EIRA_JWT__SECRET=test-secret EIRA_OSS__SECRET=eira-secret \
  python -m pytest tests/ -v
```

### 测试账号

| 地址 | 邮箱 | 密码 |
|------|------|------|
| http://localhost:5173/login | `admin@eira.dev` | `Admin123!` |
| http://localhost:5174/login | `admin@eira.dev` | `Admin123!` |

### 真实 LLM

```bash
export EIRA_LLM__PROVIDER=deepseek
export EIRA_LLM__API_KEY=sk-your-key
```

未设置时自动 fallback Mock Provider。

---

## 9. 归档索引

全部历史文档位于 `docs/superpowers/handoff/archive/`：

### Handoff 文档（15 个）

| 文件 | 内容 |
|------|------|
| `2026-05-28-phase0-handoff.md` | Phase 0 基础设施细节 |
| `2026-06-03-phase1-api-spec.md` | Phase 1 原始 API 规格 |
| `2026-06-04-current-state-handoff.md` | 2026-06-04 状态快照 |
| `2026-06-06-current-state-handoff.md` | 2026-06-06 状态快照 |
| `2026-06-06-frontend-api-spec.md` | 前端 API 需求规格 |
| `2026-06-07-live2d-interaction-handoff.md` | Live2D 交互修复 |
| `2026-06-08-phase2-handoff.md` | Phase 2 知识库 RAG |
| `2026-06-08-phase3-handoff.md` | Phase 3 语音多模态 |
| `2026-06-08-phase4-handoff.md` | Phase 4 管理后台主体 |
| `2026-06-08-phase4-fixes-handoff.md` | Phase 4 7 项功能修复 |
| `2026-06-08-phase4-gap-closure-handoff.md` | Phase 4 4 个缺口闭合 |
| `2026-06-08-phase4-p0-fixes-handoff.md` | Phase 4 P0 紧急修复 |
| `2026-06-08-security-audit-and-test-fixes.md` | 安全审计 + 测试修复 |
| `2026-06-09-phase1-complete-handoff.md` | Phase 1 完整交接 |
| `2026-06-09-security-fixes-handoff.md` | §5.4+5.5+6.1+6.2+6.4 修复 |

### Plans 文档

| 位置 | 内容 |
|------|------|
| `docs/superpowers/plans/` | 当前计划（overview + Phase 0-7） |
| `docs/superpowers/plans/archive/` | 原始未精简版计划 (2026-06-02 前) |
| `C:/Users/.../.claude/plans/archive/` | Claude Code 会话级实施计划（12 个，全部已执行） |

---

**签出**: 本文档整合自 15 个 handoff + 多次全量代码审查，覆盖 Phase 0-4 全部工作和修复链。  
**下一步**: commit 当前分支 → Phase 5（运营看板）或 Phase 1-4 验证门闭合。
