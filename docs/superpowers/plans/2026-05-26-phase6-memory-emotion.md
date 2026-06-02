---
name: 2026-05-26-phase6-memory-emotion
title: Phase 6 · 长期记忆 + 情感识别
date: 2026-05-26
status: draft
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
overview: docs/superpowers/plans/2026-05-26-overview.md
prev: docs/superpowers/plans/2026-05-26-phase5-analytics-dashboard.md
revision: 2026-06-02 — 设置面板 UI 已完成，聚焦后端记忆/情感引擎
---

# Phase 6 实施计划 · 长期记忆 + 情感识别

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Eira 跨会话"记住用户" + 在对话中"读出情绪"。两件事都不影响 MVP 主链路；任何一项异常 → 静默降级。

## 🔒 前端 UI 状态

- **SettingsPanel.vue** 🔒 已包含：记忆开关、「清除全部记忆」按钮、「我的记忆列表」弹窗、隐私说明文案（在偏好设置面板中）。
- **Chat.vue** 🔒 对话气泡已就位，情绪感知仅影响回复内容（通过 LLM prompt 注入），不影响 UI。

**本 Phase 前端工作：** 在 `<script>` 中连接记忆/情感相关的后端 API 开关。必要时可调整设置面板中的记忆相关 UI。

**Architecture:**
- **长期记忆**：会话结束触发 Celery 记忆抽取任务（LLM 从 transcript 抽出事实卡）→ 向量化存 `memory_fact` 表 → 下次会话 load_context 节点向量召回 → 注入 system prompt。
- **情感识别**：L1 文本情感（ONNX 模型，CPU < 100ms）+ L2 语音特征（音量/语速）。识别结果注入 LLM prompt 微调语气。
- 两者均可通过用户设置关闭。

**Tech Stack:** 复用 Phase 1/2 LLM + Embedding Provider；情感模型本地用 `transformers` + ONNX Runtime；记忆抽取走便宜 LLM（temperature=0.2）。

**前置条件：** Phase 0-5 全部 Validation Gate passed；Celery 已上线。

**本 Phase 不做：** 记忆删除/编辑 UI（用户级 UI 已完成，后端 API 需新建）；表情识别（图像，留 Phase 7）。

**重述全局约定：** TDD；commit 前缀；密钥不入库；用户事实卡隐私保护；UI 修改需有后端需求依据。

---

## 任务依赖图

```
T6.1 memory_fact 表 + 迁移
  ↓
T6.2 记忆抽取 prompt + service（LLM 抽取事实卡）
  ↓
T6.3 Celery 任务：会话结束触发抽取
  ↓
T6.4 load_context 节点接入记忆召回（向量检索 + prompt 注入）
  ↓
T6.5 用户记忆管理 API（开关/列表/清除）
  ↓
T6.6 emotion 模型加载 + 推理 service（L1 文本）
  ↓
T6.7 emotion_detect 节点 + LLM prompt 注入情感
  ↓
T6.8 语音情感融合（L2）—— 音量/语速辅助判断
  ↓
🚦 G-6.1 / G-6.2 / G-6.3
```

---

## 后端任务

### Task 6.1: memory_fact 表

**Files:**
- Create: `backend/app/infra/alembic/versions/0011_memory_fact.py`
- Create: `backend/app/domain/memory/models.py`

字段：user_id / text (≤512) / category (preference/visit/plan/identity/other) / source_session_id / confidence / embedding vector(1536) / expires_at / last_used_at / hits。HNSW 索引。

### Task 6.2: 记忆抽取 service

**Files:**
- Create: `backend/app/domain/memory/service.py`
- Create: `backend/app/domain/memory/prompts.py`
- Create: `backend/tests/unit/test_memory_extractor.py`

抽取 prompt 用便宜 LLM（temperature=0.2）。JSON 解析失败兜底返回 []。入库前去重（余弦相似度 > 0.92 视为重复）。单次最多 20 条。

### Task 6.3: Celery 会话结束触发抽取

**Files:**
- Modify: `backend/app/api/ws/chat.py`、`voice.py`
- Create: `backend/app/workers/memory_worker.py`

触发时机：ws close + 30min idle 兜底。countdown=60s（等用户可能重连）。每日清理过期 facts。

### Task 6.4: load_context 接入记忆召回

**Files:**
- Modify: `backend/app/orchestrator/state.py`（追加 memory_context）
- Modify: `backend/app/orchestrator/nodes/load_context.py`
- Create: `backend/app/domain/memory/repository.py`
- Create: `backend/tests/integration/test_load_context_memory.py`

首次消息触发一次 embedding 查询 → top-K 召回 → 注入 prompt。会话期间静态缓存。prompt 顺序：persona → memory → kb → user_text。

### Task 6.5: 用户记忆管理 API

**Files:**
- Create: `backend/app/api/rest/user_memory.py`
- Modify: `apps/web-user/src/components/SettingsPanel.vue`（`<script>` only — 连接 API）

API：`GET /me/memory`（列表）、`DELETE /me/memory/{id}`（单条删除）、`DELETE /me/memory`（清除全部）、`GET /me/memory/settings`（开关状态）。

### Task 6.6: emotion 模型加载 + 推理（L1）

**Files:**
- Create: `backend/app/capabilities/emotion/`（base.py / text_onnx.py / factory.py）
- Modify: `backend/app/core/config.py`（追加 EmotionSettings）
- Create: `backend/tests/unit/test_emotion_text.py`

MVP 用 `cardiffnlp/twitter-xlm-roberta-base-sentiment` → ONNX。模型 ≤ 300MB，CPU P95 ≤ 100ms。输出归一化 5 类：happy/sad/angry/surprised/neutral。置信度 < 0.55 → neutral。

### Task 6.7: emotion_detect 节点 + prompt 注入

**Files:**
- Create: `backend/app/orchestrator/nodes/emotion_detect.py`
- Modify: `backend/app/orchestrator/graph.py`（safety_in 之后插入）
- Modify: `backend/app/orchestrator/nodes/llm_call.py`（注入 emotion hint）

超时硬上限 300ms → 降级 neutral。prompt 注入微调语气提示。失败永不抛异常。

### Task 6.8: 语音情感融合（L2）

**Files:**
- Create: `backend/app/capabilities/emotion/voice_acoustic.py`
- Modify: `backend/app/api/ws/voice.py`

声学特征：RMS 音量 + speaking_rate + pitch_std → 映射规则。仅 voice 通道生效。融合：text_conf ≥ 0.7 → text_label；否则 acoustic_label。

---

## 🚦 Validation Gates

### G-6.1 · 长期记忆有效性
- 5 个用户 × 3 session = 15 个会话评分；命中率 ≥ 60%；无错误注入 ≥ 95%。

### G-6.2 · 情感识别准确性 + 不拖延迟
- 100 句标注准确率 ≥ 65%；emotion_detect P95 ≤ 100ms。

### G-6.3 · 主链路稳定性回归
- 开启记忆+情感后首 token P95 ≤ 2.2s；关闭后 baseline 差异 ≤ 3%。

---

## 完成状态

Phase 6 完成 ⇔ G-6.1 / 6.2 / 6.3 全部 passed。

## Revision 2026-06-02

- **标记 T6.5 前端 UI 已完成**（SettingsPanel 记忆开关/清除/列表/隐私文案已在 Chat.vue 的设置面板中实现）。
- 新增 T6.5 后端 API（用户记忆 CRUD）+ 数据对接（SettingsPanel `<script>` 连接 API）。
- 其余后端任务保持不变。
