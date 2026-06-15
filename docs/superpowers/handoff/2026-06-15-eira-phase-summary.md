# Eira 项目阶段性总结 · 2026-06-15

> **日期**: 2026-06-15
> **分支**: master
> **本文档**: 替代 2026-06-09 版，覆盖 6/9 → 6/15 全部工作。**唯一权威入口。**

---

## 目录

1. [总览](#1-总览)
2. [6/9 → 6/15 工作链](#2-69--615-工作链)
3. [架构决策更新](#3-架构决策更新)
4. [Live2D 方案 D 与标识体系](#4-live2d-方案-d-与标识体系)
5. [API 端点全表](#5-api-端点全表)
6. [数据库迁移链](#6-数据库迁移链)
7. [测试覆盖](#7-测试覆盖)
8. [已知问题](#8-已知问题)
9. [服务启动](#9-服务启动)
10. [给新 agent 的告诫](#10-给新-agent-的告诫)
11. [归档索引](#11-归档索引)

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
| Live2D | Cubism SDK for Web 5 Framework（自管 WebGL，**方案 D：OSS zip → boto3 直读 → JSZip → fetch 拦截器**） |
| 实时通信 | WebSocket 全双工（`/ws/chat` + `/ws/voice`） |
| 鉴权 | JWT 双 token (access 15min + refresh 7d)，角色 visitor/admin |
| 测试 | pytest + httpx + structlog；~260 tests |
| 语音 | 讯飞 ASR（HMAC-SHA256 + WebSocket IAT）+ 讯飞 TTS + WebM→PCM 转码 |

### 文件结构

```
Eira/
├─ apps/
│  ├─ shared/live2d/      # 🆕 共享 Live2D 加载模块 (live2dLoader.ts)
│  ├─ web-user/           # 用户端 SPA（Chat.vue 自包含）
│  └─ web-admin/          # 管理后台 SPA（Dashboard.vue 内嵌全部功能）
├─ packages/ui-shared/    # Stub 共享包
├─ backend/
│  ├─ app/
│  │  ├─ api/rest/        # REST 路由模块
│  │  ├─ api/ws/          # /ws/chat + /ws/voice
│  │  ├─ capabilities/    # LLM / ASR / TTS / Embedding / Search Provider + effective_settings
│  │  ├─ core/            # 配置 / 安全 / 限流 / 文件校验 / error_schema / 审计中间件
│  │  ├─ domain/          # identity / conversation / knowledge / persona / system
│  │  ├─ infra/           # DB / Redis / OSS (含 get_object_bytes) / Alembic (0012 head)
│  │  ├─ orchestrator/    # LangGraph 图 + 8 节点 + 句切引擎 + RAG 自实例化
│  │  └─ workers/         # 知识库异步管线（tenacity 重试）
│  ├─ scripts/
│  │  ├─ run_clean.sh     # 🆕 干净启动脚本（杀端口树 + 清 pycache + 无 reload）
│  │  └─ seed_models.py   # 🆕 一次性上传 7 个模型到 OSS
│  └─ tests/
│     ├─ conftest.py      # session-scoped _cleanup_test_data
│     ├─ infra/           # DB/Redis/OSS/health/config/logging/system (7)
│     ├─ identity/        # auth/admin_users/admin_settings/audit (4)
│     ├─ persona/         # personas/silly_import/assets/admin_assets (4)
│     ├─ conversation/    # conversation/ws_chat/ws_messages/safety/orchestrator_smoke (5)
│     ├─ knowledge/       # documents_api/knowledge_*/chunker/parsers/retrieve_kb/embedding/search (10)
│     ├─ voice/           # asr/tts/voice/ws_voice/ws_voice_e2e/ws_stream_pacing/sentence_splitter (7)
│     └─ llm/             # llm_provider/llm_logging (2)
├─ deploy/                # docker-compose + Nginx
└─ docs/superpowers/
   ├─ specs/              # 架构设计 spec + Live2D 修复设计
   ├─ plans/              # 实施计划（当前版 + archive/ 原始版）
   ├─ handoff/            # 本文档 + eira-handoff-2026-06-15-live2d-resolved.md + archive/
   └─ validations/        # 验证门数据（17 门，6 个待人工闭合）
```

---

## 2. 6/9 → 6/15 工作链

### 2.1 时间线

| 日期 | 工作 | 关键成果 |
|------|------|---------|
| **6/9** | Phase 0-4 总结 | 15 个历史 handoff 归档，253 tests 基线 |
| **6/10** | P0-P2 修复 (12 项) | 数据库运维、会话上下文重建、背景/模型持久化、认证防护、诊断日志、文档上传、模型源切换、Live2D 动作扩展；260 tests |
| **6/10** | 持续测试 + 验证门 | Provider 配置（DeepSeek + 4sapi + 讯飞）、Embedding httpx 修复、RAG 召回评估 MRR=1.0、验证门文档创建 |
| **6/14** | 全量 API 审查 | 18 REST + 5 WS 审计，20 项修复（OSS_BUCKET NameError、persist 真实写入、MIME 标准化、admin 开关全部激活） |
| **6/14** | Voice WS 修复 | code=4000 根因（Provider 初始化在 try 外）、讯飞 ASR 三层修复（协议/解析/音频格式）、WebM→PCM 转码、会话上下文丢失修复 |
| **6/14** | Phase 5-6 部分 | 角色卡 resolver → orchestrator、effective_settings（TTS/ASR/Embedding/Search 读 DB）、RAG 自实例化、Live2D 方案 D 实施、错误格式统一、测试重组 |
| **6/14** | 测试重组 + Bug 修复 | 目录 6 功能模块重组、session-scoped cleanup、6 个 bug（Live2D 路径错位、双重气泡、NaN JSON、hit test 崩溃）、角色卡硬删除、满意度图表优化 |
| **6/15** | Live2D 攻坚战 | 三根因实证定位（P1: active_model_id 污染、P2: schema 缺 oss_key、P3: 残留进程）、7 轮 download 端点尝试、最终 boto3 直读方案定稿、共享模块抽取、纹理 fetch 拦截器修复 |

### 2.2 各 Phase 完成状态

| Phase | 内容 | 后端 | 前端 | 测试 | 验证门 |
|-------|------|:--:|:--:|:--:|:--:|
| **0** | 基础设施：仓库/Docker/CI/PG/Redis/OSS/鉴权骨架 | ✅ | ✅ | ✅ | ✅ |
| **1** | 文本对话：LLM Provider + LangGraph + WS + Live2D | ✅ | ✅ | ✅ | ✅ |
| **2** | 知识库 RAG：文档解析→分块→向量化→pgvector→Web Search | ✅ | ✅ | ✅ | ⚠️ 部分 |
| **3** | 语音多模态：ASR/TTS + /ws/voice + 句切引擎 + 音频泵 | ✅ | ✅ | ✅ | ⚠️ 部分 |
| **4** | 管理后台：用户管理/角色卡 CRUD/系统设置/审计/权限 | ✅ | ✅ | ✅ | ⚠️ 部分 |
| **5** | 运营看板：埋点 + 聚合 + 看板 API | ❌ | ✅ (UI) | — | — |
| **6** | 长期记忆 + 情感识别 | ❌ | ❌ | — | — |
| **7** | 扩展：主动问候/图像识别/多租户/AR | ❌ | ❌ | — | — |

### 2.3 关键偏差（与原始 spec 对比，已确认）

| 维度 | 原计划 | 实际 |
|------|--------|------|
| ui-shared 组件 | 4 个玻璃拟态组件 + CSS tokens | Stub，各页面自行内联 |
| Admin 布局 | 三栏侧边栏 + 菜单 | NConfigProvider 空壳 + 6 按钮导航 (v-show) |
| Admin 图表 | ECharts | 手写 SVG（满意度趋势、词云） |
| Chat.vue | 子组件组合 | 自包含内联 |
| Live2D 渲染 | pixi-live2d-display + Cubism 4 | 官方 Cubism SDK 5 Framework + 自管 WebGL + 方案 D |
| Live2D 存储 | 前端 public/ 目录 | OSS zip → boto3 直读 → JSZip 解压 |
| Dashboard 视图 | 多路由页面 | Dashboard.vue 单体内嵌全部功能 (v-show) |
| 角色卡删除 | 软删除 (disabled=True) | 硬删除 (DELETE FROM) |
| 测试目录 | unit/ + integration/ | 6 功能模块 (infra/identity/persona/conversation/knowledge/voice/llm) |

---

## 3. 架构决策更新

### 3.1 Provider 抽象模式

全部 5 个外部能力统一采用 `ABC → 实现 → Factory` 三层，**全部通过 `get_effective_*_settings()` 支持 DB 配置读取**（不再仅读环境变量）：

| Provider | 抽象基类 | 实现 | 工厂 |
|----------|---------|------|------|
| LLM | `BaseLLMProvider` | OpenAICompat (DeepSeek/OpenAI/Tongyi/Volc) / Mock | `create_llm_provider()` |
| ASR | `BaseASRProvider` | Xunfei (HMAC-SHA256 + WebSocket IAT) / Mock | `create_asr_provider()` |
| TTS | `BaseTTSProvider` | Xunfei (HMAC-SHA256 + WebSocket) / Mock | `create_tts_provider()` |
| Embedding | `BaseEmbeddingProvider` | OpenAICompat via httpx (4sapi.com) / Mock | `create_embedding_provider()` |
| Search | `BaseSearchProvider` | Tavily / Mock（Redis 日预算限频） | `create_search_provider()` |

**LLM Provider 缓存**: `ProviderRegistry` TTL 300s + SHA-256 cache key（含 api_key）+ PATCH settings 即时失效。所有 provider factory 失效逻辑已扩展。

**Embedding 降级**: embedding API 失败时自动 fallback MockEmbeddingProvider，避免 RAG 管线中断。

### 3.2 Orchestrator 图

```
load_context → safety_in → retrieve_kb → (need_web_search? → web_search) → llm_call → safety_out → persist → emit → END
```

- **safety_in**: 2000 字符截断 + 黑名单关键词拒答 → 短路至 emit
- **retrieve_kb**: 自实例化 session + provider（不受 WS 长连接限制），NaN 守卫
- **web_search**: 同上，自实例化
- **llm_call**: System Prompt 从 Persona DB 读取（resolver fallback 链）
- **safety_out**: 密钥模式脱敏（sk-xxx / AKIAxxx / JWT）
- **persist**: 真实 DB 写入（含地理位置消息正则清理）

### 3.3 WS 协议

**`/ws/chat?token=<jwt>`**: 文本对话，帧序列 `state(thinking)→token*→action*→done→state(done)`

**`/ws/voice?token=<jwt>`**: 语音全双工
客户端 → 二进制音频帧 (PCM 16kHz 16bit) + JSON 控制消息 (voice.start/end/barge_in)
服务端 → asr.partial/final + token + action + 二进制 TTS 帧

### 3.4 语音管线

```
MediaRecorder(250ms slices) → AudioProcessor(WebM→PCM 16kHz) → /ws/voice → Xunfei ASR stream → Orchestrator → SentenceSplitter → Xunfei TTS → AudioPump → 前端 Web Audio API + Live2D 口型
```

- **AudioProcessor**: `AudioContext.decodeAudioData()` → 混音单声道 → 重采样 16kHz → Float32→Int16
- **讯飞 ASR**: 全 JSON 帧（encoding=raw → base64）、dwa=wpgs 响应格式（`data.result.ws[].cw[].w`）
- **句切引擎**: `。！？\n` 触发分割 / min_chars=6 / `_ANY_BRACKET_RE` 剥离所有 `[...]` 动作标记
- **AudioPump**: buffer > 3s → sleep 50ms 反压 / cancel+reset 打断
- **前端**: `useVoiceWs` + `useAudioProcessor` (Web Audio API decode + amplitude → 口型)

### 3.5 知识库管线

```
upload → OSS → INSERT documents(pending) → BackgroundTask
  → Parser(MIME→注册表) → Chunker(500/80 token 滑动窗口)
  → Embedding(batch=64, tenacity retry, 失败降级 Mock) → pgvector HNSW
  → status=ready|failed
```

- **重试**: 3 次指数退避 (2s→4s)，区分可重试(OSError/429/5xx)与不可重试(4xx/EmptyText)
- **安全网**: `_ensure_terminal_status()` 兜底

### 3.6 安全加固

| 机制 | 实现 |
|------|------|
| 限流 | Redis Lua 令牌桶：chat(5/s) / upload(2/s) / write(3/s) / WS(10/s) / auth(0.5/s, IP 维度)；二进制音频帧绕过限流 |
| 文件校验 | Magic number 字节匹配（JPEG/PNG/WebP/PDF/ZIP/DOCX），`normalize_mime()` 标准化 |
| JWT/OSS 密钥 | 默认空字符串，staging/prod 无密钥拒绝启动 |
| 审计 | ASGI AuditMiddleware，fire-and-forget 写 audit_log，180 天保留 |
| 错误格式 | `ErrorResponse` pydantic model + 全局 HTTPException handler |
| Logger | 全部 `except` 块加 structlog + print 诊断 |

### 3.7 前端架构决策

- **Admin**: 6 按钮导航 + `v-show` 切换视图（DOM 持久保留，Live2D canvas 不销毁重建）
- **Live2D**: 像素级 alpha 命中门控 + 手势锁定制止误触 + ratio 追踪平移边界
- **认证**: `router.beforeEach` 守卫 + Axios 401 自动 refresh + 并发请求排队
- **数据回退**: API 失败 → mock fallback
- **背景系统**: 用户自定义 > Admin 全局默认 (persona_config) > CSS 蓝色 #0078D7

### 3.8 角色卡系统

- **硬删除**: service 先清理 `chat_session.persona_id` 悬空引用，再 DELETE
- **resolver**: 优先级 `persona.system_prompt` > `personality+scenario+first_mes` 构建 > 硬编码 fallback
- **set_default**: 跨 scope 清除旧默认，`system_prompt` 必填 (min_length=10)
- **import_v2**: 无 system_prompt 时自动生成默认值

---

## 4. Live2D 方案 D 与标识体系

### 4.1 架构全链路

```
MinIO OSS (live2d-models/{model_id}.zip)
  ↓ boto3 get_object_bytes() 直读
Backend /user/model/file?oss_key=  +  /admin/assets/{id}/file
  ↓ HTTP 200 + application/zip
前端 shared/live2d/live2dLoader.ts
  ↓ downloadAndExtract(): fetch → JSZip 解压
  ↓ installFetchInterceptor(): 劫持 window.fetch → 虚拟 URL → Blob
  ↓ textureViaFetch(): PNG 纹理经 fetch 拦截器 → blob URL → Image.src
Cubism SDK for Web 5 Framework
  ↓ 自管 WebGL 渲染
<canvas>
```

### 4.2 共享模块

**`apps/shared/live2d/live2dLoader.ts`** (~285 行纯 TypeScript，零框架依赖)：

- `downloadAndExtract(url, cacheKey, options?)` — zip 下载 + JSZip 解压 + 可选 IndexedDB 缓存
- `createBlobBase(files, model3Path)` — 创建虚拟 URL + 文件名映射
- `installFetchInterceptor()` / `uninstallFetchInterceptor()` — **全局单例**，`virtualBase→files` 注册表支持多模型并存
- `textureViaFetch(url)` — 通过 fetch 拦截器加载纹理 → blob URL → `Image.src`

### 4.3 ⚠️ 标识体系约定（铁律）

任何写入 `active_model_id`（persona_config 或 user_preferences）的地方，值**必须是 OSS key**（`startswith("live2d/")`）。

| 字段 | 标准值 | 谁写 | 谁读 |
|------|--------|------|------|
| `persona_config.active_model_id` | **OSS key** `live2d/.../xxx.zip` | admin Dashboard | user + admin |
| `persona_config.active_model_display_name` | 显示名 `mao_pro_zh` | admin | 仅展示 |
| `user_preferences.active_model_id` | **OSS key** 或 null（走默认） | web-user | user |
| admin `availableModels[].ossKey` | OSS key（asset.oss_key） | — | 持久化 / changeModel |
| admin `availableModels[]._ossKey` | asset.id（数字） | — | 下载端点 |

**脏值黑名单**：`eira-model://` (virtualBase)、显示名、文件夹名。这些值传入 `active_model_id` 会导致 502。

**后端守卫** (`user.py`): fallback 时回退源 `default_model_id` 也校验 `startswith("live2d/")`，非法下发 None。

### 4.4 OSS 模型清单

| Asset ID | 名称 | OSS Key |
|:--------:|------|---------|
| 128 | mao_pro_zh | `live2d/8767b36fcc6c/mao_pro_zh.zip` |
| 129 | hiyori_pro_zh | `live2d/1bd1c6347b0e/hiyori_pro_zh.zip` |
| 130 | akari_vts | `live2d/1672aa665401/akari_vts.rar` |
| 131 | hiyori_vts | `live2d/7c028e0d654d/hiyori_vts.rar` |
| 132 | PinkHair_workshop_2802653785 | `live2d/bdd4212ef2f3/PinkHair_workshop_2802653785.rar` |
| 133 | haru | `live2d/d39eb5b06545/haru.zip` |
| 134 | MaidCyrene | `live2d/6b8ee25433ee/MaidCyrene20251105_....zip` |

当前默认：`mao_pro_zh` (OSS key: `live2d/8767b36fcc6c/mao_pro_zh.zip`)

### 4.5 纹理加载修复

Cubism SDK 通过 `img.src = fileName` 加载 PNG 纹理，**不经过 `window.fetch`**。当 `fileName` 是 `eira-model://` 自定义协议 URL 时，浏览器直接抛出 `ERR_UNKNOWN_URL_SCHEME`。

修复：`lapptexturemanager.ts` 中 `img.src = fileName` 改为 `textureViaFetch(fileName).then(url => img.src = url)`。

---

## 5. API 端点全表

### 5.1 认证

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/auth/register` | 无 | 注册 |
| POST | `/auth/login` | 无 | 登录 |
| POST | `/auth/refresh` | 无 | 刷新 token |
| GET | `/auth/me` | Bearer | 当前用户信息 |

### 5.2 用户端

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/user/preferences` | Bearer | 获取偏好（含 persona_config fallback） |
| PATCH | `/user/preferences` | Bearer | 部分更新偏好（model_source 字段） |
| POST | `/user/background` | Bearer | 上传背景图（magic + 限流 + normalize_mime） |
| POST | `/user/model` | Bearer | 上传 Live2D 模型包 |
| GET | `/user/model/file` | Bearer | 🆕 boto3 直读模型 zip（`?oss_key=`） |
| POST | `/conversations` | Bearer | 创建会话 |
| GET | `/conversations` | Bearer | 列出会话 |
| GET | `/conversations/{id}/messages` | Bearer | 列出消息 |
| POST | `/feedback` | Bearer | 提交反馈 |
| POST | `/voice/asr` | Bearer | 语音识别 REST fallback |
| POST | `/voice/tts` | Bearer | 文本转语音 |
| GET | `/voice/asr/config` | Bearer | ASR 服务配置 |

### 5.3 角色卡

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/personas?scope=public\|mine` | Bearer | 用户端列表 |
| POST | `/personas` | Bearer | 创建 |
| GET | `/personas/{id}` | Bearer | 详情 |
| PATCH | `/personas/{id}` | Bearer | 更新自己的 |
| DELETE | `/personas/{id}` | Bearer | **硬删除**（先清理 chat_session 引用） |
| POST | `/personas/import` | Bearer | ST V2 JSON 导入 |
| GET | `/personas/{id}/export` | Bearer | ST V2 JSON 导出 |

### 5.4 文档 (用户端)

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/documents/upload` | Bearer | 上传文档 |
| GET | `/documents` | Bearer | 列出自己的 |
| GET | `/documents/{id}` | Bearer | 详情（含 progress 字段） |
| GET | `/documents/{id}/progress` | Bearer | 处理进度 |
| DELETE | `/documents/{id}` | Admin | 删 OSS + DB |
| POST | `/documents/{id}/reprocess` | Admin | 重新向量化 |

### 5.5 资源 (用户端)

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/assets/backgrounds` | Bearer | 上传背景 |
| GET | `/assets/backgrounds` | Bearer | 列出背景 |
| DELETE | `/assets/backgrounds/{id}` | Bearer(own) | 删除 |
| POST | `/assets/live2d` | Bearer | 上传模型 zip |
| GET | `/assets/live2d` | Bearer | 列出模型 |
| DELETE | `/assets/live2d/{id}` | Bearer(own) | 删除 |
| GET | `/assets/quota/{kind}` | Bearer | 配额查询 |

### 5.6 管理后台 (全部 require_admin)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/stats` | 账号数 + 对话数（真实数据） |
| GET/PATCH | `/admin/settings` | 系统设置（API key 脱敏） |
| GET/PATCH | `/admin/settings/{key}` | 单个设置（flat key 兼容） |
| GET | `/admin/users?keyword=&role=&page=&size=` | 用户分页列表 |
| GET | `/admin/users/{uid}` | 用户详情 |
| PATCH | `/admin/users/{uid}` | 改 role/disabled |
| DELETE | `/admin/users/{uid}` | 软删除 |
| GET/POST | `/admin/personas` | Persona CRUD（system_prompt 必填） |
| GET/PATCH/DELETE | `/admin/personas/{id}` | Persona 详情/更新/硬删除 |
| POST | `/admin/personas/{id}/set-default` | 设为默认（跨 scope 清除） |
| POST | `/admin/personas/import` | ST V2 JSON 导入 |
| GET | `/admin/documents` | 全量文档列表 |
| POST | `/admin/documents/upload` | 上传文档 |
| GET | `/admin/documents/{id}` | 详情含 chunks |
| GET | `/admin/documents/{id}/status` | 处理进度 |
| DELETE | `/admin/documents/{id}` | 删 OSS + DB |
| POST | `/admin/documents/{id}/reprocess` | 重新向量化 |
| GET | `/admin/assets?kind=` | 全量资产列表（含 oss_key 字段） |
| POST | `/admin/assets/backgrounds` | 上传背景 |
| POST | `/admin/assets/live2d` | 上传模型 |
| DELETE | `/admin/assets/{id}` | 删 OSS + DB |
| POST | `/admin/assets/{id}/set-default` | 设为默认（两种类型） |
| GET | `/admin/assets/{id}/file` | 🆕 boto3 直读模型 zip |
| GET | `/admin/audit?user_id=&action=&path=` | 审计日志查询 |
| GET | `/admin/audit/export` | CSV 导出 |
| GET | `/admin/dashboard/*` (7 端点) | 运营看板（满意度 zero-filling + 词云地理位置过滤） |
| GET | `/admin/dashboard/feedback` | 反馈列表（真实数据） |
| POST | `/admin/dashboard/feedback/{id}/reply` | 回复反馈 |
| GET/PATCH | `/admin/persona-config` | Persona Live2D 配置（background/live2d） |

### 5.7 WebSocket

| 路径 | 鉴权 | 说明 |
|------|------|------|
| `/ws/chat?token=<jwt>` | JWT query param | 文本对话全双工（真实 User + DB session + persist） |
| `/ws/voice?token=<jwt>` | JWT query param | 语音全双工（前端传 session_id） |

---

## 6. 数据库迁移链

迁移 0001 → 0012，线性无分支：

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
| `0012_persona_default_unique` | 🆕 persona 默认唯一索引（跨 scope） |

```bash
cd backend
EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira alembic upgrade head
```

---

## 7. 测试覆盖

### 7.1 目录结构（6 功能模块）

```
tests/
├── conftest.py          ← session-scoped _cleanup_test_data (autouse)
├── pytest.ini           ← asyncio_mode=auto
├── infra/       (7)     ← DB/Redis/OSS/health/config/logging/system
├── identity/    (4)     ← auth/admin_users/admin_settings/audit
├── persona/     (4)     ← personas/silly_import/assets/admin_assets
├── conversation/(5)     ← conversation/ws_chat/ws_messages/safety/orchestrator_smoke
├── knowledge/   (10)    ← documents_api/knowledge_*/chunker/parsers/retrieve_kb/embedding/search
├── voice/       (7)     ← asr/tts/voice/ws_voice/ws_voice_e2e/ws_stream_pacing/sentence_splitter
└── llm/         (2)     ← llm_provider/llm_logging
```

### 7.2 基线

```
~260 passed, 1 skipped, 0 failures
```

1 skipped 为 `test_worker_handles_error_gracefully`（硬编码 skip 占位测试）。

### 7.3 验证门状态

| 状态 | 数量 | 说明 |
|------|:--:|------|
| ✅ 自动化通过 | 9 | 测试已验证 |
| ⚠️ 部分通过 | 2 | 指标接近阈值（RAG Recall@5=0.61、P95=5392ms） |
| ⏳ 待人工闭合 | 6 | 需人工操作 / 真实凭证 / Playwright |

### 7.4 未覆盖

- Playwright E2E 测试（spec 要求，未实现）
- Vitest 前端单元测试（配置就绪，无测试文件）
- 前端质量门: `vue-tsc --noEmit` → 0 errors

### 7.5 注意事项

- `_cleanup_test_data`: session-scoped，仅在 pytest 完全退出时执行。Ctrl+C 中断不会清理
- `_test_transaction`: 已禁用（autouse=False），per-test 事务与 asyncpg 单连接限制冲突
- 测试数据在 session 内部会短暂存在于开发库中

---

## 8. 已知问题

### 8.1 ✅ 已解决（6/15 最终验证通过）

| # | 问题 | 修复 |
|:--:|------|------|
| 1 | web-user Live2D 502（`active_model_id` 被污染为 `eira-model://`） | 分离 virtualBase 与 oss_key；后端 fallback 守卫拒绝脏默认值 |
| 2 | web-admin `Unknown model`（`AdminAssetOut` 缺 `oss_key`） | schema 添加 `oss_key` 字段；list SQL 构造包含 `oss_key` |
| 3 | 残留进程跑旧代码 | `run_clean.sh` 杀端口树 + 无 reload 单进程 |
| 4 | boto3 `get_object()` SignatureDoesNotMatch | 确认为残留进程/网络层问题；干净重启后 18 并发全 200 |
| 5 | PNG 纹理 `ERR_UNKNOWN_URL_SCHEME` | `textureViaFetch()` 路由经 fetch 拦截器 |
| 6 | fetch 拦截器多模型冲突 | 改为 `virtualBase→files` 注册表 |

### 8.2 🔴 上线前必须处理

| # | 问题 | 位置 |
|---|------|------|
| §4.5 | API key 明文存储 system_settings JSONB | `admin_settings.py` / config — 需 pgcrypto + KMS 加密 |

### 8.3 🟡 生产部署前应处理

| # | 问题 | 位置 |
|---|------|------|
| 1 | Auth 限流用 `request.client.host` 非 `X-Forwarded-For` | `deps.py` |
| 2 | ProviderRegistry.invalidate() 单进程，多 Worker 需 Redis pub/sub | `provider_registry.py` |
| 3 | Pipeline 用 asyncio task 无崩溃恢复 | `knowledge_worker.py` |
| 4 | 语音 WS 发送前未检查状态（客户端关闭时 `Cannot call "send"`） | `voice.py` |

### 8.4 🟢 后续改进

| # | 问题 |
|---|------|
| 1 | Dashboard 运营看板 7 个占位端点（Phase 5 填充） |
| 2 | Admin 无用户管理前端页面（API 已就绪） |
| 3 | TTS 语音播报未端到端验证（讯飞凭证有效，浏览器播放待测） |
| 4 | SillyTavern PNG 角色卡导入（当前仅 JSON） |
| 5 | 用户端角色卡选择 UI 未集成 |
| 6 | OSS 孤立文件清理机制（OSS 删除失败时 DB 行已删） |
| 7 | Chunker 短文档静默丢弃（低于 80 tokens） |
| 8 | Embedding API 密钥已过期（4sapi.com），需更新 |
| 9 | Tavily Search API key 未配置 |
| 10 | Dashboard 指标/热问/趋势/词云/情感大量 mock 数据（Phase 5） |
| 11 | 前端单元测试空白 |

---

## 9. 服务启动

### 9.1 基础设施

```powershell
docker compose -f deploy\docker-compose.dev.yml up -d
```

### 9.2 后端（推荐方式）

```bash
# 🆕 干净启动（杀端口残留 + 清 pycache + 无 reload 单进程）
bash backend/scripts/run_clean.sh
```

或手动启动：

```powershell
cd D:\Application\ClaudeCode\repository\Eira\backend
$env:EIRA_JWT__SECRET = "dev-secret"
$env:EIRA_OSS__SECRET = "eira-secret"
$env:EIRA_DB_DSN = "postgresql+asyncpg://eira:eira@localhost:5432/eira"
$env:EIRA_REDIS_URL = "redis://localhost:6379/0"
$env:EIRA_OSS_ENDPOINT = "http://localhost:9000"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 9.3 前端

```bash
pnpm --filter @eira/web-user dev      # http://localhost:5173
pnpm --filter @eira/web-admin dev     # http://localhost:5174
```

### 9.4 测试

```bash
cd backend
EIRA_JWT__SECRET=test-secret EIRA_OSS__SECRET=eira-secret \
  EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
  EIRA_REDIS_URL=redis://localhost:6379/0 \
  EIRA_OSS_ENDPOINT=http://localhost:9000 \
  python -m pytest tests/ -v --tb=short
```

### 9.5 Provider 配置参考

| 服务 | Provider | 环境变量 |
|------|----------|---------|
| LLM | deepseek | `EIRA_LLM__PROVIDER` / `EIRA_LLM__API_KEY` |
| Embedding | openai (4sapi.com) | `EIRA_EMBEDDING__PROVIDER` / `EIRA_EMBEDDING__API_KEY` |
| ASR | xunfei | `EIRA_ASR__PROVIDER` / `EIRA_ASR__API_KEY` / `EIRA_ASR__API_SECRET` / `EIRA_ASR__APP_ID` |
| TTS | xunfei | `EIRA_TTS__PROVIDER` / `EIRA_TTS__API_KEY` / `EIRA_TTS__API_SECRET` / `EIRA_TTS__APP_ID` |
| Search | tavily | `EIRA_SEARCH__PROVIDER` / `EIRA_SEARCH__API_KEY` |

环境变量覆盖格式：`EIRA_{SECTION}__{FIELD}`

### 9.6 测试账号

| 地址 | 邮箱 | 密码 |
|------|------|------|
| http://localhost:5173/login | `admin@eira.dev` | `admin123` |
| http://localhost:5174/login | `admin@eira.dev` | `admin123` |

### 9.7 实机验证四件套

每次验证前必做：
1. `bash backend/scripts/run_clean.sh` 重启后端
2. 两端前端 build / dev server **硬刷新** (Ctrl+Shift+R)
3. **清浏览器 IndexedDB** `eira-live2d-cache`
4. 重新登录

---

## 10. 给新 agent 的告诫

1. **启动后端一律用 `bash backend/scripts/run_clean.sh`**，不要手动 `--reload`。残留旧进程跑旧代码是本项目最频繁的干扰源——日志里出现你代码不该产生的值时，第一反应是「进程没更新」而非改代码。

2. **后端 OSS 下载方式已定稿**：boto3 `get_object_bytes()` 直读，两端走 `/admin/assets/{id}/file` 和 `/user/model/file`。**不要再碰 presigned URL / Vite proxy / 307 重定向**。前序 7 轮尝试已证明那些方向是死路。

3. **改任何涉及 `active_model_id` 的逻辑，先回看 §4.3 标识体系约定**。`eira-model://` 和显示名都是脏值，写入 DB 会导致 502。

4. **不要再盲改后端下载方式**。boto3 直读已实证可用（18 并发全 200）。真正容易出问题的是前端标识体系 + DB 数据 + 残留进程，与 OSS 签名无关。

5. **实机验证前必做四件套**（§9.7），缺一不可。

6. **Persona 已改为硬删除**，删除前会清理 chat_session 引用。不要期望 `disabled=True` 的软删除行为。

7. **测试在开发库中运行**，`_cleanup_test_data` 仅在 session 结束时清理。中断测试会残留数据。

8. 相关记忆文件：
   - `live2d-cubism5-rendering.md` — Cubism 5 渲染关键坑
   - `frontend-optimization-2026-06-06.md` — 前端优化记录
   - `live2d-oss-download-backend-stream.md` — OSS 下载失败循环教训

---

## 11. 归档索引

### 11.1 活跃文档（handoff 根目录）

| 文件 | 说明 |
|------|------|
| `2026-06-15-eira-phase-summary.md` | 🟢 **本文档 — 唯一权威入口** |
| `eira-handoff-2026-06-15-live2d-resolved.md` | 🟢 Live2D 最终修复结论（标识体系、告诫、验证结果） |
| `README.md` | 使用指引 |

### 11.2 早期文档（`archive/` 根，2026-05-28 ~ 06-09）

| 文件 | 内容 |
|------|------|
| `2026-05-28-phase0-handoff.md` | Phase 0 基础设施 |
| `2026-05-28-api-design-spec.md` | 早期 API 设计 |
| `2026-05-28-frontend-ui-handoff.md` | 早期前端 UI |
| `2026-05-29-ui-final-handoff.md` | UI 最终定档 |
| `2026-05-29-ui-responsive-handoff.md` | 响应式 |
| `2026-06-03-frontend-issues.md` | 前端问题清单（已修复） |
| `2026-06-03-phase1-api-spec.md` | Phase 1 API 规格（原始） |
| `2026-06-04-current-state-handoff.md` | 状态快照 |
| `2026-06-06-current-state-handoff.md` | 状态快照 |
| `2026-06-06-frontend-api-spec.md` | 前端 API 需求 |
| `2026-06-07-live2d-interaction-handoff.md` | Live2D 交互修复 |
| `2026-06-08-phase2-handoff.md` | Phase 2 知识库 RAG |
| `2026-06-08-phase3-handoff.md` | Phase 3 语音多模态 |
| `2026-06-08-phase4-handoff.md` | Phase 4 管理后台主体 |
| `2026-06-08-phase4-fixes-handoff.md` | Phase 4 7 项功能修复 |
| `2026-06-08-phase4-gap-closure-handoff.md` | Phase 4 4 个缺口闭合 |
| `2026-06-08-phase4-p0-fixes-handoff.md` | Phase 4 P0 紧急修复 |
| `2026-06-08-security-audit-and-test-fixes.md` | 安全审计 + 测试修复 |
| `2026-06-09-eira-phase-summary.md` | 被本文档替代的旧总结 |
| `2026-06-09-phase1-complete-handoff.md` | Phase 1 完整交接 |
| `2026-06-09-security-fixes-handoff.md` | §5.4+5.5+6.1+6.2+6.4 修复 |

### 11.3 中期文档（`archive/2026-06-10-to-06-15/`）

| 文件 | 内容 |
|------|------|
| `2026-06-10-p0-p2-fixes-handoff.md` | 12 个 P0-P2 问题修复 |
| `2026-06-10-testing-handoff.md` | 持续测试 + 验证门闭合 |
| `eira-handoff-2026-06-14.md` | 全量 API 审查 + P0-P2 修复 |
| `eira-handoff-2026-06-14-phase5-6.md` | Phase 5-6 部分实施 |
| `eira-handoff-2026-06-14-final.md` | 测试重组 + 6 bug 修复 |
| `eira-voice-fixes-handoff-2026-06-14.md` | Voice WS + 讯飞 ASR 修复 |
| `eira-handoff-2026-06-15-live2d-admin-fix.md` | Admin Live2D 7 轮尝试史 |
| `eira-handoff-2026-06-15-live2d-rootcause-review.md` | 三根因系统性审查 |

### 11.4 Plans 文档

| 位置 | 内容 |
|------|------|
| `docs/superpowers/plans/` | 当前计划（overview + Phase 0-7 + Live2D fix） |
| `docs/superpowers/plans/archive/` | 原始未精简版计划 (2026-06-02 前) |

### 11.5 规格与验证

| 位置 | 内容 |
|------|------|
| `docs/superpowers/specs/2026-05-26-architecture-design.md` | 架构设计 spec |
| `docs/superpowers/specs/2026-06-14-live2d-fix-design.md` | Live2D 修复设计 |
| `docs/superpowers/validations/` | 17 个验证门（9 ✅ + 2 ⚠️ + 6 ⏳） |

---

**签出**: 本文档整合自 6/9 总结 + 6/10-6/15 全部 8 个 handoff + 多轮代码审查 + 实机验证，覆盖 Phase 0-5 全部工作和修复链。
**下一步**: Phase 5（运营看板后端 API）或 Phase 3-4 验证门闭合。
