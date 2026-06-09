# Phase 1 API 规格 · Eira Backend

**日期:** 2026-06-03
**Phase:** 1 · 文本对话闭环 + Live2D 画布
**App:** `backend/app/main.py` → `create_app()`

---

## 1. 路由总览

### 1.1 REST 端点

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| `GET` | `/` | 无 | 服务信息 |
| `GET` | `/healthz` | 无 | 存活检查 |
| `GET` | `/readyz` | 无 | 就绪检查 (DB + Redis + OSS) |
| `GET` | `/metrics` | 无 | Prometheus 指标 |
| `POST` | `/auth/register` | 无 | 用户注册 |
| `POST` | `/auth/login` | 无 | 登录，返回 access_token + refresh_token |
| `POST` | `/auth/refresh` | 无 | 刷新令牌对 |
| `GET` | `/auth/me` | Bearer Token | 当前用户信息 |
| `POST` | `/conversations` | Bearer Token | 创建聊天会话 |
| `GET` | `/conversations` | Bearer Token | 列出会话 (分页: limit/offset) |
| `GET` | `/conversations/{session_id}/messages` | Bearer Token | 列出消息 (分页: limit/offset) |

### 1.2 WebSocket

| 路径 | 认证 | 说明 |
|---|---|---|
| `/ws/chat?token=<jwt>` | Query String JWT | 聊天 WebSocket |

---

## 2. 数据模型

### 2.1 请求 / 响应 Schema

**POST /auth/register**
```json
{ "email": "u@x.com", "password": "Passw0rd!", "display_name": "U1" }
```
→ 201 `{ "id": 1, "email": "u@x.com", "display_name": "U1", "role": "admin" }`

**POST /auth/login**
```json
{ "email": "u@x.com", "password": "Passw0rd!" }
```
→ 200 `{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }`

**POST /auth/refresh**
```json
{ "refresh_token": "..." }
```
→ 200 `{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }`

**GET /auth/me**
→ 200 `{ "id": 1, "email": "u@x.com", "display_name": "U1", "role": "admin" }`

**POST /conversations**
```json
{ "persona_id": null, "title": "My Chat" }
```
→ 201 `{ "id": 1, "user_id": 1, "persona_id": null, "title": "My Chat", "created_at": "...", "ended_at": null }`

**GET /conversations?limit=20&offset=0**
→ 200 `{ "sessions": [...], "total": 5 }`

**GET /conversations/1/messages?limit=200&offset=0**
→ 200 `[ { "id": 1, "session_id": 1, "role": "user", "content": "你好", "created_at": "..." } ]`

---

## 3. WebSocket 协议

### 3.1 连接

```
ws://localhost:8000/ws/chat?token=<access_token>
```

认证失败 → `{"type":"error","code":"auth_failed","detail":"invalid_token"}` → close (4001)

### 3.2 客户端 → 服务端

```json
{"type":"user_text","session_id":"sess-xxx","text":"你好","ts":1234567890}
```
```json
{"type":"interrupt"}
```

### 3.3 服务端 → 客户端（按序）

| 帧 | 示例 |
|---|---|
| State (thinking) | `{"type":"state","phase":"thinking"}` |
| State (streaming) | `{"type":"state","phase":"streaming"}` |
| Token | `{"type":"token","text":"你好"}` |
| Action | `{"type":"action","tag":"Flick"}` |
| Done | `{"type":"done","message_id":null,"latency_ms":123.4,"tokens":{"completion":79}}` |
| State (done) | `{"type":"state","phase":"done"}` |
| Error | `{"type":"error","code":"llm_error","detail":"..."}` |

### 3.4 Action Tags（Live2D 动作标记）

LLM System Prompt 教模型插入动作标记。后端提取并转换为 action 帧：

| 标记 | Motion Group | 效果 |
|---|---|---|
| `[wave]` | Flick | 挥手 |
| `[nod]` | FlickDown | 点头 |
| `[happy]` | Tap | 开心 |
| `[greet]` | FlickUp | 打招呼 |
| `[tap]` | Tap@Body | 轻触身体 |
| `[idle]` | Idle | 待机 |

---

## 4. 数据库表

### chat_session
| 列 | 类型 | 约束 |
|---|---|---|
| id | BIGINT | PK, autoincrement |
| user_id | BIGINT | FK → users.id |
| persona_id | VARCHAR(64) | nullable |
| title | VARCHAR(255) | nullable |
| created_at | TIMESTAMPTZ | NOT NULL, server_default now() |
| ended_at | TIMESTAMPTZ | nullable |

### chat_message
| 列 | 类型 | 约束 |
|---|---|---|
| id | BIGINT | PK, autoincrement |
| session_id | BIGINT | FK → chat_session.id |
| role | VARCHAR(16) | NOT NULL, CHECK (user/assistant) |
| content | TEXT | NOT NULL |
| audio_oss_key | VARCHAR(512) | nullable (Phase 3) |
| metadata_json | TEXT | nullable |
| created_at | TIMESTAMPTZ | NOT NULL, server_default now() |

---

## 5. LLM Provider 配置

环境变量（前缀 `EIRA_LLM__`）：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `EIRA_LLM__PROVIDER` | `deepseek` | deepseek / openai / tongyi / volc / mock |
| `EIRA_LLM__API_KEY` | `sk-...` | API 密钥 |
| `EIRA_LLM__API_BASE` | `https://api.deepseek.com` | API 基础 URL |
| `EIRA_LLM__MODEL` | `deepseek-chat` | 模型名称 |
| `EIRA_LLM__MAX_TOKENS` | `2048` | 最大 token 数 |
| `EIRA_LLM__TEMPERATURE` | `0.7` | 温度参数 |
| `EIRA_LLM__MAX_RETRIES` | `3` | 最大重试次数 |
| `EIRA_LLM__REQUEST_TIMEOUT` | `60` | 请求超时(秒) |

---

## 6. Orchestrator 节点序列

```
load_context → safety_in → llm_call → safety_out → persist → emit → END
```

- **load_context**: 加载 persona prompt（Phase 1 使用默认导游助手 prompt）
- **safety_in**: 输入长度截断 (2000 chars) + 黑名单关键词拒答
- **llm_call**: 调用 LLM Provider 流式获取回复
- **safety_out**: 输出脱敏（sk-xxx / AKIAxxx / JWT 替换为 [REDACTED]）
- **persist**: 持久化 user + assistant 消息（Phase 1 暂为日志）
- **emit**: 终端节点

短路规则：
- safety_in 失败 → 直接跳到 emit（返回兜底回复）
- llm_call 异常 → 跳到 emit（返回错误信息）
