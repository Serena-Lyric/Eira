---
name: 2026-05-26-architecture-design
title: Eira 景区 AI 数字人导览系统 · 总体架构设计
date: 2026-05-26
status: draft
source: docs/DESIGN.txt
---

# Eira 景区 AI 数字人导览系统 · 总体架构设计

## 0. 文档定位

本文档为顶层架构规约（"宪法"），覆盖技术栈选型、分层划分、模块边界、数据模型、关键时序、横切关注点、实施分期与后续 spec 拆分。后续每个子模块 spec 不重新讨论本文档已锁定的决策；可在子 spec 中扩展或细化。

源需求：`docs/DESIGN.txt`。示范知识包：`docs/示范景区公开资料包/`。

---

## 1. 关键决策汇总

| 维度 | 决策 |
|---|---|
| 后端语言/框架 | Python 3.11+ / FastAPI（单体模块化） |
| 前端框架 | Vue 3 + Vite + TypeScript（用户端、管理后台双 SPA） |
| 部署形态 | 公有云后端 + 浏览器访问（用户与管理员均通过浏览器登录） |
| LLM 接入 | 以云 API 为主，Provider 抽象层支持切换 |
| 语音 | 云 ASR + 云 TTS（流式） |
| 数据存储 | PostgreSQL（含 pgvector）+ Redis + 云对象存储（OSS） |
| 知识库向量化 | 手动触发；保留"重新向量化"按钮 |
| Agent 编排 | 有状态图编排（LangGraph 或等价实现），节点可插拔 |
| 实时通信 | WebSocket 全双向 |
| 记忆 | 短期（Redis 滚动上下文）+ 长期（关键事实抽取入 pgvector） |
| Live2D | 前端 Cubism Web SDK + PixiJS 实时驱动 |
| 互联网检索 | 集成 Web Search Provider（Tavily/Bocha 等），RAG 命中不足时降级 |
| 鉴权 | 双端均需登录，JWT（access + refresh）；角色 visitor/admin/superadmin |
| 情感识别 | 架构预留节点，MVP 默认返回 neutral；v2 接入真实模型 |
| 多租户 | 字段级预留（所有领域查询带 `tenant_id`），MVP 单租户 |

---

## 2. 系统总览与分层

### 2.1 角色

- **游客**：浏览器访问用户端 SPA，与 Live2D 数字人交互（语音/文字问答、个性化讲解、满意度反馈）。
- **景区管理员**：浏览器访问管理后台 SPA，管理知识库、角色卡、Live2D 模型、查看运营数据。

### 2.2 五层架构

```
┌──────────────────────────────────────────────────────┐
│  L1  接入层    Nginx 反向代理 + WSS + 静态资源                                            │
├──────────────────────────────────────────────────────┤
│  L2  前端层    用户端 SPA  +  管理后台 SPA                                                     │
│                Vue 3 + Vite + TS + Pinia                                                             │
│                共享 UI 包（玻璃拟态组件）                                                            │
├──────────────────────────────────────────────────────┤
│  L3  应用层    FastAPI 单体（模块化）                                                             │
│  ┌─────────────────────────────────────────────────┐     │
│  │ API Layer       REST + WebSocket                                                      │     │
│  │ Domain Services 用户/角色卡/会话/知识库/运营                                   │     │
│  │ AI Orchestrator LangGraph 图，节点可插拔                                         │    │
│  │ Capability      LLM/ASR/TTS/Search/Embed Adapter                           │    │
│  │ Knowledge       Parser→Chunk→Embed→Index 流水线                       │    │
│  │ Background      APScheduler / asyncio Task                                       │    │
│  └─────────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────┤
│  L4  数据层    PostgreSQL(+pgvector) / Redis / OSS                                      │
├──────────────────────────────────────────────────────┤
│  L5  外部服务  LLM API / ASR / TTS / Web Search                                          │
└──────────────────────────────────────────────────────┘
```

### 2.3 单体模块化原则

后端单进程，但代码按 bounded context 划分包，每个包仅通过显式 service interface 互相调用：

- 模块边界清晰，未来可独立拆出（如 RAG 服务）。
- 每个包独立测试，文件不会膨胀。
- 利于 AI 协作开发——一次只看一个有界上下文。

### 2.4 仓库结构

```
Eira/
├─ apps/
│  ├─ web-user/        # 用户端 SPA
│  └─ web-admin/       # 管理后台 SPA
├─ packages/
│  └─ ui-shared/       # 共享 UI 组件 + 主题 token
├─ backend/
│  ├─ app/
│  │  ├─ api/          # FastAPI 路由（REST + WS）
│  │  ├─ core/         # 配置、依赖注入、异常、日志
│  │  ├─ domain/
│  │  │  ├─ identity/      # 用户 + 鉴权
│  │  │  ├─ persona/       # 角色卡
│  │  │  ├─ conversation/  # 会话 + 消息
│  │  │  ├─ knowledge/     # 知识库 + RAG
│  │  │  ├─ memory/        # 短期/长期记忆
│  │  │  └─ analytics/     # 运营看板
│  │  ├─ orchestrator/ # Agent 图
│  │  ├─ capabilities/ # LLM/ASR/TTS/Search/Embed Adapter
│  │  ├─ infra/        # DB/Redis/OSS/迁移
│  │  └─ workers/      # 后台任务
│  ├─ tests/
│  └─ pyproject.toml
├─ docs/
│  └─ superpowers/specs/
└─ deploy/             # docker-compose / Dockerfile / nginx.conf
```

前端使用 pnpm workspace monorepo；两 SPA 共享 `ui-shared` 包。

---

## 3. 后端模块设计

### 3.1 API Layer

**REST 路由**（前缀 `/api/v1`）按领域分组：

| 路由组 | 用途 |
|---|---|
| `/auth` | 登录、登出、刷新 token、注册 |
| `/users` | 用户资料、偏好设置 |
| `/personas` | 角色卡 CRUD（含示例对话、描述） |
| `/conversations` | 会话列表、单会话历史、导出 jsonl、满意度反馈 |
| `/knowledge` | 文档上传、列表、删除、重新向量化、检索预览 |
| `/live2d-models` | 模型上传（zip/文件夹）、列表、删除 |
| `/backgrounds` | 背景图/视频上传、列表 |
| `/admin/analytics` | 运营看板数据（服务人次、TOP5、词云、情感、满意度趋势） |
| `/admin/settings` | 系统级设置（启用的 LLM/ASR/TTS provider、API key） |

**WebSocket**：`/ws/chat`，鉴权后建立长连，承载所有实时双向消息。

**WS 消息协议**（统一信封）：

```json
{
  "type": "user.text | user.audio.chunk | user.audio.end | agent.thinking | agent.text.delta | agent.text.done | agent.audio.chunk | agent.audio.done | agent.action | agent.error | ping | pong",
  "session_id": "uuid",
  "msg_id": "uuid",
  "payload": {},
  "ts": 1716700000
}
```

文本和动作标记**分开消息**下发，前端无需边渲染边解析字符串。

### 3.2 Domain Services

每个领域包组织为 `models / repository / service / schemas` 四件套：

- **identity**：JWT 签发、刷新、密码哈希（passlib bcrypt）；角色 visitor/admin/superadmin。
- **persona**：角色卡（参考 SillyTavern 字段：`name` / `description` / `personality` / `scenario` / `first_mes` / `mes_examples`）；用户可设当前激活角色卡；至少保留一张默认 Eira 卡不可删。
- **conversation**：会话与消息持久化、jsonl 导出、满意度（👍/👎）写入。
- **knowledge**：文档实体 + 分块实体；元数据（来源、页码、章节）随分块存储，用于答案溯源。
- **memory**：短期上下文（Redis）+ 长期记忆（关键事实抽取后入 pgvector）。
- **analytics**：聚合任务每日/每小时跑批，结果存 `analytics_*` 表，看板直查。

### 3.3 AI Orchestrator（图编排）

LangGraph（或等价实现）的状态图。一次用户消息从入图到出图的节点流：

```
入口
  │
  ▼
[1 输入预处理]    文本：直通；语音：调用 ASR Adapter → 文本
  │
  ▼
[2 短期记忆加载]  Redis 拉 N 轮上下文
  │
  ▼
[3 情感识别 占位] MVP 阶段返回 neutral，预留接入点
  │
  ▼
[4 路由决策]      LLM 判定：闲聊 / 知识库问答 / 推荐路线 / 拒答
  │
  ├─→ [5a RAG 检索]  pgvector top-k → rerank → 拼 prompt
  │       │
  │       └─ 命中阈值不足 → [5b 互联网检索] Tavily/Bocha
  │
  ▼
[6 长期记忆检索]  用户画像 + 相关历史事实
  │
  ▼
[7 LLM 生成]      流式输出，Provider Adapter 选模型
  │
  ▼
[8 动作标记抽取]  从输出文本中正则提取 [wave]/[happy] 等
  │
  ▼
[9 TTS 合成]      流式输出，与文本分通道下发
  │
  ▼
[10 记忆写回]     本轮入短期；满足条件抽取关键事实写入长期
  │
  ▼
[11 埋点]         写入 analytics_event
出口
```

节点可插拔：第 3、5b、6 节点 MVP 可降级（直通），后期接入真实实现不影响其他节点。

状态对象 `ChatState { session_id, user_input, history, retrieved_chunks, persona, sentiment, llm_response, action_tags, ... }` 贯穿整个图。

### 3.4 Capability Adapters

所有外部 AI 能力套抽象层。

```python
class LLMProvider(Protocol):
    async def chat_stream(messages, *, model, **opts) -> AsyncIterator[str]: ...

class ASRProvider(Protocol):
    async def transcribe(audio_bytes, *, language) -> str: ...
    async def transcribe_stream(audio_iter) -> AsyncIterator[str]: ...

class TTSProvider(Protocol):
    async def synthesize_stream(text, *, voice) -> AsyncIterator[bytes]: ...

class EmbeddingProvider(Protocol):
    async def embed(texts: list[str]) -> list[list[float]]: ...

class WebSearchProvider(Protocol):
    async def search(query, *, top_k) -> list[SearchResult]: ...
```

实现选型（MVP 默认，可在 admin/settings 切换）：

- **LLM**：DeepSeek 或通义千问；备选 OpenAI 兼容协议。
- **ASR**：阿里云 NLS 或讯飞流式 ASR。
- **TTS**：阿里云 TTS / Azure TTS。
- **Embedding**：通义 `text-embedding-v3` 或 BGE-M3。
- **Web Search**：Bocha（中文优）或 Tavily。

### 3.5 Knowledge Pipeline

```
管理员上传文档 → OSS 持久化原件 → 写 documents 表（status=pending）
        │
        │  管理员点击「向量化」按钮
        ▼
   [文档解析]   docx/pdf/xlsx/md/txt → 纯文本 + 结构化元数据（页码/章节）
        │
        ▼
   [智能分块]   按章节 + 滑动窗口（默认 chunk=500, overlap=80）
        │
        ▼
   [Embedding]  批量调云 API，并发限速
        │
        ▼
   [写入 pgvector]  knowledge_chunks(doc_id, chunk_idx, text, embedding, meta)
        │
        ▼
   documents.status = indexed
```

**重新向量化**：管理员可针对单文档或全库触发；同一流水线，先 `DELETE FROM knowledge_chunks WHERE doc_id=?` 再重跑。

**异步执行**：FastAPI BackgroundTasks 起协程；进度写 Redis（key `vec_job:<doc_id>`）；管理后台轮询。

### 3.6 Background Workers

MVP 阶段不引入 Celery/RQ，使用 APScheduler + asyncio：

- 知识库向量化任务（用户触发）
- 运营数据每日聚合（凌晨）
- 长期记忆抽取（会话结束触发）
- 临时文件清理

后期负载上来再独立成 worker 进程。

---

## 4. 数据层设计

### 4.1 PostgreSQL 库表

按领域包分组，命名 snake_case，所有表带 `id (uuid) / created_at / updated_at`。

**身份与租户**

```
tenants            (id, name, ...)
users              (id, tenant_id, email, password_hash, role, display_name, prefs jsonb)
auth_sessions      (id, user_id, refresh_token_hash, expires_at, ua, ip)
```

**角色卡**

```
personas           (id, tenant_id, name, description, personality, scenario,
                    first_mes, mes_examples jsonb, voice_id, live2d_model_id,
                    is_default bool, is_official bool, created_by)
user_active_persona(user_id, persona_id)
```

**会话与消息**

```
conversations      (id, user_id, persona_id, title, started_at, ended_at, msg_count)
messages           (id, conversation_id, role, content text, audio_oss_key,
                    action_tags jsonb, latency_ms, model_used, source jsonb,
                    feedback smallint)         -- 1=👍 -1=👎 0=未评
                   -- audio_oss_key 仅指 assistant TTS 回复音频；
                   -- 用户语音默认不持久化
```

**知识库**

```
documents          (id, tenant_id, name, oss_key, mime, size, source enum,
                    status enum, chunk_count, indexed_at, indexed_by)
knowledge_chunks   (id, doc_id, chunk_idx, content text, meta jsonb,
                    embedding vector(1024))
                   INDEX hnsw (embedding vector_cosine_ops)
vec_jobs           (id, scope enum, target_id, status, progress, error,
                    started_at, finished_at)
```

**记忆**

```
memory_facts       (id, user_id, tenant_id, content, embedding vector(1024),
                    source_msg_id, importance, expires_at, meta jsonb)
                   INDEX hnsw (embedding)
```
（短期上下文存 Redis，不入库）

**资产**

```
live2d_models      (id, tenant_id, name, oss_key_prefix, manifest jsonb,
                    thumbnail_oss_key, uploaded_by, is_default)
backgrounds        (id, tenant_id, name, kind enum<image|video>, oss_key,
                    fit enum<cover|contain|center|stretch|free>, uploaded_by)
```

**运营分析**

```
analytics_events   (id, ts, tenant_id, user_id, event_type, payload jsonb)
                   PARTITION BY RANGE(ts)
analytics_daily    (date, tenant_id, served_users, qa_count,
                    avg_latency_ms, satisfaction_pos, satisfaction_neg,
                    keyword_cloud jsonb, sentiment_dist jsonb)
```

**系统设置**

```
system_settings    (key, value jsonb, updated_by, updated_at)
```

### 4.2 Redis 用途

| key 模式 | 用途 | TTL |
|---|---|---|
| `session:<sid>:ctx` | 短期上下文（最近 N 轮 list） | 24h |
| `vec_job:<doc_id>` | 向量化任务进度 | 1h |
| `rate:<user>:<api>` | 速率限制（令牌桶） | 滚动 |
| `ws:user:<uid>` | 在线 WS 连接映射（多副本场景） | 心跳更新 |
| `cache:rag:<hash>` | RAG 检索结果短缓存 | 5min |

### 4.3 OSS 对象存储

```
/documents/<tenant>/<doc_id>/<原文件名>
/live2d/<tenant>/<model_id>/...                # 解压后保留 Cubism 目录结构
/backgrounds/<tenant>/<bg_id>/...
/audio/messages/<conversation_id>/<msg_id>.mp3 # 历史音频可选保留
/avatars/<user_id>.jpg
```

前端访问统一通过签名 URL（短期有效）。

### 4.4 数据迁移

- **Alembic** 管理 schema；每个领域包贡献迁移脚本。
- **种子数据**：默认 Eira 角色卡 + 示范景区知识包 + 一套官方 Live2D 模型，初始化脚本一键灌入。

### 4.5 备份与隐私

- PG 每日逻辑备份（`pg_dump`）+ WAL 持续归档。
- 用户音频默认**不持久化**；用户可在设置中开启"保留语音"。
- API key、密码：`pgcrypto` 字段级加密 + 应用层 KMS 包装。
- 数据导出：用户可导出本人会话为 jsonl（DESIGN.txt:399）。

---

## 5. 前端设计

### 5.1 Monorepo 与共享

```
apps/
├─ web-user/   # 用户端：Live2D 沉浸交互
└─ web-admin/  # 管理后台：SaaS 仪表盘
packages/
└─ ui-shared/  # 玻璃拟态组件 + 主题 token + 工具
```

**共用**：玻璃拟态原子组件（`GlassCard` / `GlassButton` / `GlassInput` / `GlassModal`）、主题 CSS 变量、HTTP 客户端、WS 客户端、鉴权 store、错误处理。

**不共用**：业务页面、路由、状态结构。

### 5.2 用户端（web-user）

| 用途 | 选型 |
|---|---|
| 框架 | Vue 3 + `<script setup>` + TypeScript |
| 状态 | Pinia |
| 路由 | Vue Router |
| 请求 | Axios + 拦截器（鉴权 + 错误） |
| WS | 自封装 `useWebSocket`，自动重连 + 心跳 + 消息分发 |
| Live2D | `pixi-live2d-display` + Cubism 4 SDK Web |
| 语音录制 | MediaRecorder + AudioWorklet（流式分片上传） |
| 摄像头 | `getUserMedia`，仅小窗预览 |
| 动画 | `@vueuse/motion` |

**路由**

```
/login                登录
/                     主交互页（登录后默认）
/settings             设置（弹层）
```

**主交互页布局**（对应 DESIGN.txt 53-176）：

```
┌─────────────────────────────────────────────────┐
│ ⚙                                                                           [前置摄像头小窗]  │
│                                                                                                         │
│              ┌──────────────────┐                                                │
│              │     Live2D                        │                                               │
│              │     全屏画布                     │                                                │
│              │   (位移+缩放)                   │                                                │
│              └──────────────────┘                                                │
│         「你好啊，我是你今天的导游」                                                    │
│  ┌──────┐                                                                                      │
│  │ 快捷1    │                                                                                      │
│  │ 快捷2    │                                                                                      │
│  │ 快捷3    │                                                                                      │
│  └──────┘                                                                                      │
│ ┌──────────────────────────────────────────┐          │
│ │ 🎤   输入您的问题...                                                  +   ✈  │          │
│ └──────────────────────────────────────────┘          │
└─────────────────────────────────────────────────┘
```

输入框三按钮均位于输入框**内部**：麦克风极简图标**左对齐**（左侧），加号与发送圆按钮**右对齐**（右侧）。三按钮等大、玻璃反射 + 柔和阴影。详见 DESIGN.txt:141-156。

**布局层级（z-index 从低到高）**

```
┌───────────────────────────────────────────────┐
│ 0  背景层      纯色 / 图片 / 视频（OSS）      │  全屏
├───────────────────────────────────────────────┤
│ 1  Live2D 画布 PixiJS Application（全屏）     │  全屏
│        └─ 角色 Sprite（可拖动 + 可缩放）      │
├───────────────────────────────────────────────┤
│ 2  UI 覆盖层   设置按钮、摄像头小窗、气泡、   │  浮于其上
│                快捷问题、输入框               │
└───────────────────────────────────────────────┘
```

**MVP 必须支持的画布交互**

| 操作 | 桌面端 | 移动端 |
|---|---|---|
| 位移 | 鼠标按住角色拖动 | 单指拖动 |
| 缩放 | 滚轮 / `Ctrl + 滚轮` | 双指捏合 |
| 重置 | 双击角色 | 双击角色 |

实现要点：

- PixiJS Application 监听 resize，画布跟随全屏。
- 角色容器 `eventMode = 'static'`，监听 `pointerdown / move / up`；缩放走 `wheel`。
- 缩放限制 `0.3x ~ 3x`；位移限制至少保留 20% 角色 bounds 在视口内。
- 位置 `(x, y)` 与缩放 `scale` 写 localStorage，按角色卡 ID 维度独立保存。
- UI 覆盖层默认 `pointer-events: none`，仅按钮/输入框等具体元素 `pointer-events: auto`。
- 设置面板提供"恢复角色默认位置"按钮。

**核心 composable**

- `useChatSession`：会话生命周期、消息发送、WS 状态。
- `useLive2DController`：模型加载、动作播放、参数设置、口型同步、待机动画；含 `dragController` / `zoomController` / `transformPersistence`。
- `useActionParser`：解析 `[wave]` `[happy]` 等标记 → 派发到 Live2D。
- `useVoiceRecorder`：录音分片、VAD、上传。
- `useTTSPlayer`：流式音频播放 + 与 Live2D LipSync 联动。

**Live2D 控制要点**

- 待机动画（眨眼、呼吸、转头）由前端定时器随机派发。
- 收到文本流 → 播"思考"动作；收到 TTS 音频流 → 切到"说话+口型同步"。
- 收到 `[wave]` 等标记时，根据当前播放优先级排队执行。

**响应式**：`useBreakpoints`（vueuse）区分桌面/移动横屏/移动竖屏。

### 5.3 管理后台（web-admin）

| 用途 | 选型 |
|---|---|
| 框架 | Vue 3 + TS |
| 组件库 | Naive UI |
| 图表 | ECharts（折线、环形、词云、面积） |
| 表格 | Naive UI DataTable + 服务端分页 |
| 上传 | 自封装大文件分片 |

**页面骨架**（对应 DESIGN.txt 187-360 三栏式）

```
顶部导航：数据概览 / 交互管理 / 内容管理 / 系统设置
─────────────────────────────────────────────
左侧 26%      │  中间 38%        │  右侧 36%
形象切换      │  Live2D 大型展示 │  运营数据卡片
形象配置      │  操作浮条        │  TOP5 / 折线
（外观/服装/  │  （形象预览/动作/│  情感环形 / 词云
  声音 Tab）  │   语音测试/更多）│  服务建议
```

**主要路由**

```
/admin/login                   登录
/admin/dashboard               数据概览（默认）
/admin/interaction             交互管理（会话审计、满意度）
/admin/content/personas        角色卡管理
/admin/content/knowledge       知识库管理
/admin/content/live2d          Live2D 模型库
/admin/content/backgrounds     背景库
/admin/system                  系统设置（Provider、API key）
```

**关键交互**

- 知识库列表：`status` 列展示「待向量化 / 向量化中 X% / 已索引 / 失败」；操作列「向量化 / 重新向量化 / 删除 / 检索预览」。
- 检索预览：管理员输入 query，看 RAG 召回的 chunk 列表。
- 角色卡编辑器：表单字段对齐 SillyTavern；支持 `{{user}}` `{{char}}` 占位符并实时预览。
- Live2D 上传：接受 zip 或文件夹；后端解压后校验 `model3.json` 存在。
- 仪表盘数据：直查 `analytics_daily`，切换日/周/月仅改聚合粒度。

### 5.4 主题与设计令牌

`packages/ui-shared/tokens.css` 定义 CSS 变量，两端共用：

```css
:root {
  --glass-bg: rgba(255,255,255,0.55);
  --glass-border: rgba(255,255,255,0.35);
  --glass-blur: 24px;
  --radius-card: 24px;
  --radius-pill: 9999px;
  --shadow-soft: 0 8px 32px rgba(0,40,90,0.08);
  --color-accent: #6aa2ff;
  --color-text-primary: #1d2433;
  --ease-soft: cubic-bezier(.4,.0,.2,1);
}
```

用户端默认深背景模式，后台默认浅背景模式，差异通过 `[data-theme]` 切换。

### 5.5 错误与离线兜底

| 场景 | 兜底 |
|---|---|
| WS 断线 | 指数退避重连，UI 顶部不打扰提示 |
| TTS 失败 | 降级为纯文本展示 |
| ASR 失败 | 提示用户改用文字 |
| Live2D 加载失败 | 回退到静态二次元立绘 + 文字交互 |
| 网络慢 | 思考占位（"嗯..."气泡 + 待机动作）；满 5s 给出"还在思考"提示 |

---

## 6. 关键时序

### 6.1 语音问答端到端

```
用户                前端                  后端 (FastAPI)              外部服务
 │                    │                       │                         │
 │ 按住麦克风         │                       │                         │
 │───────────────────▶│ MediaRecorder 录音    │                         │
 │                    │ AudioWorklet 分片     │                         │
 │                    │                       │                         │
 │                    │  WS user.audio.chunk  │                         │
 │                    │──────────────────────▶│                         │
 │                    │  (持续分片上行)       │  流式转发               │
 │                    │                       │ ───────────────────────▶│ ASR 流式 API
 │                    │                       │ ◀── 文本片段 ───────────│
 │                    │                       │                         │
 │ 松开麦克风         │                       │                         │
 │───────────────────▶│ user.audio.end        │                         │
 │                    │──────────────────────▶│                         │
 │                    │                       │ ASR 终态文本            │
 │                    │                       │                         │
 │                    │                       │ ──▶ Orchestrator 入图   │
 │                    │  agent.thinking       │     [短期记忆/路由]     │
 │                    │ ◀─────────────────────│                         │
 │                    │                       │ ──▶ pgvector 检索       │
 │                    │                       │     (RAG 命中阈值<? →  │
 │                    │                       │      Web Search)        │
 │                    │                       │                         │
 │                    │                       │ ──▶ LLM 流式生成        │
 │                    │                       │ ───────────────────────▶│ LLM API
 │                    │                       │ ◀── token 流 ───────────│
 │                    │  agent.text.delta×N   │                         │
 │                    │ ◀─────────────────────│ (边收边转发，去除标记)  │
 │                    │  agent.action         │                         │
 │                    │ ◀─────────────────────│ (抽到 [happy] 立即下发) │
 │                    │                       │                         │
 │                    │                       │ ──▶ TTS 流式            │
 │                    │                       │ ───────────────────────▶│ TTS API
 │                    │                       │ ◀── 音频帧 ─────────────│
 │                    │  agent.audio.chunk×N  │                         │
 │                    │ ◀─────────────────────│                         │
 │                    │  agent.text.done      │                         │
 │                    │  agent.audio.done     │                         │
 │ 看角色挥手         │                       │ ──▶ 写消息/埋点         │
 │ 听到回答           │ Live2D 口型同步       │ ──▶ 异步抽长期记忆      │
 │                    │ TTS 播放器播放        │                         │
```

**延迟预算（目标 < 5s）**

| 阶段 | 预算 |
|---|---|
| ASR 首字返回 | < 600ms |
| Orchestrator 入图到首 token | < 1.2s（含 RAG） |
| LLM 首 token → 首音频帧 | < 800ms |
| 网络往返与播放启动 | < 400ms |
| **总首响延迟** | **< 3s** |

### 6.2 文本问答时序

复用语音路径中后段，去掉 ASR、TTS 改可选（语音播放开关在前端设置中）。

### 6.3 知识库向量化时序

```
管理员             前端              后端                          OSS / DB
  │                  │                 │                            │
  │ 选文件上传        │                 │                            │
  │────────────────▶│ POST /knowledge │                            │
  │                  │ ───────────────▶│ 接收文件                   │
  │                  │                 │ ──── 上传到 OSS ─────────▶│
  │                  │                 │ INSERT documents          │
  │                  │                 │   status=pending           │
  │                  │ ◀── doc_id ─────│                            │
  │ 看到文档列表      │                 │                            │
  │ 点「向量化」      │                 │                            │
  │────────────────▶│ POST .../index  │                            │
  │                  │ ───────────────▶│ 创建 vec_job              │
  │                  │ ◀── job_id ─────│ status=running, prog=0    │
  │                  │                 │                            │
  │                  │                 │ ──▶ 后台协程               │
  │                  │                 │     [解析]                 │
  │                  │                 │     [分块]                 │
  │                  │                 │     [Embedding 批]         │
  │                  │                 │     [写 pgvector]          │
  │                  │                 │     每批写 progress→Redis  │
  │                  │                 │                            │
  │                  │ 轮询 progress    │                            │
  │                  │ ──── GET ──────▶│ 读 Redis vec_job:<id>     │
  │                  │ ◀── 30/50/... ──│                            │
  │                  │                 │ 完成: documents.status     │
  │                  │                 │       = indexed            │
  │                  │ ◀── done ───────│                            │
  │ UI 状态变绿       │                 │                            │
```

失败处理：任何步骤异常 → vec_job 写入 error，documents 回滚至 `failed` 状态，前端列表显示红色 + 错误详情，可重试。

### 6.4 长期记忆抽取（异步）

```
会话进行中
  │
  └─▶ 每 N 轮 OR 会话结束触发
        │
        ▼
   后台协程：
   1. 取本段对话 → LLM 抽取候选事实（json schema）
   2. 去重（向量相似度 > 阈值的合并/丢弃）
   3. Embedding → 写入 memory_facts
   4. 重要度衰减（importance × decay）
```

召回时机：每次新对话入图时（节点 6），按 `user_id` + 当前 query 向量做 top-k 召回，拼入 prompt 的 system 段。

### 6.5 实时通信容错

| 场景 | 处理 |
|---|---|
| WS 断线 | 客户端 1s/2s/4s/8s 退避重连，sequence 号断点续接 |
| LLM 超时 | Orchestrator 节点 30s 超时，前端收到 `agent.error` 后展示重试按钮 |
| TTS 失败 | 降级为仅文本 + 默认动作 |
| ASR 部分失败 | 已识别文本可见但提示"识别可能不完整，可手动修改后发送" |
| RAG 命中阈值不足 | 自动转 Web Search；若也失败，降级为通用 LLM 回答 + 标注"基于通用知识" |

---

## 7. 横切关注点

### 7.1 鉴权与权限

- **JWT 双 token**：access（15min）+ refresh（7d，存 `auth_sessions` 表，可吊销）。
- **WebSocket 鉴权**：建连时 query 参数带 access token，握手阶段校验，失败直接 close。
- **角色三档**：`visitor` / `admin` / `superadmin`。
- **依赖注入**：FastAPI `Depends(get_current_user)` + `Depends(require_role("admin"))` 保护路由。
- **租户隔离**：所有领域查询带 `tenant_id` 过滤；MVP 单租户但字段必须先有。

### 7.2 配置管理

- **环境变量**：`pydantic-settings`，分层 `BaseSettings` → `DatabaseSettings` / `LLMSettings` / `OssSettings`。
- **运行时配置**：`system_settings` 表存可热改的项，管理后台修改后立即生效。
- **API key 加密**：写入前 KMS 包装；不出现在日志、错误、响应中。

### 7.3 日志与可观测

| 维度 | 工具 | 用途 |
|---|---|---|
| 应用日志 | `structlog` JSON 格式 | 行为追踪、错误诊断 |
| 链路追踪 | OpenTelemetry（可选） | 跨节点延迟分析 |
| 指标 | Prometheus client | QPS、延迟、错误率、外部 API 成功率 |
| 错误上报 | Sentry（可选） | 异常聚合 |

埋点：每个 Orchestrator 节点的入参摘要、耗时、是否降级；每次 LLM/ASR/TTS 调用的 provider、model、tokens、cost、latency。

### 7.4 限流与配额

- **Redis 令牌桶**：按 `user_id + endpoint` 维度。
- **WS 消息限流**：单连接每秒最多 10 条 user.* 消息。
- **管理后台**：写操作（上传、删除、向量化）单独限流。
- **外部 API 配额**：LLM/TTS 等 provider 维度日配额上限，到上限自动切备用 provider 或降级。

### 7.5 安全

- **密码**：bcrypt cost=12，注册时校验强度。
- **CSRF**：API 走 Bearer token 模式天然规避；管理后台敏感操作要求二次确认。
- **CORS**：白名单前端域名。
- **上传校验**：文件类型白名单 + magic number 校验 + 大小上限（文档 50MB / Live2D 200MB / 视频背景 100MB）。
- **SQL 注入**：全程 SQLAlchemy ORM，禁用裸 SQL 拼接。
- **Prompt 注入防御**：用户输入用统一分隔符标记后塞进 system prompt 模板；知识库 chunk 用 `<context>...</context>` 包裹。
- **OSS 直链**：所有访问走签名 URL，TTL 短。

### 7.6 测试策略

| 层级 | 工具 | 范围 |
|---|---|---|
| 单元 | `pytest` + `pytest-asyncio` | 领域服务、capability adapter（mock 外部） |
| 集成 | `pytest` + 真 PG/Redis（docker-compose） | 知识库流水线、Orchestrator 图 |
| 契约 | OpenAPI schema 校验 | REST 接口 + WS 消息 schema |
| 前端 | Vitest + Vue Test Utils | composable 与组件 |
| E2E | Playwright | 登录、文本问答、上传知识、向量化 |

外部 AI 服务：默认走录制回放（`pytest-vcr` 或自建 fixture），CI 不消耗真 API key。

### 7.7 部署与环境

- **容器化**：后端、前端各一个 Dockerfile，`docker-compose.yml` 起 PG/Redis/Nginx/backend/web-user/web-admin。
- **三套环境**：`dev`（本地）/ `staging`（云上联调）/ `prod`（云上）。
- **Nginx 路由**：
  - `/api` → FastAPI
  - `/ws` → FastAPI（升级 WSS，长超时）
  - `/` → web-user 静态资源
  - `/admin` → web-admin 静态资源
- **PG/Redis**：MVP 用云厂商托管实例。
- **OSS**：阿里云 OSS / 腾讯云 COS / MinIO（自托管备选）。
- **CI/CD**：Git push → 单元测试 → 构建镜像 → 推仓库 → 服务器拉取重启。

### 7.8 性能与扩展路径

| 信号 | 应对动作 |
|---|---|
| LLM 调用排队 | 增并发限制下游 → 加备用 provider → 模型分级 |
| WS 连接数 > 单进程承载 | 上 nginx 多副本 + Redis pub/sub 转发 |
| pgvector 检索慢 | 调 HNSW 参数 → 单独迁 Milvus |
| 文档解析阻塞 | workers 拆独立进程 + 任务队列（Arq / RQ） |
| 看板查询慢 | 物化视图或 ClickHouse 接管分析侧 |

---

## 8. 实施分期

按"先打通主链路，再加广度"组织。

**Phase 0 · 基础设施**

- Monorepo 骨架 / Docker 化 / CI
- PG + pgvector + Redis + OSS 接入
- 鉴权骨架（JWT + 用户 CRUD）
- 共享 UI 包初版（玻璃拟态原子组件 + 主题 token）

**Phase 1 · 文本问答闭环**

- LLM Provider 抽象 + 默认实现
- Orchestrator 图最小骨架（路由→LLM→输出）
- WebSocket 协议 + 前端会话页
- Live2D 画布（全屏 + 位移 + 缩放）+ 默认模型加载
- 动作标记解析与播放
- 会话与消息持久化

**Phase 2 · 知识库与 RAG**

- 文档上传 + OSS 存储 + 文档列表
- 知识库流水线（解析→分块→Embedding→pgvector）
- 手动向量化 + 重新向量化按钮 + 进度
- RAG 节点接入 Orchestrator + 来源标注
- Web Search Provider 接入

**Phase 3 · 语音与多模态外壳**

- ASR 流式 + TTS 流式接入
- 前端语音录制 + 流式播放 + 口型同步
- 摄像头小窗（仅本地预览）
- 快捷问题、背景上传、Live2D 模型上传/切换、设置面板

**Phase 4 · 管理后台 + 角色卡**

- 后台三栏布局 + 顶部导航
- 角色卡 CRUD（SillyTavern 字段）+ 默认 Eira 不可删
- 知识库管理界面 + 检索预览
- Live2D / 背景资源管理界面
- 系统设置（Provider 选型、API key）

**Phase 5 · 运营看板**

- analytics_event 埋点
- 每日聚合任务
- 看板模块（运营概览 / TOP5 / 满意度趋势 / 交互记录 / 词云 / 情感环形 / 服务建议）

**Phase 6 · 长期记忆与情感**

- 长期记忆抽取 + 召回
- 情感识别节点接入（文本基线）

**Phase 7+ · 后续迭代**

- 主动问候 / 打断插话 / 多模态图像识别 / 多租户 / AR 多形态

---

## 9. 后续 Spec 拆分清单

每个子 spec 独立走 brainstorming → spec → writing-plans → 实现。本顶层架构是它们共同的地基。

**基础设施层**

1. `infra-bootstrap`：仓库脚手架与本地开发环境
2. `auth-and-user`：鉴权与用户管理

**核心交互层**

3. `chat-pipeline-text`：文本问答主链路（含 Orchestrator 框架）
4. `live2d-canvas`：全屏画布、位移缩放、动作标记
5. `voice-streaming`：ASR/TTS 流式与口型同步

**知识与记忆层**

6. `knowledge-base-pipeline`：文档解析、分块、向量化、管理 UI
7. `rag-and-web-search`：RAG 召回、来源标注、互联网兜底
8. `long-term-memory`：长期记忆抽取与召回

**资产与外壳层**

9. `persona-cards`：角色卡 CRUD 与激活
10. `live2d-model-management`：模型上传、解压、校验
11. `background-and-settings`：背景资源、用户端设置面板

**管理与运营层**

12. `admin-shell`：后台布局、导航、权限页面
13. `analytics-pipeline`：事件埋点 + 聚合任务 + 看板查询接口
14. `dashboard-ui`：后台仪表盘各模块 UI

**横切层**

15. `observability`：日志、指标、追踪接入
16. `provider-abstractions`：LLM/ASR/TTS/Embedding/Search 适配层与切换

---

## 10. 锁定 / 推迟决策清单

### 10.1 已锁定（后续 spec 必须遵守）

- 后端单技术栈 Python 3.11+ / FastAPI；前端 Vue 3 + TS。
- 双 SPA + 共享 UI 包；后端单体 + 模块化领域包。
- PG + pgvector + Redis + OSS；不再引入额外存储。
- 实时通信走 WebSocket；流式输出统一在 WS。
- 所有外部 AI 能力必须通过 Capability Adapter（不允许业务代码直连 SDK）。
- 所有领域查询必须带 `tenant_id`。
- 任何长任务（解析、向量化、聚合）必须异步、必须可观测进度。
- API key 不进日志、不进响应、不进前端。

### 10.2 刻意推迟

- 是否拆 worker 进程（Phase 1 用同进程协程）。
- Embedding 模型最终选型（Phase 2 时跑评测对比再定）。
- 长期记忆的具体提取 schema 与衰减策略（Phase 6）。
- 多租户路由策略（subdomain / path / header）。
- 是否引入 Celery（Phase 7+ 后视负载）。
