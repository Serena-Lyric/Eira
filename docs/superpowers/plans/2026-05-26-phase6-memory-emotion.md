---
name: 2026-05-26-phase6-memory-emotion
title: Phase 6 · 长期记忆 + 情感识别
date: 2026-05-26
status: draft
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
overview: docs/superpowers/plans/2026-05-26-overview.md
prev: docs/superpowers/plans/2026-05-26-phase5-analytics-dashboard.md
---

# Phase 6 实施计划 · 长期记忆 + 情感识别

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Eira 能跨会话"记住用户"（爱好、来过的地方、上次没逛完的路线）+ 在对话中"读出情绪"（对失落用户更温柔、对兴奋用户更活泼）。两件事都不影响 MVP 主链路；任何一项异常 → 静默降级到 Phase 5 状态。

**Architecture:**
- **长期记忆**：每次会话结束（ws close 或 30 分钟 idle），后台 Celery 任务跑"记忆抽取" — 调一次便宜模型从 transcript 里抽出 1-N 条「事实卡」（user-fact），存 `memory_fact` 表（含 embedding）。下次同 user 启动会话时，`load_context` 节点从向量库 top-K 召回 + 摘要后塞进 system prompt。
- **情感识别**：在 `safety_in` 之后插入 `emotion_detect` 节点，三选一（多模态难度递增）：
  - L1 文本情感（轻量，基于关键词 + 情感模型，如 `cardiffnlp/twitter-xlm-roberta-base-sentiment` 或国产 `iflytek/erlangshen`）；
  - L2 ASR text + 语音特征（音量/语速）；本 phase 仅做 L1 + L2 的简单融合；
  - L3 表情识别留 Phase 7。
- **回路应用**：识别出的 emotion 写入 ChatState，`llm_call` 节点取出后注入 prompt 模板（`<context source='emotion'>{{user}}'s tone is {{emotion}}</context>`）；同时 `emit chat.emotion` 事件供分析。

**Tech Stack:** 复用 Phase 1/2 LLM Provider；情感模型本地用 `transformers` + ONNX Runtime（CPU 推理 < 100ms）；记忆抽取走 LLM Provider（temperature=0.2 让结构化稳定）。

**前置条件：** Phase 0/1/2/3/4/5 全部 Validation Gate passed；Celery 已上线（Phase 3.14 或 Phase 5 完成时）。

**本 Phase 不做：** 记忆删除/编辑 UI（用户级，留 Phase 7+）；表情识别（图像，Phase 7+ 与图像识别合并做）；记忆冲突合并（多条事实矛盾时本期采用最新覆盖策略，复杂合并留 backlog）。

**重述全局约定：** TDD；commit 前缀；密钥不入库；用户隐私敏感数据（事实卡）默认仅本人可见，admin 端不展示明文，仅展示数量统计；用户可在设置中关闭记忆功能。

---

## 任务依赖图

```
T6.1 memory_fact 表 + 迁移 0011
  ↓
T6.2 记忆抽取 prompt + service
  ↓
T6.3 Celery 任务：会话结束触发抽取
  ↓
T6.4 load_context 节点接入记忆召回
  ↓
T6.5 用户设置：记忆开关 + 隐私说明
  ↓
T6.6 emotion 模型加载 + 推理 service（L1）
  ↓
T6.7 emotion_detect 节点 + state 字段
  ↓
T6.8 LLM prompt 注入情感（结合 persona）
  ↓
T6.9 语音情感融合（L2）—— 仅在 voice 路径生效
  ↓
🚦 G-6.1 / G-6.2 / G-6.3
```

---

## Task 6.1: memory_fact 表 + 迁移 0011

**Files:**
- Create: `backend/app/infra/alembic/versions/0011_memory_fact.py`
- Create: `backend/app/domain/memory/models.py`

```python
op.create_table(
    "memory_fact",
    sa.Column("id", sa.BigInteger, primary_key=True),
    sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
    sa.Column("text", sa.String(512), nullable=False),
    sa.Column("category", sa.String(32), nullable=False),  # preference/visit/plan/identity/other
    sa.Column("source_session_id", sa.BigInteger, nullable=True),
    sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
    sa.Column("embedding", Vector(1536), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("hits", sa.Integer, nullable=False, server_default="0"),
)
op.execute("CREATE INDEX ix_memory_user_emb ON memory_fact USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)")
op.create_index("ix_memory_user_created", "memory_fact", ["user_id", "created_at"])
op.create_check_constraint("ck_memory_category", "memory_fact",
    "category IN ('preference','visit','plan','identity','other')")
```

> ⚠️ **要点**：
> - `text` 限 512 字符（防 prompt 灌水）；`category` 是粗分类便于看板；`expires_at` 用于"短期事实"自动失效（如"明天去十七孔桥"，过期就丢）。
> - `confidence` 用于召回阈值过滤（默认 ≥ 0.5）。
> - **隐私**：admin 端 metrics 仅统计 count，明文不入 audit；用户关闭记忆功能 → 入口直接绕过抽取与召回，且可选「立即删除我的所有记忆」。
> - 用户级 user_id 必填，禁止跨用户召回；service 层强约束。

提交：`infra(memory): memory_fact table with hnsw vector index`。

---

## Task 6.2: 记忆抽取 prompt + service

**Files:**
- Create: `backend/app/domain/memory/service.py`
- Create: `backend/app/domain/memory/prompts.py`
- Create: `backend/tests/unit/test_memory_extractor.py`

抽取 prompt 模板（关键，决定输出质量）：

```
你是 Eira 的记忆助手。请从以下对话中抽取关于"用户本人"的事实，输出 JSON 数组。
每条事实应满足：
1) 关于用户的客观信息或偏好，**不是** Eira 的回复内容；
2) 不重复同义事实；
3) 长度 ≤ 60 个汉字；
4) 标注 category ∈ {preference, visit, plan, identity, other}；
5) 如该事实有时效（如"明天/这周"），给出 ttl_days；否则置为 null；
6) 给出 confidence ∈ [0,1]。

输出 schema（**只输出 JSON 数组，不要包裹任何解释或代码块**）：
[
  {"text":"用户喜欢拍人少的角度","category":"preference","ttl_days":null,"confidence":0.8},
  ...
]

对话：
<<<
{transcript}
>>>
```

service：

```python
class MemoryExtractor:
    def __init__(self, llm: BaseLLM): self.llm = llm
    async def extract(self, transcript: str, user_id: int) -> list[MemoryFactDraft]:
        prompt = MEMORY_PROMPT.format(transcript=transcript[:8000])  # 限上下文
        full = ""
        async for d in self.llm.stream([LlmMessage(role="user", content=prompt)],
                                       model=settings.memory.extract_model,
                                       temperature=0.2):
            full += d.text
        items = _safe_json_array(full)  # 失败返回 []
        out = []
        for it in items[:20]:  # 单次最多 20 条防 LLM 失控
            text = (it.get("text") or "").strip()
            if not text or len(text) > 120: continue
            cat = it.get("category", "other")
            if cat not in {"preference","visit","plan","identity","other"}: cat = "other"
            ttl = it.get("ttl_days")
            expires = (datetime.utcnow() + timedelta(days=int(ttl))) if isinstance(ttl, int) and ttl > 0 else None
            conf = float(it.get("confidence", 0.5))
            out.append(MemoryFactDraft(text=text, category=cat, expires_at=expires, confidence=conf))
        return out
```

> ⚠️ **要点**：
> - **抽取模型用便宜的**（如 `deepseek-chat` 或更小的）：日均会话量大时成本敏感。给到 spec 的成本上限：每会话抽取 ≤ 0.001 USD。
> - JSON 解析失败兜底返回空 `[]` + log warn；不重试（LLM 不稳定时不卡 worker）。
> - 抽取后调 embedding 一次批量（不要 N 次）。
> - 入库前去重：与该用户现有 facts top-3 余弦相似度 > 0.92 视为重复，跳过；高相似度 + 较高 confidence 时**更新 last_used_at**。

- [ ] **Step 1: 失败测试**

```python
@pytest.mark.asyncio
async def test_extract_returns_empty_on_invalid_json(monkeypatch):
    fake_llm = FakeLLM(canned="not valid json")
    ext = MemoryExtractor(fake_llm)
    out = await ext.extract("transcript", user_id=1)
    assert out == []

@pytest.mark.asyncio
async def test_extract_filters_oversized():
    fake_llm = FakeLLM(canned='[{"text":"' + ("x" * 200) + '","category":"preference","confidence":0.8}]')
    out = await MemoryExtractor(fake_llm).extract("t", 1)
    assert out == []
```

- [ ] **Step 2/3: 实现 + 运行 + 提交**

提交：`feat(memory): extractor service with safe json fallback`。

---

## Task 6.3: Celery 任务：会话结束触发抽取

**Files:**
- Modify: `backend/app/api/ws/chat.py`（ws close 时 enqueue）
- Modify: `backend/app/api/ws/voice.py`（同上）
- Create: `backend/app/workers/memory_worker.py`
- Modify: `backend/app/workers/celery_app.py`（注册 task + 定时清理过期 facts）

```python
@celery_app.task(name="memory.extract_session")
def extract_session(session_id: int):
    asyncio.run(_extract(session_id))

async def _extract(session_id):
    async with async_session() as s:
        msgs = await s.execute(select(ChatMessage).where(
            ChatMessage.session_id == session_id).order_by(ChatMessage.id))
        rows = msgs.scalars().all()
        if len(rows) < 4:  # 太短没价值
            return
        sess = await s.get(ChatSession, session_id)
        if not (await user_memory_enabled(s, sess.user_id)):
            return
        transcript = "\n".join(f"{m.role}: {m.content}" for m in rows)
        drafts = await MemoryExtractor(build_llm()).extract(transcript, sess.user_id)
        if not drafts: return
        # 批量 embedding
        vecs = await build_embedding().embed([d.text for d in drafts])
        for d, v in zip(drafts, vecs):
            await maybe_insert(s, sess.user_id, d, v, source_session_id=session_id)
        await s.commit()
```

> ⚠️ **要点**：
> - **触发时机**：ws close（前端关闭/网络断）+ 30 分钟 idle 守护任务（兜底，避免连接泄漏导致没抽取）。
> - 触发后入 celery 队列，`countdown=60s`（用户可能马上重连，等 60s 合并）。
> - **每日清理任务**：`memory.cleanup` 每天 04:00 跑 `DELETE FROM memory_fact WHERE expires_at < now()`。
> - 失败仅 log；该任务不可重试（LLM 抽取重复跑会重复写）。

提交：`feat(memory): celery worker on session close with idle guard`。

---

## Task 6.4: load_context 节点接入记忆召回

**Files:**
- Modify: `backend/app/orchestrator/state.py`（追加 `memory_context: str = ""`，与 Phase 1 的 `persona_prompt / retrieved_chunks` 同级）
- Modify: `backend/app/orchestrator/nodes/load_context.py`
- Modify: `backend/app/orchestrator/nodes/llm_call.py`（prompt 拼装顺序追加 memory_context，见 Task 6.8）
- Create: `backend/app/domain/memory/repository.py`（含 `top_k_for_user`）
- Create: `backend/tests/integration/test_load_context_memory.py`

```python
async def top_k_for_user(s, user_id: int, query_vec, k: int = 5, min_conf=0.5):
    sql = text("""
        SELECT id, text, category, confidence,
               1 - (embedding <=> :qvec) AS score
        FROM memory_fact
        WHERE user_id = :uid
          AND (expires_at IS NULL OR expires_at > now())
          AND confidence >= :mc
        ORDER BY embedding <=> :qvec
        LIMIT :k
    """)
    rows = (await s.execute(sql, {"qvec": list(query_vec), "uid": user_id, "k": k, "mc": min_conf})).mappings().all()
    return [r for r in rows if r["score"] >= 0.4]
```

`load_context` 节点改为：

```python
async def load_context(state: ChatState) -> ChatState:
    if not user_memory_enabled(state.user_id): return state
    qvec = await build_embedding().embed([state.user_text])
    facts = await top_k_for_user(state.db, state.user_id, qvec[0], k=5)
    if facts:
        rendered = "\n".join(f"- {f['text']}" for f in facts)
        state.memory_context = f"<context source='memory'>\n{rendered}\n</context>"
        # 命中即更新 last_used_at + hits
        await mark_hits(state.db, [f["id"] for f in facts])
    return state
```

> ⚠️ **要点**：
> - 召回成本：每次会话首条消息触发一次 embedding；用户后续消息**不再调**（context 在会话期间静态）。
> - 把 memory_context 与 RAG 的 retrieved_chunks 同时塞 prompt：顺序 = `persona → memory_context → kb_context → user_text`，避免长期记忆覆盖事实库。
> - 召回失败（pgvector 不可用）：**降级**为不带记忆继续，不报错给用户。

- [ ] **Step 1: 失败测试 + 实现 + 提交**

```python
@pytest.mark.asyncio
async def test_load_context_injects_memory(test_db, seed_user_with_facts):
    state = ChatState(user_id=seed_user_with_facts.id, user_text="今天去哪好？", db=test_db)
    out = await load_context(state)
    assert out.memory_context and "<context source='memory'>" in out.memory_context
```

提交：`feat(orchestrator): inject long-term memory into context`。

---

## Task 6.5: 用户设置：记忆开关 + 隐私说明

**Files:**
- Modify: `apps/web-user/src/components/SettingsPanel.vue`
- Modify: `backend/app/api/rest/user_preferences.py`
- Create: `backend/app/api/rest/user_memory.py`（删除 / 列表）

设置项：

| 项 | 默认 | 说明 |
|---|---|---|
| 长期记忆 | 开 | 关闭后：不抽取、不召回；UI 提示「关闭后已有记忆仍保留，点'清除全部'立即删除」 |
| 清除全部记忆（按钮） | — | 二次 confirm 后 `DELETE /me/memory`，物理删除 |
| 我的记忆列表 | — | 弹窗显示 text/category/created_at（无 embedding），用户可单条删除 |

> ⚠️ **要点**：
> - 隐私文案（spec 锁定大致措辞）：「Eira 会从我们的对话中提取关于你的偏好和计划，仅用于让对话更连贯。我们不会与第三方分享这些信息。你随时可以查看、编辑或删除。」
> - admin 永远看不到具体 fact text；admin metrics 只统计 count。

提交：`feat(memory): user settings for memory toggle and listing`。

---

## Task 6.6: emotion 模型加载 + 推理 service（L1）

**Files:**
- Create: `backend/app/capabilities/emotion/__init__.py`
- Create: `backend/app/capabilities/emotion/base.py`
- Create: `backend/app/capabilities/emotion/text_onnx.py`
- Create: `backend/app/capabilities/emotion/factory.py`
- Modify: `backend/app/core/config.py`（追加 EmotionSettings 含模型路径）
- Create: `backend/tests/unit/test_emotion_text.py`

> ⚠️ **要点**：
> - **模型选择**：MVP 用 `cardiffnlp/twitter-xlm-roberta-base-sentiment`（多语种 3 类：positive/negative/neutral）→ 转 ONNX；中文专用如 `iflytek/erlangshen`（5 类）作为备选，G-6.2 评测后定。
> - 模型大小 ≤ 300MB；启动加载到内存；CPU 推理 P95 ≤ 100ms（spec 锁定）；GPU 不引入。
> - 输出归一到我们的 5 类：`happy / sad / angry / surprised / neutral`；neutral 是默认；置信度 < 0.55 → 一律 neutral，避免误注入误导 LLM。
> - 接口：`async def detect(text: str) -> EmotionResult{label, confidence, raw: dict}`。

```python
# emotion/text_onnx.py
class TextEmotionOnnx:
    def __init__(self, model_path: str, tokenizer_path: str):
        self.session = onnxruntime.InferenceSession(model_path)
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
        self.label_map = {"LABEL_0": "negative", "LABEL_1": "neutral", "LABEL_2": "positive"}
    async def detect(self, text: str) -> EmotionResult:
        if not text.strip(): return EmotionResult("neutral", 0.0, {})
        inp = self.tokenizer(text, return_tensors="np", truncation=True, max_length=128)
        out = self.session.run(None, {"input_ids": inp["input_ids"], "attention_mask": inp["attention_mask"]})
        scores = softmax(out[0][0])
        idx = int(scores.argmax())
        raw_label = self.label_map[f"LABEL_{idx}"]
        # 映射到 5 类 + 阈值
        mapped = {"positive": "happy", "negative": "sad", "neutral": "neutral"}[raw_label]
        conf = float(scores[idx])
        return EmotionResult(mapped if conf >= 0.55 else "neutral", conf, {"raw": raw_label})
```

- [ ] **Step 1: 失败测试**

```python
def test_text_emotion_short_neutral():
    p = build_emotion("text-onnx")
    r = asyncio.run(p.detect(""))
    assert r.label == "neutral"

def test_text_emotion_basic_positive():
    p = build_emotion("text-onnx")
    r = asyncio.run(p.detect("太棒了！"))
    assert r.label in {"happy", "neutral"}
```

- [ ] **Step 2/3: 实现 + 运行 + 提交**

提交：`feat(emotion): text emotion onnx provider`。

---

## Task 6.7: emotion_detect 节点 + state 字段

**Files:**
- Modify: `backend/app/orchestrator/state.py`（追加 `emotion: EmotionResult | None = None`）
- Create: `backend/app/orchestrator/nodes/emotion_detect.py`
- Modify: `backend/app/orchestrator/graph.py`（在 `safety_in` 之后插入）

```python
async def emotion_detect(state: ChatState) -> ChatState:
    if not settings.emotion.enabled: return state
    try:
        state.emotion = await asyncio.wait_for(
            build_emotion().detect(state.user_text), timeout=0.3)
    except (asyncio.TimeoutError, Exception):
        state.emotion = EmotionResult("neutral", 0.0, {})
    await emitter.emit(kind="chat.emotion", user_id=state.user_id,
                        session_id=state.session_id,
                        attrs_json={"label": state.emotion.label,
                                    "confidence": state.emotion.confidence})
    return state
```

> ⚠️ **要点**：
> - **超时硬上限 300ms**：超过即降级 neutral；emotion 不能拖累首 token 延迟。
> - 失败永远不抛出，只 log；emotion 是"锦上添花"功能，不能拖垮主链路。

提交：`feat(orchestrator): emotion detect node with timeout fallback`。

---

## Task 6.8: LLM prompt 注入情感

**Files:**
- Modify: `backend/app/orchestrator/nodes/llm_call.py`
- Modify: `backend/app/domain/persona/service.py`（追加 `render_emotion_hint`）

```python
EMOTION_TONE_HINT = {
    "happy":     "用户当前情绪愉悦，回复可以更活泼、加入合适的[happy]动作标记。",
    "sad":       "用户当前情绪低落，回复语气温暖、放慢节奏，不要使用感叹号；可加入[nod]动作。",
    "angry":     "用户当前情绪烦躁，先共情、再简洁回答；不要长篇大论。",
    "surprised": "用户当前情绪惊讶，回复可以共鸣这一感受。",
    "neutral":   None,  # 不注入
}

def render_emotion_hint(emotion: EmotionResult | None) -> str:
    if not emotion or emotion.label == "neutral": return ""
    hint = EMOTION_TONE_HINT.get(emotion.label)
    if not hint: return ""
    return f"<context source='emotion'>{hint}</context>"
```

prompt 拼装顺序更新：

```
<persona system_prompt>
<emotion hint>          ← Phase 6 新增
<context source='memory'>...</context>
<context source='kb'>...</context>
<context source='web'>...</context>
user: <user_text>
```

> ⚠️ **要点**：
> - emotion hint 永远在 persona 之后、context 之前，避免被知识库内容淹没。
> - 仍由 persona system_prompt 决定基础人设；emotion 仅微调语气，不能让 Eira 突然变性格。

提交：`feat(orchestrator): inject emotion-tone hint into prompt`。

---

## Task 6.9: 语音情感融合（L2）

**Files:**
- Create: `backend/app/capabilities/emotion/voice_acoustic.py`
- Modify: `backend/app/api/ws/voice.py`（asr.final 后调 acoustic + text 融合）

> ⚠️ **要点**：
> - 声学特征：用 `librosa` / `webrtcvad` 抽 RMS（音量）、speaking_rate（字数/秒）、pitch_std；映射规则：
>   - 高音量 + 快语速 → 偏 happy/angry；
>   - 低音量 + 慢语速 → 偏 sad；
>   - 平均 → neutral。
> - 融合：`final = text_label if text_conf >= 0.7 else acoustic_label`；都低置信度 → neutral。
> - 仅 voice 通道生效；text 路径不引入 librosa（包大）。

提交：`feat(emotion): acoustic feature fusion for voice channel`。

---

## 🚦 Validation Gate G-6.1 · 长期记忆有效性

| 项 | 内容 |
|---|---|
| 指标 | 模拟 5 个用户，每人跑 3 个 session（共 15 个），人工评：第 2/3 个 session 的 Eira 回复是否体现了第 1 个 session 抽出的事实 |
| 阈值 | 命中率 ≥ 60%；无明显错误注入（编造用户没说过的事实） ≥ 95% |
| 测试方法 | 评测脚本 `scripts/memory_eval.py` + 5 名内部测试者打分表 |
| 数据源 | `docs/superpowers/validations/G-6.1.md` 含 15 个会话 transcript + 评分 |
| 通过分支 | 进入 G-6.2 |
| 不通过分支 | 命中率 < 60%：(a) 调召回 k=5→8 + min_conf 0.5→0.4；(b) 改抽取 prompt（few-shot 示例增加）；(c) 切到更强抽取模型；编造率 > 5%：必须立刻禁用记忆功能并查 prompt 模板，可能是抽取出的事实里夹了 Eira 自己的话 |

---

## 🚦 Validation Gate G-6.2 · 情感识别准确性 + 不拖延迟

| 项 | 内容 |
|---|---|
| 指标 | (a) 100 句标注（5 类 × 20 条）的准确率；(b) emotion_detect 节点 P95 耗时 |
| 阈值 | (a) ≥ 65%（5 类 baseline 较难）；(b) ≤ 100ms |
| 测试方法 | `tests/eval/emotion_acc.py` 跑混淆矩阵 + structlog grep 取节点 P95 |
| 数据源 | `docs/superpowers/validations/G-6.2.md` |
| 通过分支 | 进入 G-6.3 |
| 不通过分支 | 准确率 < 65%：换中文专用模型重测；P95 > 100ms：用更小模型（量化 INT8 ONNX）；fp16 GPU 不在本期范围；最差路径 → 关闭 emotion，spec 修订记录"text emotion 暂未达标"，等 Phase 7 与图像情感一起重做 |

---

## 🚦 Validation Gate G-6.3 · 主链路稳定性回归

| 项 | 内容 |
|---|---|
| 指标 | (a) 开启记忆+情感后，文本首 token P95（spec KPI ≤ 2s）回归测试；(b) 端到端语音 P95（spec KPI ≤ 5s）；(c) 关闭记忆/情感开关后回到 Phase 5 baseline 是否一致 |
| 阈值 | (a) ≤ 2.2s（spec 允许 +10%）；(b) ≤ 5.3s（同上）；(c) baseline 差异 ≤ 3% |
| 测试方法 | 复用 G-1.2 / G-3.1 脚本；3 组测试：开+关；样本 ≥ 20/组 |
| 数据源 | `docs/superpowers/validations/G-6.3.md` |
| 通过分支 | 合入，标 `gate-G-6-passed` |
| 不通过分支 | 文本路径回退原因多在 load_context 多调一次 embedding：把"会话首消息触发 + 静态缓存到本会话"逻辑核对；语音路径回退在 emotion 模型 IO 阻塞：emotion 调用必须 `asyncio.to_thread` 跑；超过 +10% 阈值即 spec 修订强制把 emotion 改为「异步事件，不入主 prompt」（事件归档但不影响回复）|

---

## 完成状态

Phase 6 完成 ⇔ G-6.1 / 6.2 / 6.3 全部 passed。Eira 具备"记得你 + 读得出你的情绪"的差异化能力，进入 Phase 7+ 持续扩展。
