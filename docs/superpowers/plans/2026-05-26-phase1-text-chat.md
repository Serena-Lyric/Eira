---
name: 2026-05-26-phase1-text-chat
title: Phase 1 · 文本对话闭环 + Live2D 画布（后端 + 数据对接）
date: 2026-05-26
status: draft
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
overview: docs/superpowers/plans/2026-05-26-overview.md
prev: docs/superpowers/plans/2026-05-26-phase0-infra-bootstrap.md
revision: 2026-06-02 — UI 冻结，移除前端构建任务，替换为数据对接
---

# Phase 1 实施计划 · 文本对话闭环 + Live2D 画布

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现后端 LLM 对话链路（LangGraph 编排 + WS 流式推送），并将前端已完成的数据层 composables（useChatSession / useLive2DController / useActionParser）接入 Chat.vue 的 `<script>` 部分。验证门 G-1.x 通过后视为"文本闭环达标"。

## 🔒 前端 UI 状态

**用户端 UI 已 100% 定档。** Chat.vue（426 行自包含）、Login.vue、Live2D 画布占位符及所有子组件（CameraMiniWindow / CharacterSpeechBubble / ChatInputArea / QuickQuestionPanel / SettingsPanel / TopSettingsButton / Live2DCanvas）的 `<template>` 和 `<style>` 不可修改。

**三个 Composable 已实现但未接入：**
- `useChatSession` — WebSocket 会话管理 + 消息队列
- `useLive2DController` — PIXI 应用初始化 + 模型加载
- `useActionParser` — 动作标记解析（[wave]/[nod]/[happy]）

**本 Phase 前端工作仅限：** 在 Chat.vue 的 `<script>` 中引入上述 composables，替换 mock 数据逻辑，不修改 template/CSS。

**Architecture:**
- LLM Provider 抽象：默认 DeepSeek（OpenAI 兼容协议）；预留 OpenAI/Tongyi/Volc 适配器。
- Orchestrator：LangGraph 状态图，节点序列：`load_context → safety_in → retrieve(stub) → llm_call → safety_out → persist → emit`。
- 通信：WebSocket `/ws/chat?session_id=...`，消息类型 `user_text / token / done / error / state`。
- Live2D：PixiJS + pixi-live2d-display 渲染 Cubism 4 模型，全屏画布，支持拖拽 + 滚轮缩放。
- 持久化：会话与消息表落 PG，支持后续 Phase 6 抽取记忆。

**Tech Stack:** LangGraph、`openai` SDK（兼容 DeepSeek）、httpx、pgvector（仅建表占位）、PixiJS 7、pixi-live2d-display、WebSocket（FastAPI 内置）。

**前置条件：** Phase 0 全部 Validation Gate passed。✅

**本 Phase 不做：** 真正的 RAG 检索（Phase 2）；ASR/TTS（Phase 3）；情感与长期记忆（Phase 6）；管理后台功能（Phase 4）。

**重述全局约定：**
- TDD 强制；每 Step 5 提交。
- 所有 Provider 调用走 `capabilities/llm/base.py` 的统一接口；禁止业务模块直接 import openai/deepseek SDK。
- 🔒 禁止修改任何 `.vue` 文件的 `<template>` / `<style>`。
- 验证门数据归档至 `docs/superpowers/validations/`。

---

## 任务依赖图

```
T1.1 LLM Provider 抽象 + DeepSeek 适配器（含 VCR 录制）
  ↓
T1.2 Orchestrator 状态机骨架（LangGraph 图与 State）
  ↓
T1.3 Conversation 领域（session/message 模型 + 仓储 + 服务）
  ↓
T1.4 Safety 节点（in/out 简版：长度 + 关键词）
  ↓
T1.5 WS 协议与端点 /ws/chat
  ↓
T1.6 流式 token 推送（LLM stream → WS token 帧）
  ↓
T1.7 前端数据对接 — Chat.vue 接入 useChatSession + useLive2DController + useActionParser
  ↓
T1.8 节点埋点 + LLM 调用日志
  ↓
🚦 G-1.1 / G-1.2 / G-1.3 / G-1.4
```

---

## 后端任务

### Task 1.1: LLM Provider 抽象 + DeepSeek 适配器

**Files:**
- Create: `backend/app/capabilities/__init__.py`
- Create: `backend/app/capabilities/llm/__init__.py`
- Create: `backend/app/capabilities/llm/base.py`
- Create: `backend/app/capabilities/llm/openai_compat.py`
- Create: `backend/app/capabilities/llm/mock.py`
- Create: `backend/app/capabilities/llm/factory.py`
- Modify: `backend/app/core/config.py`（追加 LlmSettings）
- Modify: `backend/pyproject.toml`（加 `openai>=1.30`、`tenacity>=8.2`、`pytest-vcr>=1.0`）
- Create: `backend/tests/unit/test_llm_provider.py`
- Create: `backend/tests/cassettes/`

> ⚠️ **要点**：
> - 适配器返回 `AsyncIterator[LlmDelta]`，业务代码用 `async for` 消费。
> - 失败重试：网络错误指数退避 3 次（tenacity）；429 退避 + 抖动；4xx 不重试；5xx 重试 2 次。
> - 调用日志字段：`provider/model/prompt_tokens/completion_tokens/cost_estimate/latency_ms/request_id`。
> - Mock Provider 用于测试，返回固定中文文本。

测试流程：写失败测试 → 实现 → VCR 录制（需真实 key）→ 验证通过 → 提交。

---

### Task 1.2: Orchestrator 状态机骨架

**Files:**
- Create: `backend/app/orchestrator/__init__.py`
- Create: `backend/app/orchestrator/state.py`
- Create: `backend/app/orchestrator/graph.py`
- Create: `backend/app/orchestrator/nodes/__init__.py`
- Create: `backend/app/orchestrator/nodes/load_context.py`
- Create: `backend/app/orchestrator/nodes/llm_call.py`
- Create: `backend/app/orchestrator/nodes/persist.py`
- Create: `backend/app/orchestrator/nodes/emit.py`
- Modify: `backend/pyproject.toml`（加 `langgraph>=0.2`）
- Create: `backend/tests/integration/test_orchestrator_smoke.py`

> ⚠️ **要点**：
> - ChatState 字段：session_id / user_id / user_text / history / persona_prompt / retrieved_chunks / safety_in_ok / safety_out_ok / llm_text / llm_meta / error。
> - 图节点序列（MVP）：load_context → llm_call → persist → emit → END。Safety 节点在 T1.4 插入，RAG 在 Phase 2 插入。
> - 使用 Mock LLM Provider 跑通全链路。

---

### Task 1.3: Conversation 领域（会话/消息）

**Files:**
- Create: `backend/app/domain/conversation/__init__.py`
- Create: `backend/app/domain/conversation/models.py`
- Create: `backend/app/domain/conversation/schemas.py`
- Create: `backend/app/domain/conversation/repository.py`
- Create: `backend/app/domain/conversation/service.py`
- Create: `backend/app/api/rest/conversations.py`
- Modify: `backend/app/main.py`（注册路由）
- Create: `backend/app/infra/alembic/versions/0003_conversation_tables.py`
- Create: `backend/tests/integration/test_conversation.py`
- Modify: `backend/app/orchestrator/nodes/persist.py`（接入仓储）

> ⚠️ **要点**：
> - 表：`chat_session`（id / user_id / persona_id / title / created_at / ended_at）
> - 表：`chat_message`（id / session_id / role / content / audio_oss_key / metadata_json / created_at）
> - REST：`POST /conversations`（创建会话）、`GET /conversations`（列表）、`GET /conversations/{sid}/messages`（消息列表）
> - persist 节点：用户提交时插入 role=user 消息；流式完成后插入 role=assistant 消息。

---

### Task 1.4: Safety 节点（输入/输出过滤简版）

**Files:**
- Create: `backend/app/orchestrator/nodes/safety_in.py`
- Create: `backend/app/orchestrator/nodes/safety_out.py`
- Create: `backend/app/core/safety_words.py`
- Modify: `backend/app/orchestrator/graph.py`（插入 safety_in / safety_out）
- Create: `backend/tests/unit/test_safety.py`

> ⚠️ **要点**：
> - Phase 1 仅做"长度截断 + 黑名单关键词拒答"。
> - 输入截断：MAX_USER_INPUT_LEN = 2000 字符。
> - 输出脱敏：正则匹配 sk-xxx、AKIAxxx 等密钥模式替换为 [REDACTED]。
> - safety_in 失败 → 短路至 emit，返回兜底回复。

---

### Task 1.5: WebSocket 协议与 /ws/chat

**Files:**
- Create: `backend/app/api/ws/__init__.py`
- Create: `backend/app/api/ws/chat.py`
- Create: `backend/app/api/ws/messages.py`（pydantic 消息 schema）
- Modify: `backend/app/main.py`（注册 ws 路由）
- Create: `backend/tests/integration/test_ws_chat.py`

> ⚠️ **协议契约（spec 已锁定）**：
> ```
> client → server:
>   {"type":"user_text","session_id":"...","text":"...","ts":...}
>   {"type":"interrupt"}                      # 预留 phase 3
> server → client:
>   {"type":"state","phase":"thinking"}
>   {"type":"token","text":"..."}             # 流式片段
>   {"type":"action","tag":"wave"}            # 动作标记
>   {"type":"done","message_id":123,"latency_ms":..., "tokens":{...}}
>   {"type":"error","code":"...","detail":"..."}
> ```

WS 端点通过 query string 携带 token（简化做法）；接收 user_text 后驱动 orchestrator 图，流式推送 token 帧。

---

### Task 1.6: 流式 token 推送链路自检

**Files:**
- Create: `backend/tests/integration/test_ws_stream_pacing.py`

> 目的：验证 token 帧首响 ≤ 1.2s（mock）/ ≤ 2s（真实 LLM）；token 帧节奏均匀（最大 gap < 800ms）。

---

## 前端数据对接任务

> 🔒 以下任务**仅修改 Chat.vue 的 `<script>` 部分**和 composables 文件。禁止修改 template/CSS。

### Task 1.7-FE: Chat.vue 接入 useChatSession

**Files:**
- Modify: `apps/web-user/src/pages/Chat.vue`（`<script>` only）
- Modify: `apps/web-user/src/composables/useChatSession.ts`（按需调整）

**工作内容：**
1. 在 Chat.vue `<script setup>` 中 `import { useChatSession } from '../composables/useChatSession'`
2. 用 `useChatSession` 的 `messages` / `phase` / `send` 替换当前 `mockBackendResponse` 逻辑
3. 保留所有现有 UI 交互（打字机效果、气泡渲染、发送触发）
4. WS URL 从当前环境自动推导（`ws://` 或 `wss://`）
5. 错误处理：WS 断开时在控制台 log，不弹出 visible error（保持 UI 干净）

**验证：** 启动后端 + `pnpm --filter web-user dev`，发送文本消息 → 收到 WS 流式回复 → 气泡正常渲染。

---

### Task 1.7-FE-2: Chat.vue 接入 useLive2DController

**Files:**
- Modify: `apps/web-user/src/pages/Chat.vue`（`<script>` only）
- Modify: `apps/web-user/src/composables/useLive2DController.ts`（按需调整）

**工作内容：**
1. 在 Chat.vue `<script setup>` 中引入 `useLive2DController`
2. 在 `onMounted` 中初始化 PIXI 应用 + 加载默认模型（`/live2d/Hiyori/Hiyori.model3.json`）
3. 将 Live2D 画布绑定到现有 canvas 占位元素
4. 支持拖拽 + 滚轮缩放 + 位置持久化到 localStorage

**前置依赖：** 需补充 Live2D 模型资产文件（`.moc3` / 纹理 PNG / `.physics3.json` / `.motion3.json`）到 `public/live2d/Hiyori/`。

**验证：** 浏览器中模型正常显示，可拖拽/缩放，刷新后位置保留。

---

### Task 1.7-FE-3: Chat.vue 接入 useActionParser

**Files:**
- Modify: `apps/web-user/src/pages/Chat.vue`（`<script>` only）
- Modify: `apps/web-user/src/composables/useActionParser.ts`（按需调整）

**工作内容：**
1. 在 Chat.vue 中监听 WS `action` 帧（`{"type":"action","tag":"wave"}`）
2. 调用 `useActionParser` 解析动作标记 → 触发 Live2D motion
3. 动作标记从显示文本中剥离（不在气泡里展示 `[wave]` 等标记）

**后端依赖：** 需要在 LLM system prompt 中教模型插入动作标记（见 T1.2 llm_call 节点）。

**验证：** 发送触发消息 → LLM 返回含 `[wave]` 等标记的回复 → Live2D 执行对应动作 → 气泡中不显示标记。

---

### Task 1.8: 节点埋点 + LLM 调用日志

**Files:**
- Modify: `backend/app/orchestrator/nodes/*.py`（每节点 enter/exit log 与耗时）
- Create: `backend/app/capabilities/llm/logging_decorator.py`
- Create: `backend/app/capabilities/llm/pricing.yaml`
- Create: `backend/tests/unit/test_llm_logging.py`

> ⚠️ **关键日志字段**：
> - `event=orchestrator.node.start | orchestrator.node.end | orchestrator.error`
> - `event=llm.call.start | llm.call.end | llm.call.error`
> - 必含 `request_id / session_id / user_id / model / latency_ms`

---

## 🚦 Validation Gate G-1.1 · 文本对话功能完整性

| 项 | 内容 |
|---|---|
| 指标 | 注册→登录→建会话→发问→收到完整回复→`/conversations/{id}/messages` 出现两条记录 |
| 阈值 | 100% 通过；DB 中 user/assistant message 顺序正确；token 帧数 > 1 |
| 测试方法 | `pytest tests/integration/test_ws_chat.py tests/integration/test_conversation.py -v`；手测 dev 环境完整跑 3 轮 |
| 数据源 | pytest 报告；归档 `docs/superpowers/validations/G-1.1.md` |
| 通过分支 | 进入下一门 |
| 不通过分支 | 缺消息持久化 → 回 T1.5；token 帧只 1 个 → 检查 stream 配置 |

---

## 🚦 Validation Gate G-1.2 · 端到端文本延迟

| 项 | 内容 |
|---|---|
| 指标 | 真实 LLM (deepseek-chat) 下首 token 延迟 P50/P95；整答完成延迟 P50/P95 |
| 阈值 | 首 token P50 ≤ 1.2s, P95 ≤ 2s；整答完成 P50 ≤ 4s, P95 ≤ 6s |
| 测试方法 | `scripts/bench_chat_latency.py`，固定 30 个 prompt，串行跑 5 轮 |
| 数据源 | 脚本输出 CSV + structlog；归档 `docs/superpowers/validations/G-1.2.md` |
| 通过分支 | 进入 G-1.3 |
| 不通过分支 | 首 token 慢 → 检查 provider stream 配置；普遍超 → 升级 spec |

---

## 🚦 Validation Gate G-1.3 · Live2D 画布 + 数据对接集成

| 项 | 内容 |
|---|---|
| 指标 | Chat.vue 通过 useChatSession 成功收发消息；Live2D 模型加载并渲染；动作标记触发正确 motion |
| 阈值 | 三项全部通过；刷新后 Live2D 位置/缩放保留 |
| 测试方法 | 手动：启动全栈（backend + frontend），完成登录→发消息→观察 Live2D 渲染→验证动作标记 |
| 数据源 | 截图 + 功能 checklist；归档 `docs/superpowers/validations/G-1.3.md` |
| 通过分支 | 进入 G-1.4 |
| 不通过分支 | WS 不通 → 检查 useChatSession wsUrl 构建；模型不加载 → 检查资产文件路径；动作不触发 → 检查 actionParser 映射 |

---

## 🚦 Validation Gate G-1.4 · 单元 + 集成测试覆盖率

| 项 | 内容 |
|---|---|
| 指标 | 后端 `pytest --cov=app` 覆盖率（行）；关键模块覆盖率单独统计 |
| 阈值 | 总覆盖 ≥ 70%；关键模块（domain/conversation, capabilities/llm, orchestrator, api/ws）≥ 80% |
| 测试方法 | CI 中 `--cov-report=xml` 取分项 |
| 数据源 | `coverage.xml`；归档 `docs/superpowers/validations/G-1.4.md` |
| 通过分支 | 合入 main，打 `gate-G-1.4-passed`；进入 Phase 2 |
| 不通过分支 | 不允许临时屏蔽测试达标；优先补 service / WS 边界测试 |

---

## 完成状态

Phase 1 完成 ⇔ G-1.1 / G-1.2 / G-1.3 / G-1.4 全部 passed。

## Revision 2026-06-02

- **移除 T1.7-T1.10**（前端聊天页骨架 / Live2D 画布 / 动作标记解析 / 待机动作构建任务）—— 前端 UI 已全部完成。
- **新增 T1.7-FE 系列**（Chat.vue 数据对接任务）—— 在 `<script>` 中连接 useChatSession / useLive2DController / useActionParser。
- Chat.vue 已从子组件模式变为全内联模式（426 行自包含），UI 冻结不可修改 template/CSS。
- Live2D 模型资产（.moc3 / 纹理等）需补充到 `public/live2d/Hiyori/`。
