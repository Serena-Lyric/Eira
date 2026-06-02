---
name: 2026-05-26-phase3-voice-multimodal-shell
title: Phase 3 · 语音流式 + 多模态壳层（后端 + 数据对接）
date: 2026-05-26
status: draft
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
overview: docs/superpowers/plans/2026-05-26-overview.md
prev: docs/superpowers/plans/2026-05-26-phase2-knowledge-rag.md
revision: 2026-06-02 — UI 基线已完成，移除前端构建任务，替换为数据对接
---

# Phase 3 实施计划 · 语音流式 + 多模态壳层

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现后端 ASR/TTS 流式管线，将前端已完成的麦克风/摄像头小窗/设置面板/背景切换等 UI 通过数据对接接入后端。语音问答 P95 ≤ 5s（spec 锁定 KPI）。

## 🔒 前端 UI 状态

**用户端 UI 已 100% 基线定档。** 以下功能已在 Chat.vue 中完成 UI（mock 数据 / 占位状态）：

- ✅ 设置面板（背景替换/模糊/语音/摄像头模式/UI 位置/意见反馈）
- ✅ 麦克风按钮（语音按钮模拟）
- ✅ 附件上传按钮（`+` 按钮已绑定文件选择器，预留 `POST /api/v1/messages/attachments`）
- ✅ 画中画摄像头窗口（`getUserMedia` 已注释，显示"API预留"）
- ✅ 背景图展示 + 模糊切换
- ✅ 桌面端响应式 + 安全区适配

**本 Phase 前端工作：** 在 `<script>` 中启用已注释的功能（摄像头）、连接后端语音 WS、连接口型同步。必要时（由后端实现需求驱动）可调整 UI。

**Architecture:**
- ASR：流式 WS（云阿里 NLS / Azure / 讯飞），前端 MediaRecorder → WS 二进制帧 → 后端 ASR Provider。
- TTS：LLM token 按句切句 → TTS Provider 流式合成 → WS 推音频帧 → 前端 Web Audio API 播放 + Live2D 口型同步。
- 摄像头小窗：getUserMedia → 本地 video 元素，本 phase **不上传图像**（图像识别留 Phase 7）。
- 资源管理：背景图片/视频与 Live2D 模型上传到 OSS，前端通过签名 URL 拉取。

**Tech Stack:** 前端 `MediaRecorder`、`Web Audio API`、`pixi-live2d-display`、`getUserMedia`；后端 ASR/TTS Provider 抽象。

**前置条件：** Phase 1 + Phase 2 全部 Validation Gate passed。

**本 Phase 不做：** 图像识别（Phase 7）、长期记忆抽取（Phase 6）。

**重述全局约定：** TDD；commit 前缀；密钥不入库；用户音频默认不持久化；UI 修改需有后端需求依据。

---

## 任务依赖图

```
T3.1 ASR Provider 抽象 + 流式适配器
  ↓
T3.2 后端 /ws/voice 端点
  ↓
T3.3 TTS Provider 抽象 + 流式适配器
  ↓
T3.4 句切引擎（LLM token → 完整句 → TTS）
  ↓
T3.5 WS 音频帧推送 + 反压策略
  ↓
T3.6 前端数据对接 — 启用摄像头 + 连接语音 WS + 口型同步
  ↓
T3.7 资源管理 REST + OSS（背景 / Live2D 模型上传/列表/删除）
  ↓
T3.8 异步管线接入 Celery（替换 BackgroundTasks）
  ↓
🚦 G-3.1 / G-3.2 / G-3.3 / G-3.4
```

---

## 后端任务

### Task 3.1: ASR Provider 抽象 + 流式适配器

**Files:**
- Create: `backend/app/capabilities/asr/`（base.py / aliyun_nls.py / factory.py）
- Modify: `backend/app/core/config.py`（追加 AsrSettings）
- Create: `backend/tests/unit/test_asr.py`（VCR）

接口：`async def stream(audio: AsyncIterator[bytes], lang="zh") -> AsyncIterator[AsrEvent{kind, text, is_final}]`。心跳 5s；超时 30s 自动 close。

---

### Task 3.2: 后端 /ws/voice 端点

**Files:**
- Create: `backend/app/api/ws/voice.py`
- Create: `backend/app/api/ws/voice_messages.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/integration/test_ws_voice.py`

协议：客户端发送音频二进制帧 + 控制消息（start/end/barge_in）；服务端推送 asr.partial/asr.final/chat.token/音频二进制/chat.done。

---

### Task 3.3: TTS Provider 抽象

**Files:**
- Create: `backend/app/capabilities/tts/`（base.py / aliyun_nls.py / azure_tts.py / factory.py）
- Modify: `backend/app/core/config.py`（追加 TtsSettings）
- Create: `backend/tests/unit/test_tts.py`

接口：`async def stream(text, voice, format="opus") -> AsyncIterator[bytes]`。默认 opus@24kHz；流式合成边输出边返回 chunk。

---

### Task 3.4: 句切引擎

**Files:**
- Create: `backend/app/orchestrator/sentence_splitter.py`
- Create: `backend/tests/unit/test_sentence_splitter.py`

判定：碰到 `。！？\n`（最少 6 字）；连续 1.5s 无新 token 强制 flush；动作标记剥离。

---

### Task 3.5: WS 音频帧推送 + 反压策略

**Files:**
- Modify: `backend/app/api/ws/voice.py`
- Create: `backend/app/api/ws/audio_pump.py`
- Create: `backend/tests/integration/test_ws_voice_e2e.py`

每句 TTS 流即推 ws；反压检测（前端 buffer > 3s → sleep 50ms）。

---

## 前端数据对接任务

### Task 3.6-FE: 启用已有功能 + 连接语音管线

**Files:**
- Modify: `apps/web-user/src/pages/Chat.vue`（`<script>` only）
- Modify: `apps/web-user/src/composables/useMicRecorder.ts`（按需调整）
- Modify: `apps/web-user/src/composables/useAudioPlayer.ts`（按需调整）
- Modify: `apps/web-user/src/composables/useCamera.ts`（按需调整）

**工作内容：**
1. **启用摄像头**：恢复 Chat.vue `<script>` 中 `getUserMedia` 调用，连接 CameraMiniWindow 逻辑
2. **连接语音 WS**：创建 `voiceWs.ts` 服务，连接 `/ws/voice`，接入 useMicRecorder（录音 → 发送音频帧）
3. **连接 TTS 播放**：useAudioPlayer 接收音频帧 → Web Audio API 顺序播放
4. **口型同步**：useAudioPlayer 的 amplitude 回调 → Live2D `ParamMouthOpenY` 参数驱动

**验证：** 启动全栈 → 点击麦克风按钮录音 → ASR 识别 → LLM 回复 → TTS 语音播放 → Live2D 嘴型同步。

---

## 资源管理后端

### Task 3.7: 资源管理 REST + OSS

**Files:**
- Create: `backend/app/api/rest/assets.py`
- Create: `backend/app/infra/alembic/versions/0005_assets_table.py`
- Create: `backend/app/domain/persona/quota.py`
- Create: `backend/tests/integration/test_assets.py`

REST：`POST /assets`（上传）/ `GET /assets?kind=`（列表）/ `DELETE /assets/{id}` / `GET /assets/{id}/url`（签名 URL TTL 300s）。配额：背景 5 / Live2D 10 / 文档 100。mime 白名单校验。Live2D 模型 zip 上传后自动解压识别 model3.json。

---

### Task 3.8: 异步管线接入 Celery

**Files:**
- Modify: `deploy/docker-compose.yml`（追加 celery worker + beat）
- Create: `backend/app/workers/celery_app.py`
- Modify: `backend/app/workers/knowledge_worker.py`（@celery.task 化）

> ⚠️ **触发条件**：Phase 2 G-2.1 耗时 > 60s 或 backend 副本 ≥ 2 时必做；否则可推迟到 Phase 4。

---

## 🚦 Validation Gates

### G-3.1 · 端到端语音回路延迟（核心 KPI）
- 端到端 P95 ≤ 5s。分项：ASR final ≤ 1.5s、ASR→LLM 首 token ≤ 1.5s、LLM 首 token→TTS 首 chunk ≤ 1s。

### G-3.2 · 口型同步主观自然度
- 5 名测试者 10 段回复评分 ≥ 3.5/5。

### G-3.3 · 资源管理稳定性
- 上传/切换/删除/刷新保留 100% 成功；签名 URL 过期前刷新成功率 100%。

### G-3.4 · 设置面板回归 + MVP 完整度
- UI 全部要素功能正确；Playwright E2E 主路径绿。

---

## 完成状态

Phase 3 完成 ⇔ G-3.1 / 3.2 / 3.3 / 3.4 全部 passed。MVP 视为达标。

## Revision 2026-06-02

- **移除 T3.6-T3.13**（前端录音/播放/口型/摄像头/设置面板/背景/模型上传/资源管理 UI 构建任务）—— 前端 UI 已全部完成。
- **新增 T3.6-FE**（前端数据对接）—— 启用摄像头、连接语音 WS、连接口型同步。
- **新增 T3.7-T3.8**（资源管理后端 + Celery）—— 从原 T3.11-T3.14 提取后端部分。
- Chat.vue 中麦克风/摄像头/设置面板均已实现 UI，仅需 `<script>` 层启用和对接。
