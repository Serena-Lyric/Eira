---
name: 2026-05-26-phase5-analytics-dashboard
title: Phase 5 · 运营埋点 + 聚合 + 看板数据 API（后端 + 数据对接）
date: 2026-05-26
status: draft
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
overview: docs/superpowers/plans/2026-05-26-overview.md
prev: docs/superpowers/plans/2026-05-26-phase4-admin-persona.md
revision: 2026-06-02 — 看板 UI 已完成（手写 SVG），聚焦后端埋点/聚合/API + 数据对接
---

# Phase 5 实施计划 · 运营埋点 + 聚合 + 看板数据 API

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Phase 1-4 的日志事件沉淀为运营指标，提供后端 metrics API，将已完成的 Dashboard.vue 看板 UI 从硬编码 SVG 数据切换为真实 API 调用。

## 🔒 前端 UI 状态

- **Dashboard.vue（499 行）** 🔒 已定档：内联三视图（运营看板/API 配置/系统设置），使用手写 SVG 图表（非 ECharts）。
- 所有数据为硬编码。
- **本 Phase 前端工作：** 在 `<script>` 中替换硬编码数据为 API 调用。SVG 图表的数据绑定可能需要根据 API 数据结构做适配性调整。

**Architecture:**
- **事件源**：chat_session/chat_message、LLM 调用日志、retrieve 日志、ASR/TTS 日志、audit_log。
- **聚合**：Celery beat 每日 03:30 跑聚合任务 → `metric_daily` / `topic_daily` / `cost_daily` 三张聚合表。
- **实时**：当日数据走 Redis 计数器（DAU 用 HyperLogLog、在线连接数）。
- **看板 API**：`/admin/metrics/*` REST 端点（require_admin 保护）。

**Tech Stack:** Celery beat + worker、Redis HLL、pandas（仅 worker 中按需引入，不拖慢 backend 冷启动）。

**前置条件：** Phase 0-4 全部 Validation Gate passed。

**本 Phase 不做：** ECharts（手工 SVG 已是最终方案）；外部 BI 接入；告警规则系统。

**重述全局约定：** TDD；commit 前缀；密钥不入库；聚合任务幂等可重跑；数据保留期 365 天（聚合表）+ 90 天（明细日志）。

---

## 任务依赖图

```
T5.1 app_event 表 + 标准事件 schema
  ↓
T5.2 事件写入封装（关键节点接入 emit）
  ↓
T5.3 聚合表 schema（metric_daily / topic_daily / cost_daily）+ 迁移
  ↓
T5.4 Celery beat 每日聚合任务（含主题分类）
  ↓
T5.5 Redis 实时计数器 + 在线连接数
  ↓
T5.6 后端 metrics REST 接口
  ↓
T5.7 前端数据对接 — Dashboard.vue SVG 图表接入 API + 数据导出
  ↓
🚦 G-5.1 / G-5.2 / G-5.3
```

---

## 后端任务

### Task 5.1: app_event 表 + 标准事件 schema

**Files:**
- Create: `backend/app/infra/alembic/versions/0009_app_event.py`
- Create: `backend/app/domain/analytics/models.py`
- Create: `backend/app/domain/analytics/event_schema.py`
- Create: `backend/tests/unit/test_event_schema.py`

标准事件 kind（白名单）：`chat.session_open/close`、`chat.user_message/assistant_message`、`llm.call`、`embedding.call`、`retrieve.kb/web`、`asr.session`、`tts.synthesis`、`error.captured`。不在白名单拒写。

---

### Task 5.2: 事件写入封装 + 关键节点接入

**Files:**
- Create: `backend/app/domain/analytics/emitter.py`
- Modify: `backend/app/orchestrator/nodes/llm_call.py`、`retrieve_kb.py`、`web_search.py`
- Modify: `backend/app/api/ws/chat.py`、`voice.py`
- Modify: `backend/app/capabilities/embedding/`

> ⚠️ emit 走 fire-and-forget（`asyncio.create_task`），不阻塞主链路。高频事件用批量队列（50 条或 2s flush）。

---

### Task 5.3: 聚合表 schema

**Files:**
- Create: `backend/app/infra/alembic/versions/0010_metrics_daily.py`
- Create: `backend/app/domain/analytics/schemas.py`

三张表：`metric_daily`（DAU/新用户/会话/消息/语音/检索次数/延迟 P50 P95/错误数）、`topic_daily`（d + topic + count）、`cost_daily`（d + provider + model + kind + calls + tokens + cost_usd）。主键含 date，支持 `ON CONFLICT ... DO UPDATE` 幂等。

---

### Task 5.4: Celery beat 每日聚合任务

**Files:**
- Modify: `backend/app/workers/celery_app.py`
- Create: `backend/app/workers/aggregator.py`
- Create: `backend/app/domain/analytics/topic_classifier.py`
- Create: `backend/tests/unit/test_aggregator.py`

主题分类（MVP 关键词匹配 8 类）：历史/路线/票务/餐饮/厕所/拍照/设施/其他。聚合任务幂等可重跑某日。

---

### Task 5.5: Redis 实时计数器

**Files:**
- Create: `backend/app/domain/analytics/realtime.py`
- Modify: `backend/app/api/ws/chat.py`、`voice.py`（连接/断开时 incr/decr 在线计数）
- Create: `backend/tests/unit/test_realtime_counters.py`

DAU 用 PFADD（HLL 误差 ≤ 1%）；在线数用 incr/decr + 心跳续租（key TTL 10min）。

---

### Task 5.6: 后端 metrics REST 接口

**Files:**
- Create: `backend/app/api/rest/admin_metrics.py`
- Create: `backend/tests/integration/test_admin_metrics.py`

端点：`GET /admin/metrics/realtime`、`/daily?from=&to=`、`/topics?from=&to=&topN=`、`/cost?from=&to=&groupBy=`、`/health`、`/export?metric=&from=&to=&format=csv`。全部 require_admin。

---

## 前端数据对接任务

### Task 5.7-FE: Dashboard.vue 数据对接

**Files:**
- Modify: `apps/web-admin/src/pages/Dashboard.vue`（`<script>` only）
- Create: `apps/web-admin/src/services/metricsApi.ts`
- Create: `apps/web-admin/src/composables/useMetrics.ts`

**工作内容：**
1. 创建 `metricsApi.ts`：封装 `/admin/metrics/*` 接口调用
2. 创建 `useMetrics.ts`：时间窗筛选状态（今天/昨天/近7天/近30天/自定义）+ 轮询逻辑
3. 在 Dashboard.vue `<script>` 中替换硬编码 SVG 数据为 API 数据：
   - 实时数字卡片（DAU/在线/昨日成本/平均延迟）→ `/admin/metrics/realtime`（每 10s 轮询）
   - 趋势图（访问/留存/主题/性能/成本/健康）→ `/admin/metrics/daily` + `/topics` + `/cost`（每 60s 或时间窗切换时拉取）
   - 6 张 SVG 图的数据绑定从硬编码常量切换为响应式 API 数据
4. 数据导出按钮 → `/admin/metrics/export`（UTF-8 BOM CSV）

**验证：** 启动全栈 → Dashboard 显示真实 API 数据 → 切换时间窗图表刷新 → 导出 CSV 可用。

---

## 🚦 Validation Gates

### G-5.1 · 数据正确性
- 造 10 万条事件 → 聚合 → 5 个核心指标手工对比，误差 ≤ 1%（DAU 允许 ≤ 1.5%）。

### G-5.2 · 主题分布可用性
- 100 条消息人工打标，准确率 ≥ 70%，"其他"占比 ≤ 30%。

### G-5.3 · 看板性能与可用性
- Dashboard 首屏 ≤ 2s；时间窗切换刷新 ≤ 1.5s；实时数字 10s 轮询无跳变。

---

## 完成状态

Phase 5 完成 ⇔ G-5.1 / 5.2 / 5.3 全部 passed。

## Revision 2026-06-02

- **移除 T5.7/T5.8/T5.9 前端看板构建任务**（DashboardPage 实装 + 6 张图组件 + CSV 导出 UI）—— 看板 UI 已全部完成（手写 SVG 方式）。
- **新增 T5.7-FE**（Dashboard.vue SVG 数据对接）—— 将硬编码数据切换为 API 调用。
- 图表使用手写 SVG（非 ECharts，不回退）。
- Dashboard 三视图内联模式（非组件拆分，不回退）。
