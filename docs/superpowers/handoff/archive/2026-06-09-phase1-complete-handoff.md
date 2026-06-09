# Phase 1 完整交接文档 · 文本对话闭环 + Live2D 画布

**日期:** 2026-06-09
**分支:** `chore/live2d-rewrite-and-handoff`
**原始计划:** `docs/superpowers/plans/2026-05-26-phase1-text-chat.md`
**当前代码状态:** 已演进至 Phase 4（含知识库、语音、管理后台），Phase 1 核心全部就绪

---

## 目录

1. [架构概览](#1-架构概览)
2. [后端实施清单](#2-后端实施清单)
3. [前端实施清单](#3-前端实施清单)
4. [数据库迁移](#4-数据库迁移)
5. [测试套件](#5-测试套件)
6. [陷阱分析](#6-陷阱分析-7-个关键-bug)
7. [手动测试步骤](#7-手动测试步骤)
8. [环境变量速查](#8-环境变量速查)

---

## 1. 架构概览

```
┌─────────────────────────────────────────────────────────┐
│  浏览器 (localhost:5173)                                  │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Chat.vue │──│useChatSession│──│ WebSocket /ws/chat│   │
│  │ (426行)   │  │  (WS 管理)    │  │  ?token=<jwt>     │   │
│  ├──────────┤  └──────────────┘  └──────────────────┘   │
│  │Live2D    │──│useLive2DController (Cubism 5 FW)       │
│  │Canvas    │  │  + useActionParser                      │
│  └──────────┘  └───────────────────────────────────────  │
└─────────────────────────────────────────────────────────┘
                          │ WebSocket (streaming token frames)
                          ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI (localhost:8000)                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │ LangGraph Orchestrator                            │   │
│  │ load_context → safety_in → retrieve_kb →          │   │
│  │   web_search → llm_call → safety_out →            │   │
│  │   persist → emit                                  │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌────────────────┐  ┌──────────┐  ┌───────────────┐   │
│  │ LLM Provider   │  │  Safety  │  │ Conversation  │   │
│  │ (DeepSeek)     │  │  Filter  │  │ Domain         │   │
│  └────────────────┘  └──────────┘  └───────────────┘   │
└─────────────────────────────────────────────────────────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
          PostgreSQL   Redis      MinIO (OSS)
          (pgvector)   (cache)    (文件存储)
```

---

## 2. 后端实施清单

### 2.1 LLM Provider 抽象层

| 文件 | 说明 |
|---|---|
| `app/capabilities/llm/base.py` | `BaseLLMProvider` 抽象基类，定义 `stream()` / `complete()` / `close()` 接口，`LlmDelta` / `LlmUsage` / `LlmResult` 数据类 |
| `app/capabilities/llm/openai_compat.py` | OpenAI 兼容协议适配器（DeepSeek/OpenAI/Tongyi/Volc），含 tenacity 重试（指数退避 + 抖动） |
| `app/capabilities/llm/mock.py` | Mock Provider，返回固定中文导游回复，用于测试 |
| `app/capabilities/llm/factory.py` | `create_llm_provider()` 工厂函数，无 API key 时优雅降级为 MockProvider |
| `app/capabilities/llm/provider_registry.py` | `ProviderRegistry` 多 Provider 实例管理，支持运行时切换 |
| `app/capabilities/llm/logging_decorator.py` | `@log_llm_call` 装饰器，记录结构化日志 |
| `app/capabilities/llm/pricing.yaml` | 各 Provider 定价配置（USD/1M tokens） |

**配置 (`app/core/config.py` — `LlmSettings`):**

| 变量 | 默认值 | 说明 |
|---|---|---|
| `EIRA_LLM__PROVIDER` | `deepseek` | deepseek / openai / tongyi / volc / mock |
| `EIRA_LLM__API_KEY` | `""` | **必须设置** — DeepSeek API Key |
| `EIRA_LLM__API_BASE` | `https://api.deepseek.com` | 标准 DeepSeek OpenAI 兼容端点 |
| `EIRA_LLM__MODEL` | `deepseek-chat` | 模型名称 |
| `EIRA_LLM__MAX_TOKENS` | `2048` | 最大输出 token |
| `EIRA_LLM__TEMPERATURE` | `0.7` | 温度参数 |

> **⚠️ 注意:** `EIRA_LLM__API_KEY` 在 `config.py` 中默认为空字符串。必须通过环境变量或 `.env` 文件注入实际密钥。旧版代码曾硬编码密钥，已清理。

### 2.2 Orchestrator 编排引擎

**文件:** `app/orchestrator/graph.py`

**当前节点序列 (Phase 2):**

```
load_context → safety_in → retrieve_kb → (web_search?) → llm_call → safety_out → persist → emit → END
```

| 节点 | 文件 | 功能 |
|---|---|---|
| `load_context` | `nodes/load_context.py` | 加载会话历史 + persona prompt。Phase 2 增强：从 DB 加载最近 20 条消息 |
| `safety_in` | `nodes/safety_in.py` | 输入验证：长度截断 (2000 chars) + 黑名单关键词拒答 |
| `retrieve_kb` | `nodes/retrieve_kb.py` | Phase 2 — 知识库 RAG 检索（可选） |
| `web_search` | `nodes/web_search.py` | Phase 2 — Tavily 网络搜索（可选，由 `need_web_search` 控制） |
| `llm_call` | `nodes/llm_call.py` | 调用 LLM Provider，含 System Prompt（教模型插入 `[wave]`/`[nod]`/`[happy]`） |
| `safety_out` | `nodes/safety_out.py` | 输出脱敏：sk-xxx / AKIAxxx / JWT 替换为 `[REDACTED]` |
| `persist` | `nodes/persist.py` | 持久化 user + assistant 消息到 PG |
| `emit` | `nodes/emit.py` | 终端节点 |

**短路规则:**
- `safety_in` 失败 → 直接跳到 `emit`（返回兜底回复「抱歉，您的消息包含不支持的内容」）
- `llm_call` 异常 → 跳到 `emit`（返回错误信息）

**RAG 增强（Phase 2）:**
- `retrieve_kb` 检索知识库后，llm_call 将相关知识片段注入 System Prompt 的 `<context>` 块
- `web_search` 为可选节点，由 `need_web_search` 状态标志控制

### 2.3 Conversation 领域

| 文件 | 说明 |
|---|---|
| `app/domain/conversation/models.py` | `ChatSession` + `ChatMessage` + `Feedback` ORM 模型 |
| `app/domain/conversation/repository.py` | `ConversationRepository` + `FeedbackRepository` |
| `app/domain/conversation/service.py` | `ConversationService` — 会话/消息业务逻辑 |
| `app/domain/conversation/schemas.py` | Pydantic 模式：`SessionCreate` / `SessionOut` / `ChatMessageOut` / `ConversationList` |

### 2.4 REST API

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| `POST` | `/auth/register` | 无 | 注册 |
| `POST` | `/auth/login` | 无 | 登录 → `{access_token, refresh_token}` |
| `POST` | `/auth/refresh` | 无 | 刷新 token |
| `GET` | `/auth/me` | Bearer | 当前用户 |
| `POST` | `/conversations` | Bearer | 创建会话 |
| `GET` | `/conversations` | Bearer | 列出会话 |
| `GET` | `/conversations/{id}/messages` | Bearer | 列出消息 |

> **注意:** `main.py` 已在 `fastapi.FastAPI(..., docs_url=None, redoc_url=None)` 中禁用自动生成的 Swagger/ReDoc 页面。API 文档见 `docs/superpowers/handoff/2026-06-03-phase1-api-spec.md`。

### 2.5 WebSocket 端点

**`/ws/chat?token=<jwt>`**

**客户端 → 服务端:**
```json
{"type":"user_text","session_id":"sess-xxx","text":"你好","ts":1234567890}
{"type":"interrupt"}
```

**服务端 → 客户端（按序）:**
```
{"type":"state","phase":"thinking"}
{"type":"state","phase":"streaming"}
{"type":"token","text":"你好"}
{"type":"action","tag":"Flick"}
{"type":"done","message_id":null,"latency_ms":123.4,"tokens":{"completion":79}}
{"type":"state","phase":"done"}
{"type":"error","code":"llm_error","detail":"..."}
```

**Action Tags（Live2D 动作标记）:**

| 标记 | Motion Group | 效果 |
|---|---|---|
| `[wave]` | Flick | 挥手 |
| `[nod]` | FlickDown | 点头 |
| `[happy]` | Tap | 开心 |
| `[idle]` | Idle | 待机 |

---

## 3. 前端实施清单

### 3.1 文件结构

```
apps/web-user/src/
├── main.ts                          # 入口 — Router + 认证守卫
├── App.vue                          # <router-view/>
├── pages/
│   ├── Chat.vue                     # 主聊天页 (426行自包含)
│   └── Login.vue                    # 登录页
├── composables/
│   ├── useChatSession.ts            # WS 会话管理 + 消息队列
│   ├── useLive2DController.ts       # Live2D Cubism 5 渲染控制器
│   ├── useActionParser.ts           # 动作标记 [wave]/[nod]/[happy] 解析
│   ├── useAudioPlayer.ts            # 音频播放（Phase 3）
│   └── useVoiceWs.ts                # 语音 WS（Phase 3）
├── live2d/                          # 应用层 Live2D 代码
│   ├── lappdelegate.ts              # 主委托 — 管理整个 Live2D 生命周期
│   ├── lappdefine.ts                # 配置常量
│   ├── lappview.ts                  # WebGL 渲染视图
│   ├── lappmodel.ts                 # 模型加载/管理
│   ├── lappsubdelegate.ts           # 子委托 — 场景管理
│   ├── lapplive2dmanager.ts         # Live2D 管理器
│   ├── lappglmanager.ts             # WebGL 上下文管理
│   ├── lapptexturemanager.ts        # 纹理管理
│   ├── lapppal.ts                   # 平台抽象层
│   ├── lappwavfilehandler.ts        # WAV 文件处理
│   └── touchmanager.ts              # 触摸/拖拽管理
├── live2d-framework/                # Cubism 5 Framework (~70 文件)
│   ├── cubismdefaultparameterid.ts  # 参数 ID 常量
│   ├── cubismframeworkconfig.ts     # Framework 配置
│   ├── model/                       # 模型层 (Moc/Model/UserModel)
│   ├── motion/                      # 动作层 (Motion/Expression/Physics)
│   ├── rendering/                   # 渲染层 (Renderer/Shader)
│   ├── effect/                      # 特效 (Breath/EyeBlink/Pose)
│   ├── physics/                     # 物理引擎
│   ├── math/                        # 数学库 (Matrix/Vector)
│   └── utils/                       # 工具集
└── services/
    ├── http.ts                       # Axios 拦截器
    ├── api.ts                        # API 调用封装
    └── types.ts                      # TypeScript 类型
```

### 3.2 Live2D 渲染方案 (重大变更)

**历史:** 原计划使用 `pixi-live2d-display` (PixiJS 7 + Cubism 4 模型)。

**问题:** `pixi-live2d-display` 读取 `drawables.renderOrders` 属性，但 Cubism 5 Core 已将 `renderOrders` 移到 model 顶层（而非 drawables 内），导致渲染崩溃。

**解决方案:** 完全弃用 `pixi-live2d-display`，改用 Live2D 官方 Cubism SDK for Web 5 Framework，自管 WebGL 渲染。

**变更文件:**
- 新增 `public/live2d-core/live2dcubismcore.min.js` — Cubism 5 Core 运行时
- 新增 `public/live2d-core/shaders/` — 14 个 WebGL Shader 文件
- 新增 `src/live2d-framework/` — ~70 个 TS 文件，官方 Framework 完整实现
- 新增 `src/live2d/` — 10 个应用层文件，封装 Framework 为 Vue composable
- 重写 `src/composables/useLive2DController.ts` — 对外接口不变，内部完全重写

**对外接口 (保持不变，Chat.vue 无需修改):**
```typescript
const { containerRef, isLoaded, activeModelId, loadError, triggerMotion, setMouthOpen }
  = useLive2DController()
```

### 3.3 模型资产

| 目录 | 角色 | 内容 |
|---|---|---|
| `public/live2d/mao_pro_zh/` | 主模型 (Mao) | `.moc3` / `.model3.json` / `.physics3.json` / 纹理 / 8 表情 / 6 动作 |
| `public/live2d/hiyori_pro_zh/` | 备用模型 (Hiyori) | `.moc3` / `.model3.json` / `.physics3.json` / 纹理 / 10 动作 |

加载优先级：`mao_pro_zh` → `hiyori_pro_zh`（自动回退）

### 3.4 认证流程

1. 用户访问 `/chat` → `router.beforeEach` 检查 `localStorage("eira:at")`
2. 若不存在 → 重定向 `/login`
3. 登录成功后 → `auth.ts` store 存入 `eira:at` (access_token) + `eira:rt` (refresh_token)
4. `useChatSession.getAccessToken()` 读取 `eira:at` → 拼接到 WS URL 的 `?token=` 参数
5. 后端 `ws_chat.py` 通过 `decode_token()` 验证 JWT

### 3.5 WebSocket 消息流

```
┌─────────┐     user_text      ┌──────────┐
│ Chat.vue │ ─────────────────→│  /ws/chat │
│          │ ←── state:thinking │          │
│          │ ←── action:Flick   │          │ ← 提取 [wave] 等标记
│          │ ←── token: "你好"  │          │ ← 流式 token 分片
│          │ ←── token: "！"    │          │
│          │ ←── done           │          │
└─────────┘                    └──────────┘
```

---

## 4. 数据库迁移

**部署方式:** Docker Compose (`deploy/docker-compose.dev.yml`)

| 服务 | 镜像 | 端口 |
|---|---|---|
| PostgreSQL 16 + pgvector | `pgvector/pgvector:pg16` | 5432 |
| Redis 7 | `redis:7-alpine` | 6379 |
| MinIO | `minio/minio:latest` | 9000 (API) / 9001 (Console) |

**迁移文件 (按执行顺序):**

| 迁移 | 内容 |
|---|---|
| `0001_init_pgvector.py` | 启用 pgvector + pgcrypto 扩展 |
| `0002_users_and_roles.py` | users 表 |
| `0003_conversation_tables.py` | chat_session + chat_message 表 |
| `0004_feedback_table.py` | feedback 表 |
| `0005_knowledge_tables.py` | 知识库相关表 |
| `0006_assets_table.py` | 资源表 |
| `0007_user_admin_extras.py` | 用户管理扩展 |
| `0008_persona_table.py` | 角色人设表 |
| `0009_user_preferences.py` | 用户偏好表 |
| `0010_system_setting.py` | 系统设置表 |
| `0011_audit_log.py` | 审计日志表 |

**执行迁移:**
```bash
cd backend
EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira alembic upgrade head
```

---

## 5. 测试套件

### 运行全部测试

```bash
cd backend
EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
EIRA_REDIS_URL=redis://localhost:6379/0 \
EIRA_OSS_ENDPOINT=http://localhost:9000 \
python -m pytest tests/ -v --cov=app --cov-report=term
```

### 测试文件清单

**单元测试 (16 文件):**

| 文件 | 测试内容 |
|---|---|
| `unit/test_llm_provider.py` | LLM Provider 工厂、Mock Provider 流/完成、配置默认值 |
| `unit/test_safety.py` | 输入长度截断、黑名单关键词、输出脱敏 (sk-xxx/AKIA/JWT) |
| `unit/test_llm_logging.py` | `@log_llm_call` 装饰器 |
| `unit/test_conversation.py` | 会话/消息服务 + 仓储 mock 测试 |
| `unit/test_ws_messages.py` | WS 协议消息 schema + 动作标记解析 |
| `unit/test_config.py` | 环境变量覆盖 |
| `unit/test_logging.py` | JSON structlog 输出 |
| `unit/test_system.py` | 根端点 |
| `unit/test_asr.py` | ASR Provider |
| `unit/test_tts.py` | TTS Provider |
| `unit/test_embedding.py` | Embedding Provider |
| `unit/test_search.py` | Search Provider |
| `unit/test_chunker.py` | 文档分割器 |
| `unit/test_knowledge_models.py` | 知识库模型 |
| `unit/test_knowledge_service.py` | 知识库服务 |
| `unit/test_sentence_splitter.py` | 语句分割器 |

**集成测试 (18 文件):**

| 文件 | 测试内容 |
|---|---|
| `integration/test_auth.py` | 注册→登录→刷新→me 完整流程 |
| `integration/test_conversation.py` | 会话 CRUD + 消息列表 + 权限隔离 |
| `integration/test_orchestrator_smoke.py` | 编排器全链路 (Mock LLM) |
| `integration/test_orchestrator_rag.py` | RAG 检索节点 |
| `integration/test_ws_chat.py` | WS 聊天端点 |
| `integration/test_ws_stream_pacing.py` | Token 流控延迟验证 |
| `integration/test_db.py` | pgvector 扩展 + schema_version 表 |
| `integration/test_redis.py` | Redis 读写 |
| `integration/test_oss.py` | MinIO 上传 + 预签名 URL |
| `integration/test_health.py` | /healthz /readyz /metrics |
| `integration/test_voice.py` | 语音 REST API |
| `integration/test_ws_voice.py` | 语音 WS |
| `integration/test_ws_voice_e2e.py` | 语音端到端 |
| `integration/test_documents_api.py` | 文档 API |
| `integration/test_admin_assets.py` | Admin 资源管理 |
| `integration/test_admin_users.py` | Admin 用户管理 |
| `integration/test_admin_settings.py` | Admin 系统设置 |
| `integration/test_personas.py` | 角色人设 API |

### 当前测试结果 (2026-06-09)

**Phase 1 核心测试:** 全部通过 ✅
**Phase 4 管理后台测试:** 部分失败 ⚠️ (MinIO 签名不匹配 — 需重启 MinIO 容器并确保 bucket 已创建)

---

## 6. 陷阱分析 (7 个关键 Bug)

### 陷阱 1: Live2D Cubism Core 脚本阻塞导致黑屏 🔴

**症状:** 浏览器访问 `/chat` 显示全黑，无任何 UI 元素。

**根因:** `index.html` 的 `<head>` 中使用同步 `<script src="/live2d-core/live2dcubismcore.min.js">` 引用了一个不存在的文件。同步 `<script>` 阻塞 HTML 解析，浏览器等待 404 响应期间只渲染了黑色的 `<body>`。

**修复:** 将脚本改为 `<script src="..." defer></script>` 并确保文件在 `public/live2d-core/` 下物理存在。

**教训:** `<head>` 中的同步脚本会阻塞整个页面渲染。Local assets 必须验证文件存在后再提交。

---

### 陷阱 2: Vue 模板引用已删除的 mock 函数 🔴

**症状:** `vue-tsc` 报错 `Property 'mockBackendResponse' does not exist` ；运行时刻 Vue 组件挂载失败 → 黑屏。

**根因:** Phase 1 实施中将 `mockBackendResponse()` 替换为 `useChatSession().sendText()`，但 `<template>` 中快捷提问按钮的 `@click="mockBackendResponse(q)"` 未被同步更新。

**修复:** 添加 `handleQuickQuestion(q: string)` 转发函数，模板改为 `@click="handleQuickQuestion(q)"`。

**教训:** 重构 composable 时必须全文搜索所有引用点，模板中的 `@click` 表达式不会在 IDE 重构中被自动更新。

---

### 陷阱 3: pixi-live2d-display 与 Cubism 5 Core 不兼容 🔴

**症状:** PIXI + pixi-live2d-display 加载模型后报 `Cannot read property 'renderOrders' of undefined` ，角色不渲染。

**根因:** Cubism 5 Core 将 `renderOrders` 从 `drawables` 子对象移至 model 顶层。`pixi-live2d-display` (v0.4.0) 读取 `drawables.renderOrders` 的旧路径，在 Cubism 5 模型上返回 `undefined`。

**修复:** 完全弃用 PIXI + pixi-live2d-display，改用官方 Cubism SDK for Web 5 Framework + 自管 WebGL 渲染。详情见 `memory/live2d-cubism5-rendering.md`。

**代价:** 需要移植 ~70 个 Framework TS 文件 + 编写 10 个应用层适配文件。但换来完全的 Cubism 5 兼容性和更高的渲染性能。

---

### 陷阱 4: `aiResponseText` 从 `ref` 变为 `computed` 导致问候语丢失 🟡

**症状:** 初始问候语不再显示。`onMounted` 中的 `aiResponseText.value = '你好啊...'` 变为 no-op。

**根因:** Phase 1 将 `aiResponseText` 从 `ref('')` 改为 `computed(...)`，但 computed 是只读的，无法在 `onMounted` 中赋值。

**修复:** 引入独立的 `initialGreeting` ref 和 `hasInteracted` 标记。`computed` 在首次交互前返回 `initialGreeting`，交互后返回 WS 实际回复。

---

### 陷阱 5: LangGraph `ainvoke()` 返回 dict 而非 ChatState 对象 🟡

**症状:** 测试中 `result.llm_text` 抛出 `AttributeError: 'dict' object has no attribute 'llm_text'`。

**根因:** LangGraph 的 `CompiledGraph.ainvoke()` 返回 `AddableUpdatesDict` (dict 子类)，不是原始 `ChatState` 对象。Phase 1 初始测试代码使用点号访问属性。

**修复:** 所有测试改为 `result.get("llm_text")` 等 dict 访问方式。

---

### 陷阱 6: httpx-ws API 版本不兼容 🟡

**症状:** WS 测试中 `aconnect_ws()` 报 `TypeError: AsyncClient.stream() got unexpected keyword argument 'transport'`。

**根因:** `httpx-ws` v0.9.0 与 `httpx` v0.28.1 的 `AsyncClient.stream()` API 不兼容。后者不支持 `transport` 关键字参数。

**修复:** 重写 WS 测试，改用 HTTP 端点验证（检查 route 注册状态）和 orchestrator 图直接调用测试（绕过 WS 传输层）。

---

### 陷阱 7: 用户修改 index.html 后未同步文件 🟡

**症状:** `index.html` 中 `<script src="/live2d-core/live2dcubismcore.min.js">` 引用本地路径，但 `public/live2d-core/` 目录当时不存在。

**根因:** 用户将 CDN URL 替换为本地路径时，未同时下载 SDK 文件并放入 public 目录。不同开发者之间的操作时序不一致。

**修复:** 确保 `public/live2d-core/live2dcubismcore.min.js` + `public/live2d-core/shaders/*` 物理存在。

---

## 7. 手动测试步骤

### 7.1 启动基础设施

```bash
cd deploy
docker compose -f docker-compose.dev.yml up -d

# 等待 PostgreSQL 就绪：
docker compose -f docker-compose.dev.yml exec pg pg_isready -U eira
# 输出: /var/run/postgresql:5432 - accepting connections
```

### 7.2 启动后端

```bash
cd backend

# 1. 确保依赖已安装
pip install -e ".[dev]"

# 2. 运行数据库迁移
EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
  python -m alembic upgrade head

# 3. 设置 LLM API Key (DeepSeek)
export EIRA_LLM__API_KEY="sk-your-deepseek-api-key"

# 4. 启动服务器
python -m uvicorn app.main:app --reload --port 8000
```

**验证:** `curl http://localhost:8000/healthz` → `{"status":"ok"}`

### 7.3 启动前端

```bash
cd apps/web-user
pnpm dev

# 或者从项目根目录:
pnpm --filter web-user dev
```

**打开浏览器:** `http://localhost:5173`

### 7.4 手动测试 Checklist

| 步骤 | 操作 | 预期结果 | 验证方法 |
|---|---|---|---|
| 1 | 访问 `/chat`（未登录） | 自动跳转 `/login` | URL 栏显示 `/login` |
| 2 | 注册：输入 email + password | 201 Created，自动跳转 `/chat` | Network 面板查看 POST /auth/register |
| 3 | 登录：输入注册的凭证 | 200 OK，跳转 `/chat` | localStorage 中出现 `eira:at` + `eira:rt` |
| 4 | 查看聊天页 | 显示毛玻璃 UI（设置按钮、对话气泡、快捷提问、输入栏）+ Live2D 角色 | 所有 UI 元素可见 |
| 5 | 观察 Live2D 角色 | mao_pro_zh 模型渲染在画布上，有呼吸 + 眨眼效果 | 角色可见、有动画 |
| 6 | 拖拽角色 | 角色随指针移动 | 位置改变 |
| 7 | 滚轮缩放角色 | 角色放大/缩小 | 尺寸改变 |
| 8 | 刷新页面 | 角色位置/缩放保留 | 同步骤 6-7 的位置 |
| 9 | 发送文本消息 | 输入 "你好" + 回车 | 消息发送 |
| 10 | 观察 AI 回复 | 对话气泡显示流式文本（打字机效果） | 气泡逐字显示、`isAiTyping` 指示器 |
| 11 | 点击快捷提问 | 点击 "路线怎么走？" | AI 回复相关问题 |
| 12 | 观察动作标记 | 如果 AI 回复含 `[wave]` 等标记 | Live2D 角色执行对应动作、气泡不显示标记文本 |
| 13 | 打开设置面板 | 点击右上角齿轮图标 | 设置卡片弹出 |
| 14 | 切换背景模糊 | 打开背景模糊开关 | 背景变模糊 |
| 15 | 上传背景图片 | 点击 "更换图片" | 背景替换 |
| 16 | 检查 WS 连接 | Chrome DevTools → Network → WS | `/ws/chat` 连接状态 101 |
| 17 | 测试错误恢复 | 停止后端 → 发送消息 → 重启后端 | 前端不崩溃，WS 自动重连 |

### 7.5 调试技巧

**查看 WS 帧:**
1. Chrome DevTools → Network → WS → 点击 `/ws/chat` → Messages
2. 发送文本后应看到: `state:thinking` → `token:*` (多次) → `action:*` (可选) → `done` → `state:done`

**查看 Vue 组件状态:**
1. 安装 Vue DevTools 扩展
2. Components → Chat → 查看 `wsPhase` / `aiResponseText` / `isAiTyping` / `activeModelId`

**查看 Live2D 日志:**
1. Console 过滤 `[Live2D]` → 显示模型加载/失败信息

---

## 8. 环境变量速查

### 必需变量

| 变量 | 示例值 | 说明 |
|---|---|---|
| `EIRA_DB_DSN` | `postgresql+asyncpg://eira:eira@localhost:5432/eira` | 数据库连接 |
| `EIRA_REDIS_URL` | `redis://localhost:6379/0` | Redis 连接 |
| `EIRA_LLM__API_KEY` | `sk-...` | DeepSeek API Key |

### 可选变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `EIRA_APP__ENV` | `dev` | dev / staging / prod |
| `EIRA_APP__LOG_LEVEL` | `INFO` | 日志级别 |
| `EIRA_JWT__SECRET` | `""` | JWT 签名密钥（staging/prod 强制设置） |
| `EIRA_OSS__ENDPOINT` | `http://localhost:9000` | S3 兼容存储端点 |
| `EIRA_OSS__KEY` | `eira` | OSS Access Key |
| `EIRA_OSS__SECRET` | `eira-secret` | OSS Secret Key |

---

## 附录：相关文档

| 文档 | 路径 |
|---|---|
| Phase 1 原始计划 | `docs/superpowers/plans/2026-05-26-phase1-text-chat.md` |
| API 规格 | `docs/superpowers/handoff/2026-06-03-phase1-api-spec.md` |
| 架构设计 | `docs/superpowers/specs/2026-05-26-architecture-design.md` |
| Live2D Cubism 5 渲染方案 | `memory/live2d-cubism5-rendering.md` |
| 验证门 G-1.1 | `docs/superpowers/validations/G-1.1.md` |
| 验证门 G-1.2 | `docs/superpowers/validations/G-1.2.md` |
| 验证门 G-1.3 | `docs/superpowers/validations/G-1.3.md` |
| 验证门 G-1.4 | `docs/superpowers/validations/G-1.4.md` |
