---
name: 2026-05-26-phase1-text-chat
title: Phase 1 · 文本对话闭环 + Live2D 画布
date: 2026-05-26
status: draft
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
overview: docs/superpowers/plans/2026-05-26-overview.md
prev: docs/superpowers/plans/2026-05-26-phase0-infra-bootstrap.md
---

# Phase 1 实施计划 · 文本对话闭环 + Live2D 画布

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户登录后可在前端用文本与 Eira 对话；后端通过 LangGraph 编排，调用云 LLM Provider 流式返回；前端在 Live2D 画布上呈现回复。验证门 G-1.x 通过后视为"MVP 文本闭环达标"。

**Architecture:**
- LLM Provider 抽象：默认 DeepSeek（OpenAI 兼容协议）；预留 OpenAI/Tongyi/Volc 适配器。
- Orchestrator：LangGraph 状态图，节点序列：`load_context → safety_in → retrieve(stub) → llm_call → safety_out → persist → emit`。
- 通信：WebSocket `/ws/chat?session_id=...`，消息类型 `user_text / token / done / error / state`。
- Live2D：PixiJS + pixi-live2d-display 渲染 Cubism 4 模型，全屏画布，支持拖拽 + 滚轮缩放（0.3x–3x）。
- 持久化：会话与消息表落 PG，支持后续 Phase 6 抽取记忆。

**Tech Stack:** LangGraph、`openai` SDK（兼容 DeepSeek）、httpx、pgvector（仅建表占位）、PixiJS 7、pixi-live2d-display 0.4、Cubism Web SDK、WebSocket（FastAPI 内置）。

**前置条件：** Phase 0 全部 Validation Gate passed。

**本 Phase 不做：** 真正的 RAG 检索（Phase 2）；ASR/TTS（Phase 3）；情感与长期记忆（Phase 6）；管理后台（Phase 4）。

**重述全局约定：**
- TDD 强制；每 Step 5 提交。
- 所有 Provider 调用走 `capabilities/llm/base.py` 的统一接口；禁止业务模块直接 import openai/deepseek SDK。
- LLM 输入必须用统一分隔符标记后注入 system prompt 模板；用户原始文本不得直接拼接到 prompt。
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
T1.7 前端聊天页骨架（GlassCard 输入框 + 文字气泡）
  ↓
T1.8 Live2D 画布与控件（拖拽/缩放/位置持久化）  ──┐
                                                  │ 与 T1.9 并行可
T1.9 动作标记解析（[wave]/[nod]/[happy]）       ──┘
  ↓
T1.10 待机动作与"思考中"反馈
  ↓
T1.11 节点埋点 + LLM 调用日志
  ↓
🚦 G-1.1 / G-1.2 / G-1.3 / G-1.4
```

---

## Task 1.1: LLM Provider 抽象 + DeepSeek 适配器

**Files:**
- Create: `backend/app/capabilities/__init__.py`
- Create: `backend/app/capabilities/llm/__init__.py`
- Create: `backend/app/capabilities/llm/base.py`
- Create: `backend/app/capabilities/llm/openai_compat.py`
- Create: `backend/app/capabilities/llm/factory.py`
- Modify: `backend/app/core/config.py`（追加 LlmSettings）
- Modify: `backend/pyproject.toml`（加 `openai>=1.30`、`tenacity>=8.2`、`pytest-vcr>=1.0`）
- Create: `backend/tests/unit/test_llm_provider.py`
- Create: `backend/tests/cassettes/test_deepseek_chat.yaml`（VCR 录制后产生）

> ⚠️ **要点**：
> - 适配器返回 `AsyncIterator[LlmDelta]`，业务代码用 `async for` 消费；非流式路径在内部把 stream collect 成 string 返回。
> - 失败重试：网络错误指数退避 3 次（tenacity）；429（限流）退避 + 抖动；4xx 不重试；5xx 重试 2 次。
> - 调用日志字段：`provider/model/prompt_tokens/completion_tokens/cost_estimate/latency_ms/request_id`。
> - `cost_estimate` 通过 `pricing.yaml` 表查得（输入/输出每 1K token 单价），未配置时为 `null`。

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_llm_provider.py`:

```python
import pytest
from app.capabilities.llm.base import LlmMessage
from app.capabilities.llm.factory import build_llm

@pytest.mark.vcr
@pytest.mark.asyncio
async def test_deepseek_chat_stream_collects_text():
    llm = build_llm("deepseek-chat")
    msgs = [LlmMessage(role="system", content="You are a tour guide."),
            LlmMessage(role="user", content="一句话介绍颐和园。")]
    chunks: list[str] = []
    async for delta in llm.stream(messages=msgs, max_tokens=120, temperature=0.7):
        chunks.append(delta.content_delta or "")
    assert "".join(chunks).strip()  # 非空回复

def test_factory_unknown_model_raises():
    with pytest.raises(ValueError):
        build_llm("no-such-model")
```

- [ ] **Step 2: 验证失败**

```
cd backend && uv run pytest tests/unit/test_llm_provider.py -v
```

预期：FAIL（模块缺失）。

- [ ] **Step 3: 配置 + 实现**

修改 `app/core/config.py`，追加：

```python
class LlmModelConfig(BaseModel):
    provider: str           # openai_compat | openai | tongyi | mock
    base_url: str
    api_key_env: str        # 环境变量名，避免直接落盘
    model_id: str
    pricing_in_per_1k: float | None = None
    pricing_out_per_1k: float | None = None

class LlmSettings(BaseModel):
    default_model: str = "deepseek-chat"
    timeout_seconds: int = 60
    models: dict[str, LlmModelConfig] = {
        "deepseek-chat": LlmModelConfig(
            provider="openai_compat",
            base_url="https://api.deepseek.com/v1",
            api_key_env="EIRA_LLM_DEEPSEEK_KEY",
            model_id="deepseek-chat",
        ),
        "mock": LlmModelConfig(
            provider="mock", base_url="", api_key_env="", model_id="mock",
        ),
    }
```

`Settings` 中追加 `llm: LlmSettings = LlmSettings()`。

`backend/app/capabilities/llm/base.py`:

```python
from dataclasses import dataclass, field
from typing import AsyncIterator, Literal, Protocol

@dataclass
class LlmMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str

@dataclass
class LlmDelta:
    content_delta: str | None = None
    finish_reason: str | None = None
    usage: dict | None = None  # {prompt_tokens, completion_tokens}

@dataclass
class LlmCallMeta:
    provider: str
    model: str
    latency_ms: int = 0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_estimate: float | None = None
    request_id: str | None = None

class LlmProvider(Protocol):
    name: str
    async def stream(self, messages: list[LlmMessage], *,
                     max_tokens: int = 1024, temperature: float = 0.7,
                     stop: list[str] | None = None) -> AsyncIterator[LlmDelta]: ...
```

`backend/app/capabilities/llm/openai_compat.py`:

```python
import os
import time
from typing import AsyncIterator
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type
from .base import LlmMessage, LlmDelta

class OpenAiCompatProvider:
    name = "openai_compat"

    def __init__(self, base_url: str, api_key_env: str, model_id: str, timeout: int = 60):
        api_key = os.environ.get(api_key_env, "")
        if not api_key:
            raise RuntimeError(f"missing api key env: {api_key_env}")
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self._model = model_id

    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential_jitter(initial=0.5, max=4),
           retry=retry_if_exception_type(Exception),
           reraise=True)
    async def stream(self, messages: list[LlmMessage], *,
                     max_tokens: int = 1024, temperature: float = 0.7,
                     stop: list[str] | None = None) -> AsyncIterator[LlmDelta]:
        start = time.monotonic()
        oa = self._client
        resp = await oa.chat.completions.create(
            model=self._model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=max_tokens, temperature=temperature, stream=True,
            stop=stop,
        )
        usage = None
        finish = None
        async for chunk in resp:
            choice = chunk.choices[0] if chunk.choices else None
            if not choice: continue
            delta_text = (choice.delta.content or "") if choice.delta else ""
            finish = choice.finish_reason or finish
            yield LlmDelta(content_delta=delta_text, finish_reason=None)
        latency_ms = int((time.monotonic() - start) * 1000)
        yield LlmDelta(content_delta="", finish_reason=finish or "stop",
                       usage={"latency_ms": latency_ms, **(usage or {})})
```

`backend/app/capabilities/llm/factory.py`:

```python
from app.core.config import get_settings
from .openai_compat import OpenAiCompatProvider
from .base import LlmProvider

def build_llm(model_key: str | None = None) -> LlmProvider:
    s = get_settings().llm
    key = model_key or s.default_model
    if key not in s.models:
        raise ValueError(f"unknown llm model: {key}")
    cfg = s.models[key]
    if cfg.provider == "openai_compat":
        return OpenAiCompatProvider(cfg.base_url, cfg.api_key_env, cfg.model_id, s.timeout_seconds)
    if cfg.provider == "mock":
        from .mock import MockProvider
        return MockProvider()
    raise ValueError(f"provider not implemented: {cfg.provider}")
```

`backend/app/capabilities/llm/mock.py`:

```python
from typing import AsyncIterator
from .base import LlmMessage, LlmDelta

class MockProvider:
    name = "mock"
    async def stream(self, messages: list[LlmMessage], **kw) -> AsyncIterator[LlmDelta]:
        text = "你好，我是测试用 Eira。"
        for ch in text:
            yield LlmDelta(content_delta=ch)
        yield LlmDelta(finish_reason="stop", usage={"latency_ms": 5})
```

`backend/tests/conftest.py` 追加 vcr 配置：

```python
import pytest

@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": ["authorization", "api-key", "x-api-key"],
        "record_mode": "once",
    }
```

加依赖并 `uv sync --extra dev`。

- [ ] **Step 4: 录 VCR / 验证通过**

```
EIRA_LLM_DEEPSEEK_KEY=sk-real-key uv run pytest tests/unit/test_llm_provider.py -v
```

第一次跑会真实请求并产生 cassette。**重要**：commit 前确认 `tests/cassettes/*.yaml` 中无明文 key（VCR 已 filter）。

- [ ] **Step 5: 提交**

```
git add backend/
git commit -m "feat(llm): provider abstraction with deepseek (openai-compat) adapter"
```

> ⚠️ **注意**：`pricing.yaml` 表与 cost 计算可放到 T1.11 一并落地；本任务不阻塞。

---

## Task 1.2: Orchestrator 状态机骨架

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

- [ ] **Step 1: 写失败测试**

`backend/tests/integration/test_orchestrator_smoke.py`:

```python
import pytest
from app.orchestrator.graph import build_graph
from app.orchestrator.state import ChatState

@pytest.mark.asyncio
async def test_graph_runs_with_mock_llm():
    graph = build_graph(llm_model_key="mock")
    state = ChatState(session_id="s-test", user_id=1,
                      user_text="你好", history=[], persona_id=None)
    final_text = ""
    async for event in graph.astream(state):
        if event.get("emit", {}).get("token"):
            final_text += event["emit"]["token"]
    assert "Eira" in final_text or "你好" in final_text
```

- [ ] **Step 2: 验证失败**

预期：FAIL。

- [ ] **Step 3: 实现**

`backend/app/orchestrator/state.py`:

```python
from dataclasses import dataclass, field
from typing import Literal, TypedDict

class HistoryItem(TypedDict):
    role: Literal["user", "assistant"]
    content: str

@dataclass
class ChatState:
    session_id: str
    user_id: int
    user_text: str
    history: list[HistoryItem] = field(default_factory=list)
    persona_id: int | None = None
    persona_prompt: str = ""
    retrieved_chunks: list[str] = field(default_factory=list)
    safety_in_ok: bool = True
    safety_out_ok: bool = True
    llm_text: str = ""
    llm_meta: dict = field(default_factory=dict)
    error: str | None = None
```

`backend/app/orchestrator/nodes/load_context.py`:

```python
from ..state import ChatState

async def load_context(state: ChatState) -> dict:
    if not state.persona_prompt:
        state.persona_prompt = (
            "你是 Eira，一名温柔有礼的景区数字导游。回答精炼准确，"
            "不知道时坦然告知，不臆造事实。"
        )
    return {"state": state}
```

`backend/app/orchestrator/nodes/llm_call.py`:

```python
from app.capabilities.llm.factory import build_llm
from app.capabilities.llm.base import LlmMessage
from ..state import ChatState

def _build_messages(state: ChatState) -> list[LlmMessage]:
    sys = state.persona_prompt
    if state.retrieved_chunks:
        ctx = "\n".join(f"<context>{c}</context>" for c in state.retrieved_chunks)
        sys += f"\n\n参考资料：\n{ctx}"
    msgs = [LlmMessage(role="system", content=sys)]
    for h in state.history[-10:]:
        msgs.append(LlmMessage(role=h["role"], content=h["content"]))
    msgs.append(LlmMessage(role="user", content=f"<user>{state.user_text}</user>"))
    return msgs

async def llm_call(state: ChatState, *, model_key: str = "deepseek-chat",
                   emit_token=None) -> dict:
    llm = build_llm(model_key)
    text = ""
    async for delta in llm.stream(messages=_build_messages(state),
                                   max_tokens=600, temperature=0.7):
        if delta.content_delta:
            text += delta.content_delta
            if emit_token:
                await emit_token(delta.content_delta)
        if delta.finish_reason:
            state.llm_meta = delta.usage or {}
    state.llm_text = text
    return {"state": state}
```

`backend/app/orchestrator/nodes/persist.py`:

```python
from ..state import ChatState

async def persist(state: ChatState) -> dict:
    # phase 1 暂留 stub；T1.3 完成后接入仓储
    return {"state": state}
```

`backend/app/orchestrator/nodes/emit.py`:

```python
from ..state import ChatState

async def emit(state: ChatState) -> dict:
    return {"state": state, "emit": {"final": state.llm_text}}
```

`backend/app/orchestrator/graph.py`:

```python
from typing import Awaitable, Callable
from langgraph.graph import StateGraph, END
from .state import ChatState
from .nodes.load_context import load_context
from .nodes.llm_call import llm_call
from .nodes.persist import persist
from .nodes.emit import emit

def build_graph(llm_model_key: str = "deepseek-chat",
                emit_token: Callable[[str], Awaitable[None]] | None = None):
    sg = StateGraph(ChatState)

    async def _llm(s: ChatState):
        return await llm_call(s, model_key=llm_model_key, emit_token=emit_token)

    sg.add_node("load_context", load_context)
    sg.add_node("llm_call", _llm)
    sg.add_node("persist", persist)
    sg.add_node("emit", emit)

    sg.set_entry_point("load_context")
    sg.add_edge("load_context", "llm_call")
    sg.add_edge("llm_call", "persist")
    sg.add_edge("persist", "emit")
    sg.add_edge("emit", END)
    return sg.compile()
```

加依赖 `langgraph>=0.2` 到 `pyproject.toml`，`uv sync --extra dev`。

- [ ] **Step 4: 验证通过**

```
uv run pytest tests/integration/test_orchestrator_smoke.py -v
```

预期：1 passed。

- [ ] **Step 5: 提交**

```
git add backend/
git commit -m "feat(orchestrator): langgraph state machine skeleton with mock llm"
```

---

## Task 1.3: Conversation 领域（会话/消息）

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
- Modify: `backend/app/orchestrator/nodes/persist.py`（接入服务）

- [ ] **Step 1: 迁移**

`backend/app/infra/alembic/versions/0003_conversation_tables.py`:

```python
"""conversation tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "chat_session",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("persona_id", sa.BigInteger, nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_chat_session_user_id", "chat_session", ["user_id"])

    op.create_table(
        "chat_message",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.BigInteger,
                  sa.ForeignKey("chat_session.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("audio_oss_key", sa.String(255), nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_chat_message_session", "chat_message", ["session_id", "id"])
    op.create_check_constraint("ck_chat_message_role", "chat_message",
                               "role IN ('user','assistant','system')")

def downgrade() -> None:
    op.drop_table("chat_message")
    op.drop_table("chat_session")
```

执行 `uv run alembic upgrade head`。

- [ ] **Step 2: 写失败测试**

`backend/tests/integration/test_conversation.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_create_session_and_list(register_and_login):
    token = await register_and_login("c1@x.com", "Passw0rd!")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        h = {"Authorization": f"Bearer {token}"}
        r = await c.post("/conversations", json={"title": "首会话"}, headers=h)
        assert r.status_code == 201, r.text
        sid = r.json()["id"]
        r = await c.get("/conversations", headers=h)
        assert any(s["id"] == sid for s in r.json()["items"])
        r = await c.get(f"/conversations/{sid}/messages", headers=h)
        assert r.status_code == 200 and r.json()["items"] == []
```

`backend/tests/conftest.py` 追加 fixture：

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
def register_and_login():
    transport = ASGITransport(app=app)
    async def _do(email: str, pwd: str) -> str:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            await c.post("/auth/register", json={"email": email, "password": pwd})
            r = await c.post("/auth/login", json={"email": email, "password": pwd})
            return r.json()["access_token"]
    return _do
```

- [ ] **Step 3: 验证失败**

预期：FAIL。

- [ ] **Step 4: 实现**

`backend/app/domain/conversation/models.py`、`repository.py`、`service.py` 按 Phase 0 identity 模板编写。**关键 schema**：

```python
# schemas.py
from pydantic import BaseModel
from datetime import datetime

class SessionCreateIn(BaseModel):
    title: str | None = None
    persona_id: int | None = None

class SessionOut(BaseModel):
    id: int
    title: str | None
    persona_id: int | None
    created_at: datetime
    ended_at: datetime | None

class SessionListOut(BaseModel):
    items: list[SessionOut]
    total: int

class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    audio_oss_key: str | None = None
    created_at: datetime

class MessageListOut(BaseModel):
    items: list[MessageOut]
    total: int
```

`backend/app/api/rest/conversations.py`:

```python
from fastapi import APIRouter, Depends, status
from app.core.deps import get_current_user, get_db_session
from app.domain.identity.models import User
from app.domain.conversation.service import ConversationService
from app.domain.conversation.repository import ConversationRepository
from app.domain.conversation.schemas import (
    SessionCreateIn, SessionOut, SessionListOut, MessageListOut)

router = APIRouter(prefix="/conversations", tags=["conversation"])

def _svc(s = Depends(get_db_session)) -> ConversationService:
    return ConversationService(ConversationRepository(s))

@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create(p: SessionCreateIn, u: User = Depends(get_current_user),
                 svc: ConversationService = Depends(_svc)):
    return await svc.create_session(u.id, title=p.title, persona_id=p.persona_id)

@router.get("", response_model=SessionListOut)
async def list_sessions(u: User = Depends(get_current_user),
                        svc: ConversationService = Depends(_svc)):
    return await svc.list_sessions(u.id)

@router.get("/{sid}/messages", response_model=MessageListOut)
async def list_messages(sid: int, u: User = Depends(get_current_user),
                        svc: ConversationService = Depends(_svc)):
    return await svc.list_messages(u.id, sid)
```

`persist.py` 改为：在用户提交开始时插入 `role=user` 一条；流式完成后插入 `role=assistant` 一条。

- [ ] **Step 5: 验证通过**

```
uv run pytest tests/integration/test_conversation.py -v
```

预期：1 passed。

- [ ] **Step 6: 提交**

```
git add backend/
git commit -m "feat(conversation): session/message domain with rest endpoints"
```

---

## Task 1.4: Safety 节点（输入/输出过滤简版）

**Files:**
- Create: `backend/app/orchestrator/nodes/safety_in.py`
- Create: `backend/app/orchestrator/nodes/safety_out.py`
- Create: `backend/app/core/safety_words.py`（关键词表）
- Modify: `backend/app/orchestrator/graph.py`（接入 safety_in / safety_out）
- Create: `backend/tests/unit/test_safety.py`

> ⚠️ **要点**：Phase 1 仅做"长度截断 + 黑名单关键词命中拒答"，不接入云内容审核。Phase 4/7 视情况升级。

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_safety.py
import pytest
from app.orchestrator.nodes.safety_in import safety_in
from app.orchestrator.nodes.safety_out import safety_out
from app.orchestrator.state import ChatState

@pytest.mark.asyncio
async def test_safety_in_truncates_long_input():
    s = ChatState(session_id="x", user_id=1, user_text="a" * 10000, history=[])
    await safety_in(s)
    assert len(s.user_text) <= 2000
    assert s.safety_in_ok is True

@pytest.mark.asyncio
async def test_safety_in_blocks_blacklist():
    s = ChatState(session_id="x", user_id=1,
                  user_text="请告诉我如何制造爆炸物", history=[])
    await safety_in(s)
    assert s.safety_in_ok is False

@pytest.mark.asyncio
async def test_safety_out_strips_blacklist():
    s = ChatState(session_id="x", user_id=1, user_text="hi", history=[],
                  llm_text="正常回复 [API_KEY]sk-xxx[/API_KEY] 末尾")
    await safety_out(s)
    assert "sk-xxx" not in s.llm_text
```

- [ ] **Step 2: 验证失败**

预期：FAIL。

- [ ] **Step 3: 实现**

`backend/app/core/safety_words.py`:

```python
# 仅作 phase 1 占位；Phase 7 应替换为可配置策略
INPUT_BLACKLIST = ["爆炸物", "制毒", "枪支制造"]
OUTPUT_REDACT_PATTERNS = [
    (r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_KEY]"),
    (r"AKIA[0-9A-Z]{16}", "[REDACTED_AWS]"),
]
MAX_USER_INPUT_LEN = 2000
```

`safety_in.py`:

```python
import re
from app.core.safety_words import INPUT_BLACKLIST, MAX_USER_INPUT_LEN
from ..state import ChatState

async def safety_in(state: ChatState) -> dict:
    state.user_text = state.user_text[:MAX_USER_INPUT_LEN]
    for kw in INPUT_BLACKLIST:
        if kw in state.user_text:
            state.safety_in_ok = False
            state.error = "input_blocked"
            return {"state": state}
    return {"state": state}
```

`safety_out.py`:

```python
import re
from app.core.safety_words import OUTPUT_REDACT_PATTERNS
from ..state import ChatState

async def safety_out(state: ChatState) -> dict:
    text = state.llm_text
    for pat, rep in OUTPUT_REDACT_PATTERNS:
        text = re.sub(pat, rep, text)
    state.llm_text = text
    return {"state": state}
```

修改 `graph.py` 节点链：`load_context → safety_in → llm_call → safety_out → persist → emit`，并在 `safety_in` 失败时短路至 `emit` 并写入兜底回复："抱歉，我无法回答此问题。"

- [ ] **Step 4: 验证通过 + 提交**

```
uv run pytest tests/unit/test_safety.py -v
git add backend/
git commit -m "feat(orchestrator): basic input/output safety nodes"
```

---

## Task 1.5: WebSocket 协议与 /ws/chat

**Files:**
- Create: `backend/app/api/ws/__init__.py`
- Create: `backend/app/api/ws/chat.py`
- Create: `backend/app/api/ws/messages.py`（pydantic 消息 schema）
- Modify: `backend/app/main.py`（注册 ws）
- Create: `backend/tests/integration/test_ws_chat.py`

> ⚠️ **协议契约（spec 已锁定）**：
> ```
> client → server:
>   {"type":"user_text","session_id":"...","text":"...","ts":...}
>   {"type":"interrupt"}                      # 预留 phase 3 用
> server → client:
>   {"type":"state","phase":"thinking"}
>   {"type":"token","text":"..."}             # 流式片段
>   {"type":"action","tag":"wave"}            # 见 T1.9
>   {"type":"done","message_id":123,"latency_ms":..., "tokens":{...}}
>   {"type":"error","code":"...","detail":"..."}
> ```

- [ ] **Step 1: 消息 schema**

```python
# api/ws/messages.py
from pydantic import BaseModel, Field
from typing import Literal

class WsUserText(BaseModel):
    type: Literal["user_text"]
    session_id: int
    text: str = Field(min_length=1, max_length=2000)
    ts: float | None = None

class WsInterrupt(BaseModel):
    type: Literal["interrupt"]

class WsServerState(BaseModel):
    type: Literal["state"] = "state"
    phase: Literal["thinking", "speaking", "idle"]

class WsServerToken(BaseModel):
    type: Literal["token"] = "token"
    text: str

class WsServerAction(BaseModel):
    type: Literal["action"] = "action"
    tag: str

class WsServerDone(BaseModel):
    type: Literal["done"] = "done"
    message_id: int
    latency_ms: int
    tokens: dict | None = None

class WsServerError(BaseModel):
    type: Literal["error"] = "error"
    code: str
    detail: str | None = None
```

- [ ] **Step 2: 写失败测试**

```python
# tests/integration/test_ws_chat.py
import json, pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.mark.asyncio
async def test_ws_chat_round_trip(register_and_login_sync):
    token, sid = register_and_login_sync()  # sync helper创建 user + session
    with TestClient(app).websocket_connect(
        f"/ws/chat?token={token}&session_id={sid}&model=mock"
    ) as ws:
        ws.send_json({"type":"user_text","session_id":sid,"text":"你好"})
        events = []
        while True:
            m = ws.receive_json()
            events.append(m)
            if m["type"] == "done":
                break
        kinds = [e["type"] for e in events]
        assert "state" in kinds
        assert any(k == "token" for k in kinds)
        assert kinds[-1] == "done"
```

`conftest.py` 加 `register_and_login_sync` fixture（用 TestClient 同步走完 register/login/createSession）。

- [ ] **Step 3: 验证失败**

预期：FAIL。

- [ ] **Step 4: 实现**

```python
# api/ws/chat.py
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.security import decode_token
from app.core.deps import get_session_factory
from app.domain.conversation.repository import ConversationRepository
from app.domain.conversation.service import ConversationService
from app.orchestrator.graph import build_graph
from app.orchestrator.state import ChatState
from .messages import (WsUserText, WsServerState, WsServerToken,
                       WsServerDone, WsServerError)

router = APIRouter()

@router.websocket("/ws/chat")
async def ws_chat(ws: WebSocket, token: str = Query(...),
                  session_id: int = Query(...), model: str = Query("deepseek-chat")):
    try:
        payload = decode_token(token)
        assert payload.get("kind") == "access"
        user_id = int(payload["sub"])
    except Exception:
        await ws.close(code=4401); return

    await ws.accept()
    factory = get_session_factory()
    async with factory() as db:
        svc = ConversationService(ConversationRepository(db))
        if not await svc.user_owns_session(user_id, session_id):
            await ws.send_json(WsServerError(code="forbidden").model_dump()); await ws.close(); return

        try:
            while True:
                raw = await ws.receive_json()
                if raw.get("type") != "user_text":
                    continue
                msg = WsUserText.model_validate(raw)
                start = time.monotonic()
                await ws.send_json(WsServerState(phase="thinking").model_dump())

                user_msg_id = await svc.append_user_message(user_id, session_id, msg.text)
                history = await svc.fetch_history(session_id, last_n=20)

                async def emit_token(t: str):
                    await ws.send_json(WsServerToken(text=t).model_dump())

                graph = build_graph(llm_model_key=model, emit_token=emit_token)
                state = ChatState(session_id=str(session_id), user_id=user_id,
                                  user_text=msg.text, history=history)

                full_text = ""
                async for event in graph.astream(state):
                    if "emit" in event and "final" in event["emit"]:
                        full_text = event["emit"]["final"]
                if not full_text:
                    full_text = state.llm_text

                assistant_msg_id = await svc.append_assistant_message(
                    session_id, full_text, meta=state.llm_meta)
                await db.commit()
                latency = int((time.monotonic() - start) * 1000)
                await ws.send_json(WsServerDone(
                    message_id=assistant_msg_id, latency_ms=latency,
                    tokens=state.llm_meta).model_dump())
        except WebSocketDisconnect:
            return
        except Exception as e:
            await ws.send_json(WsServerError(code="server_error", detail=str(e)[:200]).model_dump())
            await ws.close()
```

`main.py` 注册：`app.include_router(chat.router)`。

- [ ] **Step 5: 验证通过 + 提交**

```
uv run pytest tests/integration/test_ws_chat.py -v
git add backend/
git commit -m "feat(ws): /ws/chat with langgraph streaming pipeline"
```

> ⚠️ **延伸**：本任务"使用 query string 携带 token"是 WS 简化做法；生产中可换 Sec-WebSocket-Protocol 子协议或 Cookie + CSRF 双检。Phase 4 暴露给公网时再改。

---

## Task 1.6: 流式 token 推送链路自检

**Files:**
- Create: `backend/tests/integration/test_ws_stream_pacing.py`

> 目的：验证 token 帧首响 ≤ 1.2s（mock）/ ≤ 2s（真实 LLM）；token 帧节奏均匀（最大 gap < 800ms）。

- [ ] **Step 1: 写测试**

```python
import time, pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.mark.asyncio
async def test_first_token_latency_mock(register_and_login_sync):
    token, sid = register_and_login_sync()
    t0 = time.monotonic()
    with TestClient(app).websocket_connect(
        f"/ws/chat?token={token}&session_id={sid}&model=mock"
    ) as ws:
        ws.send_json({"type":"user_text","session_id":sid,"text":"你好"})
        first_token_t = None
        while True:
            m = ws.receive_json()
            if m["type"] == "token" and first_token_t is None:
                first_token_t = time.monotonic() - t0
            if m["type"] == "done":
                break
        assert first_token_t is not None and first_token_t < 1.2
```

- [ ] **Step 2/3: 跑 + 提交**

```
uv run pytest tests/integration/test_ws_stream_pacing.py -v
git add backend/tests/
git commit -m "test(ws): first-token latency baseline (mock)"
```

---

## Task 1.7: 前端聊天页骨架

**Files:**
- Modify: `apps/web-user/src/pages/Chat.vue`
- Create: `apps/web-user/src/composables/useChatSession.ts`
- Create: `apps/web-user/src/composables/useWebSocket.ts`
- Modify: `packages/ui-shared/src/components/GlassInput.vue`
- Modify: `apps/web-user/src/services/http.ts`

- [ ] **Step 1: composable 与组件**

`apps/web-user/src/composables/useWebSocket.ts`:

```typescript
import { ref } from "vue"

export function useWebSocket(url: () => string) {
  const ws = ref<WebSocket | null>(null)
  const connected = ref(false)
  const messages = ref<any[]>([])
  function connect() {
    const s = new WebSocket(url())
    s.onopen = () => { connected.value = true }
    s.onclose = () => { connected.value = false }
    s.onmessage = (e) => messages.value.push(JSON.parse(e.data))
    ws.value = s
  }
  function send(payload: any) { ws.value?.send(JSON.stringify(payload)) }
  function close() { ws.value?.close() }
  return { connect, send, close, connected, messages }
}
```

`apps/web-user/src/composables/useChatSession.ts`:

```typescript
import { reactive, ref, computed } from "vue"
import { http } from "../services/http"
import { useWebSocket } from "./useWebSocket"
import { useAuthStore } from "../stores/auth"

export function useChatSession() {
  const auth = useAuthStore()
  const sessionId = ref<number | null>(null)
  const messages = reactive<{role:string;text:string;pending?:boolean}[]>([])
  const phase = ref<"idle"|"thinking"|"speaking">("idle")

  const wsUrl = () => {
    const base = location.protocol === "https:" ? "wss://" : "ws://"
    return `${base}${location.host}/ws/chat?token=${auth.accessToken}` +
           `&session_id=${sessionId.value}&model=deepseek-chat`
  }
  const ws = useWebSocket(wsUrl)

  async function ensureSession() {
    if (sessionId.value) return
    const r = await http.post("/conversations", { title: null })
    sessionId.value = r.data.id
    ws.connect()
  }

  async function send(text: string) {
    await ensureSession()
    messages.push({ role: "user", text })
    const pending = reactive({ role: "assistant", text: "", pending: true })
    messages.push(pending)
    ws.send({ type: "user_text", session_id: sessionId.value, text })
    const off = () => {} // 简化：直接在 watcher 处理
    const handler = setInterval(() => {
      while (ws.messages.value.length) {
        const m = ws.messages.value.shift()
        if (!m) continue
        if (m.type === "state") phase.value = m.phase
        if (m.type === "token") pending.text += m.text
        if (m.type === "done") { pending.pending = false; phase.value = "idle"; clearInterval(handler) }
        if (m.type === "error") { pending.pending = false; pending.text += `（错误：${m.detail||m.code}）`; clearInterval(handler) }
      }
    }, 50)
  }

  return { messages, phase, send }
}
```

`apps/web-user/src/pages/Chat.vue`（核心结构）：

```vue
<script setup lang="ts">
import { ref } from "vue"
import { useChatSession } from "../composables/useChatSession"
import { GlassInput, GlassButton } from "@eira/ui-shared"

const { messages, phase, send } = useChatSession()
const draft = ref("")
function submit() {
  if (!draft.value.trim()) return
  send(draft.value); draft.value = ""
}
</script>
<template>
  <div class="chat-shell">
    <div class="bubble-area">
      <div v-for="(m,i) in messages" :key="i" :class="['bubble', m.role]">
        {{ m.text }}<span v-if="m.pending" class="cursor">▍</span>
      </div>
    </div>
    <div class="input-bar">
      <input v-model="draft" placeholder="输入您的问题..." @keyup.enter="submit" />
      <GlassButton variant="primary" @click="submit">发送</GlassButton>
    </div>
    <p v-if="phase === 'thinking'" class="hint">Eira 正在思考…</p>
  </div>
</template>
```

- [ ] **Step 2: Playwright E2E**

`apps/web-user/tests/e2e/chat.spec.ts`（先跳过依赖真后端，仅记录骨架）:

```typescript
import { test, expect } from "@playwright/test"

test("chat sends and receives", async ({ page }) => {
  await page.goto("/login")
  await page.fill('input[type=email]', "demo@x.com")
  await page.fill('input[type=password]', "Passw0rd!")
  await page.click("text=登录")
  await page.fill('input[placeholder*="问题"]', "你好")
  await page.click("text=发送")
  await expect(page.locator(".bubble.assistant")).toContainText(/.+/)
})
```

> ⚠️ **要点**：E2E 只在 G-1.2 验证门跑；CI 默认跳过（`--grep-invert e2e`）。

- [ ] **Step 3: 验证 + 提交**

```
pnpm --filter @eira/web-user run test
git add apps/ packages/
git commit -m "feat(frontend): chat page with ws streaming + composables"
```

---

## Task 1.8: Live2D 画布（拖拽 + 缩放 + 持久化）

**Files:**
- Create: `apps/web-user/src/live2d/Live2DStage.ts`
- Create: `apps/web-user/src/live2d/CubismLoader.ts`
- Create: `apps/web-user/src/components/Live2DCanvas.vue`
- Modify: `apps/web-user/src/pages/Chat.vue`（嵌入 canvas）
- Modify: `apps/web-user/package.json`（加 `pixi.js@^7`、`pixi-live2d-display@^0.4`）
- Create: `apps/web-user/public/live2d/Hiyori/`（占位模型；执行时由用户上传）

> ⚠️ **要点（spec 已锁定）**：
> - 画布**全屏**；模型默认居中底部；可拖拽到任意位置；滚轮缩放 0.3x–3x。
> - 位置/缩放写入 `localStorage`，key=`eira:live2d:${persona_id||default}`。
> - 需要在 HTML head 引入 Cubism Web SDK：`<script src="/cubism4/live2dcubismcore.min.js">`，模型加载完成后再初始化 Pixi。
> - 模型由后台管理上传到 OSS（Phase 4），本 Phase 先放本地 `/public/live2d/Hiyori/` demo。

- [ ] **Step 1: Stage 实现**

```typescript
// live2d/Live2DStage.ts
import * as PIXI from "pixi.js"
import { Live2DModel } from "pixi-live2d-display"

(window as any).PIXI = PIXI  // pixi-live2d-display 需要

export interface StageState {
  x: number; y: number; scale: number
}

export class Live2DStage {
  private app: PIXI.Application
  private model?: Live2DModel
  private dragging = false
  private dragStart = { x: 0, y: 0, mx: 0, my: 0 }

  constructor(canvas: HTMLCanvasElement, private storageKey: string) {
    this.app = new PIXI.Application({
      view: canvas, resizeTo: window, backgroundAlpha: 0,
      antialias: true, resolution: window.devicePixelRatio || 1, autoDensity: true,
    })
    canvas.addEventListener("wheel", this._onWheel)
    canvas.addEventListener("pointerdown", this._onDown)
    canvas.addEventListener("pointermove", this._onMove)
    canvas.addEventListener("pointerup", this._onUp)
  }

  async load(modelUrl: string) {
    this.model?.destroy()
    const m = await Live2DModel.from(modelUrl)
    this.app.stage.addChild(m)
    const saved = this._readState()
    const s = saved ?? { x: window.innerWidth/2, y: window.innerHeight*0.85, scale: 0.4 }
    m.x = s.x; m.y = s.y; m.scale.set(s.scale); m.anchor.set(0.5, 1)
    this.model = m
  }

  triggerExpression(name: string) { this.model?.expression(name) }
  triggerMotion(group: string, idx: number = 0) { this.model?.motion(group, idx) }

  private _readState(): StageState | null {
    const raw = localStorage.getItem(this.storageKey)
    return raw ? JSON.parse(raw) as StageState : null
  }
  private _saveState() {
    if (!this.model) return
    localStorage.setItem(this.storageKey, JSON.stringify({
      x: this.model.x, y: this.model.y, scale: this.model.scale.x,
    }))
  }

  private _onWheel = (e: WheelEvent) => {
    if (!this.model) return
    e.preventDefault()
    const cur = this.model.scale.x
    const next = Math.max(0.3, Math.min(3, cur * (e.deltaY > 0 ? 0.92 : 1.08)))
    this.model.scale.set(next)
    this._saveState()
  }
  private _onDown = (e: PointerEvent) => {
    if (!this.model) return
    const rect = this.model.getBounds()
    if (e.clientX >= rect.left && e.clientX <= rect.right &&
        e.clientY >= rect.top && e.clientY <= rect.bottom) {
      this.dragging = true
      this.dragStart = { x: this.model.x, y: this.model.y, mx: e.clientX, my: e.clientY }
    }
  }
  private _onMove = (e: PointerEvent) => {
    if (!this.dragging || !this.model) return
    this.model.x = this.dragStart.x + (e.clientX - this.dragStart.mx)
    this.model.y = this.dragStart.y + (e.clientY - this.dragStart.my)
  }
  private _onUp = () => { if (this.dragging) { this.dragging = false; this._saveState() } }
}
```

`components/Live2DCanvas.vue`:

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue"
import { Live2DStage } from "../live2d/Live2DStage"
const props = defineProps<{ modelUrl: string; personaId: string|number }>()
const canvasRef = ref<HTMLCanvasElement|null>(null)
let stage: Live2DStage | null = null
defineExpose({
  motion: (g:string,i?:number) => stage?.triggerMotion(g, i ?? 0),
  expression: (n:string) => stage?.triggerExpression(n),
})
onMounted(async () => {
  if (!canvasRef.value) return
  stage = new Live2DStage(canvasRef.value, `eira:live2d:${props.personaId}`)
  await stage.load(props.modelUrl)
})
</script>
<template>
  <canvas ref="canvasRef" class="live2d-canvas" />
</template>
<style scoped>
.live2d-canvas { position: fixed; inset: 0; width: 100vw; height: 100vh;
                 z-index: 0; touch-action: none; }
</style>
```

`Chat.vue` 在最底层嵌入 `<Live2DCanvas modelUrl="/live2d/Hiyori/Hiyori.model3.json" persona-id="default" />`。聊天 UI 用 `position:relative; z-index:1`。

- [ ] **Step 2: 验证（手动）**

```
pnpm --filter @eira/web-user run dev
# 浏览器：拖拽人物到不同位置；滚轮缩放；刷新后位置/缩放保留
```

记录到 `docs/superpowers/validations/G-1.3.md`（截图 + 描述）。

- [ ] **Step 3: 提交**

```
git add apps/web-user/
git commit -m "feat(live2d): full-screen pixi canvas with drag/zoom + state persistence"
```

> ⚠️ **要点**：Cubism Web SDK 许可仅免费供个人/教育与中小型商业使用；上线前确认 Live2D, Inc. 的最新使用条款（spec 已记入"延期决定 D-2"，Phase 4 商业化前必须重新确认）。

---

## Task 1.9: 动作标记解析 [wave]/[nod]/[happy]

**Files:**
- Create: `apps/web-user/src/live2d/actionTags.ts`
- Modify: `apps/web-user/src/composables/useChatSession.ts`（解析 token 中的标记）
- Modify: `backend/app/orchestrator/nodes/llm_call.py`（在 system prompt 教模型何时插入标记）
- Create: `backend/tests/unit/test_action_tag_prompt.py`

- [ ] **Step 1: 标记解析**

```typescript
// live2d/actionTags.ts
const TAG_RE = /\[(wave|nod|shake|point|happy|sad|surprised)\]/g
export type ActionTag = "wave"|"nod"|"shake"|"point"|"happy"|"sad"|"surprised"

export function extractTags(text: string): { clean: string; tags: ActionTag[] } {
  const tags: ActionTag[] = []
  const clean = text.replace(TAG_RE, (_, t) => { tags.push(t as ActionTag); return "" })
  return { clean, tags }
}

export const TAG_TO_MOTION: Record<ActionTag, [string, number]> = {
  wave:      ["TapBody", 0],
  nod:       ["Idle", 1],
  shake:     ["Idle", 2],
  point:     ["TapBody", 1],
  happy:     ["FlickHead", 0],
  sad:       ["Idle", 3],
  surprised: ["FlickHead", 1],
}
```

`useChatSession.ts` 收到 token 后做累积匹配：当出现完整 `[xxx]` 时调用 `live2dRef.value?.motion(...)` 并把标记从显示文本里删除。

- [ ] **Step 2: prompt 工程**

修改 `llm_call._build_messages`，在 system 末尾追加：

```
当回复需要肢体表达时，可使用以下行内标记：
- [wave] 挥手；[nod] 点头；[shake] 摇头；[point] 指方向；
- [happy] 开心；[sad] 难过；[surprised] 惊讶
每条回复最多使用 2 个标记，标记前后保留空格。不要解释标记本身。
```

`backend/tests/unit/test_action_tag_prompt.py`：

```python
from app.orchestrator.nodes.llm_call import _build_messages
from app.orchestrator.state import ChatState

def test_action_tag_instruction_present():
    s = ChatState(session_id="x", user_id=1, user_text="hi", history=[],
                  persona_prompt="base")
    msgs = _build_messages(s)
    sys = msgs[0].content
    assert "[wave]" in sys and "[happy]" in sys
```

- [ ] **Step 3: 验证 + 提交**

```
uv run pytest tests/unit/test_action_tag_prompt.py -v
git add apps/ backend/
git commit -m "feat(live2d): action tag parsing + prompt engineering"
```

---

## Task 1.10: 待机动作与"思考中"反馈

**Files:**
- Modify: `apps/web-user/src/live2d/Live2DStage.ts`（呼吸 + 眨眼自动；Idle motion loop）
- Modify: `apps/web-user/src/components/Live2DCanvas.vue`（暴露 `setPhase('thinking'|'speaking'|'idle')`）
- Modify: `apps/web-user/src/pages/Chat.vue`（订阅 phase）

> Cubism Web SDK 默认随模型 `Idle` group 自动循环；本任务额外做：
> - thinking 阶段，调一个轻微"歪头"动作（fallback 到 `Idle` index 1）；
> - speaking 阶段，回到默认（口型同步交给 Phase 3）；
> - 长时间无交互（30s）触发 idle 微动作。

- [ ] **Step 1/2: 实现 + 手动观察**

修改 `Live2DStage`：构造完成后启动 `setInterval` 30s 触发一次 idle 随机动作；新增 `setPhase()` 切换。

- [ ] **Step 3: 提交**

```
git add apps/web-user/
git commit -m "feat(live2d): idle/thinking/speaking phase animations"
```

---

## Task 1.11: 节点埋点 + LLM 调用日志

**Files:**
- Modify: `backend/app/orchestrator/nodes/*.py`（每节点 enter/exit log 与耗时）
- Create: `backend/app/capabilities/llm/logging_decorator.py`
- Modify: `backend/app/capabilities/llm/factory.py`（包装 provider）
- Create: `backend/app/capabilities/llm/pricing.yaml`
- Create: `backend/tests/unit/test_llm_logging.py`

> ⚠️ **关键日志字段**（structlog event 名固定）：
> - `event=orchestrator.node.start | orchestrator.node.end | orchestrator.error`
> - `event=llm.call.start | llm.call.end | llm.call.error`
> - 必含 `request_id / session_id / user_id / model / latency_ms`，端到端用 request_id 串联。

- [ ] **Step 1: pricing 表**

```yaml
# capabilities/llm/pricing.yaml
deepseek-chat:
  in_per_1k: 0.0014   # USD or RMB - 单位由运维自填，仅作展示
  out_per_1k: 0.0028
gpt-4o-mini:
  in_per_1k: 0.00015
  out_per_1k: 0.0006
```

- [ ] **Step 2: 写测试 + 实现 + 验证**

```python
# tests/unit/test_llm_logging.py
import structlog
from app.capabilities.llm.factory import build_llm
import pytest, json, io, sys

@pytest.mark.asyncio
async def test_mock_llm_emits_log(capsys):
    from app.core.logging import configure_logging
    configure_logging()
    llm = build_llm("mock")
    async for _ in llm.stream(messages=[]): pass
    out = capsys.readouterr().out
    assert "llm.call.end" in out
    payload = next(json.loads(l) for l in out.strip().splitlines()
                   if "llm.call.end" in l)
    assert payload["model"] == "mock"
    assert "latency_ms" in payload
```

`logging_decorator.py` 用装饰器包装 provider 的 `stream`，统计字符数 / 耗时，按 pricing 估算 cost。

- [ ] **Step 3: 提交**

```
git add backend/
git commit -m "feat(observability): orchestrator + llm structured logging with cost"
```

---

## 🚦 Validation Gate G-1.1 · 文本对话功能完整性

| 项 | 内容 |
|---|---|
| 指标 | 注册→登录→建会话→发问→收到完整回复→`/conversations/{id}/messages` 出现两条记录 |
| 阈值 | 100% 通过；DB 中 user/assistant message 顺序正确；token 帧数 > 1（确实是流式） |
| 测试方法 | `pytest tests/integration/test_ws_chat.py tests/integration/test_conversation.py -v`；手测 dev 环境完整跑 3 轮：闲聊 / 长答 / 中断（断网） |
| 数据源 | pytest 报告；归档 `docs/superpowers/validations/G-1.1.md`（含中断恢复行为说明） |
| 通过分支 | 进入下一门 |
| 不通过分支 | 缺消息持久化：回 T1.5 的 commit 时机检查；token 帧只 1 个：检查 LLM provider stream 配置；中断不可恢复（无 error 帧）：回 T1.5 异常分支 |

---

## 🚦 Validation Gate G-1.2 · 端到端文本延迟

| 项 | 内容 |
|---|---|
| 指标 | 真实 LLM (deepseek-chat) 下：(a) 首 token 延迟 P50/P95；(b) 整答完成延迟 P50/P95（200 字以内回复） |
| 阈值 | (a) P50 ≤ 1.2s, P95 ≤ 2s；(b) P50 ≤ 4s, P95 ≤ 6s（含网络） |
| 测试方法 | 写 `scripts/bench_chat_latency.py`，固定一组 30 个 prompt，串行跑 5 轮共 150 次（避免上游限流），记录 `first_token_ms` 与 `done_ms`；同时跟踪 LLM 端 `latency_ms`（区分客户端 vs 上游） |
| 数据源 | 脚本输出 CSV + structlog；归档 `docs/superpowers/validations/G-1.2.md`（含 raw CSV） |
| 通过分支 | 进入 G-1.3 |
| 不通过分支 | 仅首 token 慢：检查 provider stream 是否真流式（部分代理把 stream 拼回整段）→ 切 base_url 或换 provider；首 token < 阈值但完成 > 阈值：考虑限制 max_tokens / 提示模型简短回答（更新 system prompt）；普遍超：把 G-1.2 阈值拆为"国内/海外"两套，并在 spec 修订段记入；任何一项偏差 > 50%：升级 spec，重审"是否需要本地小模型 fallback"决策（D-3 候选） |

---

## 🚦 Validation Gate G-1.3 · Live2D 画布交互

| 项 | 内容 |
|---|---|
| 指标 | 画布初始化时间；30 分钟连续运行内存增长；FPS；拖拽/缩放/位置持久化的功能正确性 |
| 阈值 | 初始化 ≤ 1.5s（i7+集成显卡）；30 min 内存增量 ≤ 80MB；FPS ≥ 50（默认动作）；功能：刷新后位置/缩放完全一致 |
| 测试方法 | 手动 + Playwright：(1) 启动 dev 模式打开 chat；(2) Chrome Performance Tab 录 30s 看初始化；(3) 拖拽到 4 个角并刷新验证持久化；(4) Chrome Memory Tab 截两次 heap snapshot 比较 |
| 数据源 | 截图 + heap snapshot；归档 `docs/superpowers/validations/G-1.3.md` |
| 通过分支 | 进入 G-1.4 |
| 不通过分支 | 内存增长 > 80MB：定位 `Ticker` 监听是否清理（通常是 destroy 未释放）；FPS < 50：禁用 antialias 或下调 resolution；位置不持久：检查 storageKey 一致性；初始化慢：拆分模型加载与 Pixi 初始化为 dynamic import |

---

## 🚦 Validation Gate G-1.4 · 单元 + 集成测试覆盖率

| 项 | 内容 |
|---|---|
| 指标 | 后端 `pytest --cov=app` 覆盖率（行）；关键模块覆盖率（domain/conversation, capabilities/llm, orchestrator, api/ws）单独统计 |
| 阈值 | 总覆盖 ≥ 70%；关键模块 ≥ 80% |
| 测试方法 | CI 中 `--cov-report=xml`；`coverage report -m | grep -E '(domain/conversation|capabilities/llm|orchestrator|api/ws)'` 取分项 |
| 数据源 | `coverage.xml`；归档 `docs/superpowers/validations/G-1.4.md` |
| 通过分支 | 合入 main，打 `gate-G-1.4-passed`；进入 Phase 2 |
| 不通过分支 | 不允许通过临时屏蔽测试达标；优先补 service / WS 边界测试（错误分支、空 history、极长 input） |

---

## 完成状态

Phase 1 完成 ⇔ G-1.1 / G-1.2 / G-1.3 / G-1.4 全部 passed。
