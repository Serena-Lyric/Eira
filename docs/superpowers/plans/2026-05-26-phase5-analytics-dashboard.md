---
name: 2026-05-26-phase5-analytics-dashboard
title: Phase 5 · 运营埋点 + 聚合 + 看板
date: 2026-05-26
status: draft
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
overview: docs/superpowers/plans/2026-05-26-overview.md
prev: docs/superpowers/plans/2026-05-26-phase4-admin-persona.md
---

# Phase 5 实施计划 · 运营埋点 + 聚合 + 看板

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Phase 1-4 已经埋下的"日志事件"沉淀成可查询的运营指标，给管理后台中栏/右栏铺满 6 张看板：访问 / 留存 / 主题分布 / 性能 / 成本 / 系统健康。日聚合任务 + 实时统计接口 + ECharts 前端图表。指标先粗后细，先正确性后美观度。

**Architecture:**
- **事件源**：Phase 1 的 `chat_session/chat_message`、Phase 1.11 的 LLM 调用日志、Phase 2 的 retrieve 日志、Phase 3 的 ASR/TTS 日志、Phase 4 的 audit_log。**不**新增大量埋点表；以现有结构化日志（structlog → loki/promtail 或直接落 PG `app_event` 表）为主。
- **聚合**：每日凌晨 03:30 跑 Celery 周期任务（沿用 Phase 3.14 的 worker 架构），把上一日数据写入 `metric_daily` / `topic_daily` / `cost_daily` 等聚合表，看板查聚合表（毫秒级），不实时扫原表。
- **实时**：当日数据走 Redis 计数器（`metrics:dau:YYYYMMDD` set / `metrics:msg_count:YYYYMMDD` int），每次会话/消息更新；DAU 用 HyperLogLog (PFADD) 估算。
- **看板**：`web-admin` 仪表盘页 + 中栏 = 6 张图（访问 / 留存 / 主题 / 性能 / 成本 / 健康），右栏 = 实时数字（DAU / 在线 / 昨日成本 / 平均响应延迟）。

**Tech Stack:** Celery beat + worker（沿用 Phase 3.14）、`apache-superset` 不引入（自建够用）、ECharts 5、`pandas` 仅在 worker 中按需引入做聚合（避免 backend 也加 pandas 拖慢冷启动）。

**前置条件：** Phase 0/1/2/3/4 全部 Validation Gate passed。

**本 Phase 不做：** 自定义图表/拖拽看板（YAGNI）；外部 BI 接入；告警规则系统（仅看板，告警留 Phase 7+）。

**重述全局约定：** TDD；commit 前缀；密钥不入库；聚合任务幂等可重跑；数据保留期默认 365 天（聚合表）+ 90 天（明细日志），spec 锁定。

---

## 任务依赖图

```
T5.1 app_event 表 + 标准事件 schema
  ↓
T5.2 事件写入封装（emit 工具 + 关键节点接入）
  ↓
T5.3 聚合表 schema（metric_daily / topic_daily / cost_daily）+ 迁移 0009
  ↓
T5.4 Celery beat 每日聚合任务（含主题聚类）
  ↓
T5.5 Redis 实时计数器 + 在线连接数
  ↓
T5.6 后端 metrics REST 接口（带粒度 day/week 与时间窗）
  ↓
T5.7 前端看板页（DashboardPage 真正实装）
  ↓
T5.8 6 张图组件（访问 / 留存 / 主题 / 性能 / 成本 / 健康）
  ↓
T5.9 数据导出 CSV
  ↓
🚦 G-5.1 / G-5.2 / G-5.3
```

---

## Task 5.1: app_event 表 + 标准事件 schema

**Files:**
- Create: `backend/app/infra/alembic/versions/0009_app_event.py`
- Create: `backend/app/domain/analytics/models.py`
- Create: `backend/app/domain/analytics/event_schema.py`
- Create: `backend/tests/unit/test_event_schema.py`

迁移：

```python
op.create_table(
    "app_event",
    sa.Column("id", sa.BigInteger, primary_key=True),
    sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
    sa.Column("user_id", sa.BigInteger, nullable=True),
    sa.Column("session_id", sa.BigInteger, nullable=True),
    sa.Column("kind", sa.String(64), nullable=False),
    sa.Column("provider", sa.String(64), nullable=True),
    sa.Column("model", sa.String(64), nullable=True),
    sa.Column("latency_ms", sa.Integer, nullable=True),
    sa.Column("tokens_in", sa.Integer, nullable=True),
    sa.Column("tokens_out", sa.Integer, nullable=True),
    sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True),
    sa.Column("status", sa.String(16), nullable=True),  # ok/error
    sa.Column("error_code", sa.String(64), nullable=True),
    sa.Column("attrs_json", sa.JSON, nullable=True),
)
op.create_index("ix_event_ts", "app_event", ["ts"])
op.create_index("ix_event_kind_ts", "app_event", ["kind", "ts"])
op.create_index("ix_event_user_ts", "app_event", ["user_id", "ts"])
```

> ⚠️ **要点**：
> - 标准事件 `kind`（白名单）：
>   - `chat.session_open / chat.session_close`
>   - `chat.user_message / chat.assistant_message`
>   - `llm.call`（带 model/tokens/cost/latency）
>   - `embedding.call`
>   - `retrieve.kb / retrieve.web`
>   - `asr.session / tts.synthesis`
>   - `error.captured`
> - 不在白名单的 kind 直接拒写并告警，避免野生事件污染聚合。
> - 表是「事件流原表」，不做强外键（`user_id/session_id` 仅为 BigInt）；保留 90 天，超期由聚合任务尾随删除。

- [ ] **Step 1: 失败测试**

```python
# tests/unit/test_event_schema.py
import pytest
from app.domain.analytics.event_schema import validate_event, ALLOWED_KINDS

def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        validate_event({"kind": "weird.thing", "ts": "2026-05-26T10:00:00Z"})

def test_llm_call_requires_provider_model():
    with pytest.raises(ValueError):
        validate_event({"kind": "llm.call", "ts": "2026-05-26T10:00:00Z"})

def test_llm_call_ok():
    e = validate_event({"kind": "llm.call", "ts": "2026-05-26T10:00:00Z",
                        "provider": "deepseek", "model": "deepseek-chat",
                        "tokens_in": 100, "tokens_out": 200, "latency_ms": 800,
                        "cost_usd": 0.0008, "status": "ok"})
    assert e["kind"] == "llm.call"
```

- [ ] **Step 2/3: 实现 + 运行 + 提交**

提交：`infra(analytics): app_event table and event schema`。

---

## Task 5.2: 事件写入封装 + 关键节点接入

**Files:**
- Create: `backend/app/domain/analytics/emitter.py`
- Modify: `backend/app/orchestrator/nodes/llm_call.py`（写 `llm.call`）
- Modify: `backend/app/orchestrator/nodes/retrieve_kb.py`（写 `retrieve.kb`）
- Modify: `backend/app/orchestrator/nodes/web_search.py`（写 `retrieve.web`）
- Modify: `backend/app/api/ws/chat.py`（写 session_open/close、user_message、assistant_message）
- Modify: `backend/app/api/ws/voice.py`（写 asr.session、tts.synthesis）
- Modify: `backend/app/capabilities/embedding/openai.py`（写 `embedding.call`）

```python
# domain/analytics/emitter.py
from .event_schema import validate_event
from app.infra.db import async_session
from .models import AppEvent

class Emitter:
    def __init__(self, session_factory=async_session): self._sf = session_factory
    async def emit(self, **kwargs):
        e = validate_event(kwargs)
        async with self._sf() as s:
            s.add(AppEvent(**e)); await s.commit()
emitter = Emitter()
```

> ⚠️ **要点**：
> - **不阻塞主路径**：emit 走 fire-and-forget — `asyncio.create_task(emitter.emit(...))`；失败仅 log warn，不影响业务。
> - 高频事件（`llm.call` / `embedding.call`）走批量队列：内存累积 50 条或 2s flush 一次（`AsyncBatcher` 实现），减小 PG 压力。
> - 错误事件（`error.captured`）携带 `error_code` 与去敏 stack（截前 500 字符），用于 G-5.3。

- [ ] **Step 1: 失败测试**

```python
@pytest.mark.asyncio
async def test_llm_node_emits_event(graph_runner, fake_emitter, mock_llm):
    await graph_runner.run(user_text="你好")
    kinds = [e["kind"] for e in fake_emitter.events]
    assert "llm.call" in kinds
    llm_e = next(e for e in fake_emitter.events if e["kind"] == "llm.call")
    assert llm_e["model"] and llm_e["latency_ms"] >= 0
```

- [ ] **Step 2/3: 实现 + 运行 + 提交**

提交：`feat(analytics): event emitter wired into orchestrator and ws layer`。

---

## Task 5.3: 聚合表 schema + 迁移 0010

**Files:**
- Create: `backend/app/infra/alembic/versions/0010_metric_daily.py`
- Create: `backend/app/domain/analytics/schemas.py`

```python
op.create_table(
    "metric_daily",
    sa.Column("d", sa.Date, primary_key=True),
    sa.Column("dau", sa.Integer, nullable=False, server_default="0"),
    sa.Column("new_users", sa.Integer, nullable=False, server_default="0"),
    sa.Column("sessions", sa.Integer, nullable=False, server_default="0"),
    sa.Column("messages", sa.Integer, nullable=False, server_default="0"),
    sa.Column("voice_sessions", sa.Integer, nullable=False, server_default="0"),
    sa.Column("retrieve_kb_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("retrieve_web_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("p50_first_token_ms", sa.Integer, nullable=True),
    sa.Column("p95_first_token_ms", sa.Integer, nullable=True),
    sa.Column("p50_voice_e2e_ms", sa.Integer, nullable=True),
    sa.Column("p95_voice_e2e_ms", sa.Integer, nullable=True),
    sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
)

op.create_table(
    "topic_daily",
    sa.Column("d", sa.Date, nullable=False),
    sa.Column("topic", sa.String(64), nullable=False),
    sa.Column("count", sa.Integer, nullable=False),
    sa.PrimaryKeyConstraint("d", "topic"),
)

op.create_table(
    "cost_daily",
    sa.Column("d", sa.Date, nullable=False),
    sa.Column("provider", sa.String(64), nullable=False),
    sa.Column("model", sa.String(64), nullable=False),
    sa.Column("kind", sa.String(64), nullable=False),  # llm/embedding/asr/tts/search
    sa.Column("calls", sa.Integer, nullable=False),
    sa.Column("tokens_in", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("tokens_out", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("cost_usd", sa.Numeric(12, 4), nullable=False, server_default="0"),
    sa.PrimaryKeyConstraint("d", "provider", "model", "kind"),
)
```

> ⚠️ **要点**：
> - 主键即 (date, dim)，幂等：聚合任务用 `INSERT ... ON CONFLICT (...) DO UPDATE`，可重跑某一天而不重复计入。
> - 聚合表保留 365 天（spec 锁定）；`metric_daily` 体积小可永久保留，`topic_daily` 按月清理超期。

提交：`infra(analytics): metric/topic/cost daily tables`。

---

## Task 5.4: Celery beat 每日聚合任务

**Files:**
- Modify: `backend/app/workers/celery_app.py`（追加 beat schedule）
- Create: `backend/app/workers/aggregator.py`
- Create: `backend/app/domain/analytics/topic_classifier.py`
- Create: `backend/tests/unit/test_aggregator.py`
- Create: `backend/tests/integration/test_aggregator_idempotent.py`

> ⚠️ **要点**：
> - Beat schedule：`every day at 03:30`（用户使用低谷期）；任务名 `analytics.aggregate_day(d)`，可手工 `celery call` 重跑某日。
> - 主题分类（轻量）：MVP 用关键词匹配映射成 8 个固定主题：`历史 / 路线 / 票务 / 餐饮 / 厕所 / 拍照 / 设施 / 其他`；规则表见下文，命中多个取第一个。**不引入 LLM 主题聚类**（YAGNI；G-5.2 失败再升级）。
> - `INSERT ... ON CONFLICT` 保证幂等，PG ≥ 12。
> - 性能预算：单日 100 万事件聚合 ≤ 5 分钟；不行就分小时分块聚合。

```python
# topic_classifier.py
TOPIC_RULES: list[tuple[str, list[str]]] = [
    ("票务",   ["门票", "票价", "购票", "checkin", "入园"]),
    ("路线",   ["怎么走", "路线", "导览", "怎么去"]),
    ("历史",   ["历史", "建于", "朝代", "皇帝", "故事"]),
    ("餐饮",   ["吃", "餐厅", "饭店", "小吃", "美食"]),
    ("厕所",   ["厕所", "洗手间", "卫生间", "wc"]),
    ("拍照",   ["拍照", "打卡", "机位", "出片"]),
    ("设施",   ["wifi", "充电", "停车", "母婴", "无障碍"]),
]
def classify(text: str) -> str:
    t = text.lower()
    for topic, kws in TOPIC_RULES:
        if any(kw in t for kw in kws): return topic
    return "其他"
```

聚合任务示意：

```python
# workers/aggregator.py
@celery_app.task(name="analytics.aggregate_day")
def aggregate_day(d_iso: str):
    from datetime import date
    d = date.fromisoformat(d_iso)
    asyncio.run(_aggregate(d))

async def _aggregate(d):
    async with async_session() as s:
        # metric_daily
        r = await s.execute(text(METRIC_SQL), {"d": d})
        await s.execute(text(UPSERT_METRIC_SQL), r.mappings().one())
        # topic_daily（python 端聚合）
        msgs = (await s.execute(text("SELECT attrs_json->>'text' AS text FROM app_event WHERE kind='chat.user_message' AND ts::date = :d"), {"d": d})).scalars().all()
        from collections import Counter
        c = Counter(classify(m or "") for m in msgs)
        for topic, cnt in c.items():
            await s.execute(text(UPSERT_TOPIC_SQL), {"d": d, "topic": topic, "count": cnt})
        # cost_daily
        await s.execute(text(UPSERT_COST_SQL), {"d": d})
        await s.commit()
```

- [ ] **Step 1: 失败测试**

```python
# tests/integration/test_aggregator_idempotent.py
@pytest.mark.asyncio
async def test_aggregate_day_idempotent(test_db):
    await seed_events(date(2026, 5, 25))
    await _aggregate(date(2026, 5, 25))
    snap1 = await read_metric(date(2026, 5, 25))
    await _aggregate(date(2026, 5, 25))  # 第二次重跑
    snap2 = await read_metric(date(2026, 5, 25))
    assert snap1 == snap2  # 完全一致，不重复累加
```

- [ ] **Step 2/3: 实现 + 运行 + 提交**

提交：`feat(analytics): celery beat aggregator with topic rules`。

---

## Task 5.5: Redis 实时计数器 + 在线连接数

**Files:**
- Create: `backend/app/domain/analytics/realtime.py`
- Modify: `backend/app/api/ws/chat.py`（连入/断开时 incr/decr 在线连接）
- Modify: `backend/app/api/ws/voice.py`（同上）
- Create: `backend/tests/unit/test_realtime_counters.py`

```python
# realtime.py
class RealtimeMetrics:
    def __init__(self, redis): self.r = redis
    def _date_key(self): return datetime.utcnow().strftime("%Y%m%d")
    async def mark_active(self, user_id: int):
        await self.r.pfadd(f"metrics:dau:{self._date_key()}", str(user_id))
    async def incr_message(self):
        await self.r.incr(f"metrics:msg:{self._date_key()}")
    async def online_inc(self):
        await self.r.incr("metrics:online")
    async def online_dec(self):
        await self.r.decr("metrics:online")
    async def snapshot(self) -> dict:
        d = self._date_key()
        return {
            "dau_today": await self.r.pfcount(f"metrics:dau:{d}"),
            "msg_today": int(await self.r.get(f"metrics:msg:{d}") or 0),
            "online": int(await self.r.get("metrics:online") or 0),
        }
```

> ⚠️ **要点**：
> - DAU 用 HLL 估算，误差 ≤ 1%，节省内存（百万级 user 也只 12KB）。
> - 在线连接数 = ws 当前 hold 的 user_id 集合大小；进程崩溃时 redis 计数会偏高，加 `key TTL=10min` + 心跳每 5 分钟 `EXPIRE` 续租 ⇒ 异常重启后 10 分钟内自动归零。
> - HLL key TTL 31 天（保留够看周环比即可）；msg 计数 key TTL 7 天。

提交：`feat(analytics): redis realtime counters with hll dau and online gauge`。

---

## Task 5.6: 后端 metrics REST 接口

**Files:**
- Create: `backend/app/api/rest/admin_metrics.py`
- Create: `backend/tests/integration/test_admin_metrics.py`

```
GET /admin/metrics/realtime               # 返回 RealtimeMetrics.snapshot()
GET /admin/metrics/daily?from=&to=        # metric_daily 的列表
GET /admin/metrics/topics?from=&to=&topN= # topic_daily 聚合到时间窗
GET /admin/metrics/cost?from=&to=&groupBy=provider|model|kind
GET /admin/metrics/health                 # 系统健康（pg/redis/oss/celery 队列长度）
GET /admin/metrics/export?metric=daily&from=&to=&format=csv
```

> ⚠️ **要点**：
> - 时间窗最大 365 天；超出 422。
> - `health` 内部对四个依赖跑 1s timeout 探测；任一失败标 `degraded`。
> - 全部接口需 `require_admin`；Phase 5 严禁出现普通用户角色看到这些数据的路径。

- [ ] **Step 1: 失败测试**

```python
@pytest.mark.asyncio
async def test_metrics_daily_window_too_large(client, admin_token):
    r = await client.get("/admin/metrics/daily?from=2024-01-01&to=2026-05-26",
        headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 422

@pytest.mark.asyncio
async def test_metrics_realtime_role_required(client, user_token):
    r = await client.get("/admin/metrics/realtime",
        headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 403
```

- [ ] **Step 2/3: 实现 + 运行 + 提交**

提交：`feat(analytics): admin metrics rest endpoints`。

---

## Task 5.7: 前端 DashboardPage 实装

**Files:**
- Modify: `apps/web-admin/src/pages/DashboardPage.vue`
- Create: `apps/web-admin/src/composables/useMetrics.ts`
- Create: `apps/web-admin/src/services/metricsApi.ts`

> ⚠️ **要点**：
> - 顶部时间窗筛选：「今天 / 昨天 / 近 7 天 / 近 30 天 / 自定义」；切换后所有图同时刷新（pinia + ref 状态）。
> - 实时数字卡片每 10s 轮询 `/admin/metrics/realtime`；其他每 60s 或在筛选切换时拉一次。
> - 图表 hover 联动（同一时间轴上鼠标位置同步）—— 用 ECharts `connect` 把 6 张 chart 串起来。

提交：`feat(admin): dashboard page with shared time-range filter`。

---

## Task 5.8: 6 张图组件

**Files:**
- Create: `apps/web-admin/src/components/charts/TrafficChart.vue`（DAU + 新用户 + 会话）
- Create: `apps/web-admin/src/components/charts/RetentionChart.vue`（次日 / 7 日留存热力图）
- Create: `apps/web-admin/src/components/charts/TopicChart.vue`（饼图 + topN 横向条形）
- Create: `apps/web-admin/src/components/charts/PerfChart.vue`（首 token P50/P95 + 语音 e2e P50/P95）
- Create: `apps/web-admin/src/components/charts/CostChart.vue`（按 provider 堆叠柱）
- Create: `apps/web-admin/src/components/charts/HealthCard.vue`（4 个依赖 ✅/⚠️ + celery 队列长度）

> ⚠️ **要点**：
> - **留存图数据**：MVP 留存计算放在 `aggregate_day` 中：`d` 当天首次活跃的用户集合，再扫 d+1..d+7 是否再次出现，写成 `attrs_json.retain_d1..d7`。复杂留存留 backlog。
> - 性能图三色阈值线：spec 锁定的 KPI（首 token P95 ≤ 2s 文本 / 端到端语音 P95 ≤ 5s）画红线；超过即警示用红色背景 band。
> - 成本图用 `cost_usd` 累计 + 当天 search 调用数；旁边附"昨日成本 ¥X.XX → 同比上周 +X%"小字。

提交：`feat(admin): six dashboard charts with kpi reference lines`。

---

## Task 5.9: 数据导出 CSV

**Files:**
- Modify: `backend/app/api/rest/admin_metrics.py`（实装 export endpoint）
- Modify: `apps/web-admin/src/pages/DashboardPage.vue`（增加导出按钮）

> ⚠️ **要点**：
> - 导出格式：UTF-8 BOM + CSV（Excel 中文能打开）；表头中文。
> - 同步 vs 异步：≤ 90 天数据走同步 `StreamingResponse`；> 90 天 422。
> - 文件名：`eira-metrics-{type}-{from}-{to}.csv`。

提交：`feat(analytics): csv export with utf-8 bom`。

---

## 🚦 Validation Gate G-5.1 · 数据正确性（最关键）

| 项 | 内容 |
|---|---|
| 指标 | 取 1 天真实流量（或脚本造的 1 天事件），手工算 5 个核心指标（DAU / 消息数 / 平均首 token / 总成本 / TopN 主题）→ 对比聚合表 |
| 阈值 | 5 个指标全部误差 ≤ 1%（DAU 因 HLL 允许 ≤ 1.5%） |
| 测试方法 | `scripts/seed_events.py` 造 10 万条事件 → `celery call analytics.aggregate_day` → `scripts/validate_metrics.py` 比对 |
| 数据源 | `docs/superpowers/validations/G-5.1.md` 含 ground truth + 聚合结果对照表 |
| 通过分支 | 进入 G-5.2 |
| 不通过分支 | 误差 1-5%：检查时区（PG 默认 UTC，UI 显示按本地时区会偏移），把聚合 SQL 显式 `at time zone 'Asia/Shanghai'`；> 5%：check 是否漏 emit 节点（再用 grep `await emitter.emit` 数量与节点数对应） |

---

## 🚦 Validation Gate G-5.2 · 主题分布可用性

| 项 | 内容 |
|---|---|
| 指标 | 抽 100 条用户消息人工打标到 8 个主题 → 与规则分类器结果比对 |
| 阈值 | 准确率 ≥ 70%（MVP）；"其他" 类占比 ≤ 30% |
| 测试方法 | 评测脚本 `scripts/topic_eval.py` 输出混淆矩阵 |
| 数据源 | `docs/superpowers/validations/G-5.2.md` 含矩阵 + 误判样例 |
| 通过分支 | 合 |
| 不通过分支 | 准确率 < 70% 或 "其他" 占比 > 50%：(a) 扩关键词表；(b) 把分类器换成 embedding + 聚类（k=8，KMeans）；(c) 仍不行升级到 LLM 主题归纳，写入 spec 修订段；这是该 phase 唯一允许跨阶段的迭代路径 |

---

## 🚦 Validation Gate G-5.3 · 看板性能与可用性

| 项 | 内容 |
|---|---|
| 指标 | (a) DashboardPage 首屏渲染 ≤ 2s；(b) 切换时间窗后图刷新 ≤ 1.5s；(c) 6 张图联动 hover 不卡顿（FPS ≥ 50）；(d) 实时数字 10s 轮询无可见跳变（用 ease 平滑） |
| 阈值 | 4 项全 pass |
| 测试方法 | Playwright + Lighthouse 性能脚本；连续操作 30 个时间窗切换 |
| 数据源 | `docs/superpowers/validations/G-5.3.md` |
| 通过分支 | 合入，标 `gate-G-5-passed`；本 Phase 完成 |
| 不通过分支 | 首屏 > 2s：把 6 张图改 lazy（mounted 时按 IntersectionObserver 加载）；切换 > 1.5s：后端结果加 redis cache TTL=60s（按 from/to/groupBy 做 key）；FPS 卡 → ECharts `progressive` 配置 |

---

## 完成状态

Phase 5 完成 ⇔ G-5.1 / 5.2 / 5.3 全部 passed。运营看板上线，进入 Phase 6 长期记忆 + 情感（与 Phase 5 可重叠时间，按 overview 节奏建议）。
