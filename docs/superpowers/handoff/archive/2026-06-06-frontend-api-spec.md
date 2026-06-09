# Eira 前端 API 需求规格 · 后端接入文档

> **日期:** 2026-06-06
> **用途:** 供后端开发人员实现 API 端点时参考
> **状态:** 前端 API 服务层已完整定义；用户端反馈/背景/模型/偏好/语音端点已实现骨架，管理端端点待实现
> **最后更新**: 2026-06-06（第二轮——新增 TTS、ASR 配置、反馈、用户上传端点规格）

---

## 约定

- 所有请求需带 `Content-Type: application/json`（文件上传除外）
- 认证方式：Bearer Token（`Authorization: Bearer <access_token>`）
- 除 `/auth/*` 外，所有端点需认证
- 所有响应为 JSON
- 分页参数统一使用 `limit` / `offset` query 参数

---

## 一、已实现（无需后端额外开发）

以下端点在 `backend/app/api/rest/` 下已有实现，前端正常调用：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/auth/register` | 用户注册 |
| `POST` | `/auth/login` | 登录，返回 `{ access_token, refresh_token }` |
| `POST` | `/auth/refresh` | 刷新令牌对 |
| `GET` | `/auth/me` | 当前用户信息 |
| `POST` | `/conversations` | 创建会话 |
| `GET` | `/conversations` | 列出会话 (分页: `limit`, `offset`) |
| `GET` | `/conversations/{session_id}/messages` | 列出消息 (分页) |

---

## 二、用户端新增 API（待后端实现）

### 2.1 用户偏好

**`GET /user/preferences`**

获取当前用户的 UI 偏好设置。首次访问返回全部默认值。

```json
// Response 200
{
  "background_url": null,
  "background_blur": false,
  "voice_enabled": true,
  "camera_mode": "hidden",
  "show_mic": true,
  "quick_questions": ["路线怎么走？", "今天有什么表演？", "推荐附近的美食"],
  "chat_bubble_mode": "center",
  "quick_questions_mode": "center",
  "input_bar_mode": "center",
  "active_model_id": "mao_pro_zh",
  "voice_input_mode": "click"
}
```

> `voice_input_mode` 取值: `"click"`（点击录音，默认）| `"persistent"`（常驻监听）| `"smart"`（智能检测）| `"hidden"`（隐藏）

**`PATCH /user/preferences`**

部分更新用户偏好（仅发送变更字段）。

```json
// Request Body (所有字段可选)
{
  "background_url": "https://oss.example.com/bg/user_69.jpg",
  "background_blur": true,
  "voice_enabled": false,
  "camera_mode": "front",
  "show_mic": false,
  "quick_questions": ["厕所在哪里？", "几点关门？"],
  "chat_bubble_mode": "left",
  "quick_questions_mode": "hidden",
  "input_bar_mode": "center",
  "active_model_id": "hiyori_pro_zh",
  "voice_input_mode": "smart"
}

// Response 200 — { "success": true, "message": "偏好已更新" }
```

**`POST /user/background`**

上传用户自定义背景图。

```
Content-Type: multipart/form-data
字段: background (File) — JPG / PNG / WebP，最大 10MB

Response 200:
{
  "success": true,
  "message": "背景图片上传成功",
  "url": "https://oss.example.com/user/backgrounds/user_69/1718123456.jpg"
}

Error 400 — 不支持的格式:
{ "detail": "不支持的图片格式。仅接受 JPG、PNG、WebP。" }

Error 413 — 文件过大:
{ "detail": "图片文件过大。最大允许 10 MB。" }
```

**`POST /user/model`**

上传用户 Live2D 模型包。

```
Content-Type: multipart/form-data
字段: model_zip (File) — .zip / .7z / .rar 压缩包，最大 100MB

处理流程:
1. 接收并验证格式/大小
2. 解压并验证包含 model3.json（Cubism 模型入口文件）
3. 验证 .moc3 文件存在
4. 存储到 OSS 用户目录
5. 返回结果

Response 200:
{
  "success": true,
  "message": "模型包上传成功，解析完成",
  "model_id": "user-69-20260606120000"
}

Error 400 — 文件格式不符 / 缺少必要文件:
{ "detail": "不支持的压缩格式。仅接受 .zip / .7z / .rar。" }

Error 413 — 文件过大:
{ "detail": "模型包过大。最大允许 100 MB。" }
```

### 2.2 语音服务

**`POST /voice/asr`**

发送音频数据进行语音识别。

```
Content-Type: multipart/form-data
字段: audio (File) — WebM/Opus 音频 blob

Response 200:
{ "text": "我想问一下洗手间在哪里" }

Error 400:
{ "detail": "无法识别的音频格式" }
```

**`POST /voice/tts`** 🆕

文本转语音。根据系统配置的 TTS 引擎生成音频。

```json
// Request Body
{
  "text": "您好，欢迎来到景区。",
  "voice": "default",
  "speed": 1.0
}

// Response 200 — audio/wav 二进制数据
// 当前状态: 返回 501（Phase 2 实现）
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text` | string | ✅ | 要转换的文本，1-2000 字符 |
| `voice` | string \| null | ❌ | 语音角色 ID，默认使用系统配置 |
| `speed` | float \| null | ❌ | 语速倍率，0.5-2.0，默认 1.0 |

**`GET /voice/asr/config`** 🆕

获取 ASR 语音识别服务配置（前端用于初始化讯飞等实时 ASR SDK）。

```json
// Response 200
{
  "provider": "xunfei",
  "app_id": "your_app_id",
  "api_key": "your_api_key",
  "api_secret": "your_api_secret",
  "websocket_url": "wss://rtasr.xfyun.cn/v1/ws",
  "enabled": true
}
```

> 当前状态: 返回默认值（`enabled: false`），Phase 2 从 settings 读取实际配置。

### 2.3 文件上传

**`POST /conversations/upload`**

对话中上传附件（图片、文档等）。

```
Content-Type: multipart/form-data
字段:
  file (File)       — 附件文件
  session_id (str)  — 会话 ID

Response 201:
{
  "file_url": "https://oss.example.com/attachments/sess_123/photo.jpg",
  "file_type": "image/jpeg",
  "file_size": 245760
}
```

### 2.4 用户反馈

**`POST /feedback`**

提交用户反馈。

```json
// Request Body
{ "text": "希望增加英文导览语音选项" }

// Response 200
{
  "success": true,
  "message": "反馈已提交，感谢您的建议！",
  "feedback_id": 42,
  "created_at": "2026-06-06T12:00:00Z"
}

// Error 422 — 内容为空
{ "detail": "反馈内容不能为空" }
```

> 前端根据 `success` 字段判断成功/失败，`message` 展示给用户。`feedback_id` 和 `created_at` 在 Phase 2 持久化后返回实际值（当前为 null）。

---

## 三、管理端新增 API（待后端实现）

### 3.1 运营看板

**`GET /admin/dashboard/metrics`**

```json
// Query: ?range=day|week|month|custom&start_date=2026-06-01&end_date=2026-06-06

// Response 200
{
  "total_visitors": 1258,
  "total_conversations": 8432,
  "avg_response_latency_ms": 1200,
  "satisfaction_pct": 98.5,
  "visitors_change_pct": 12.5,
  "conversations_change_pct": 5.2,
  "latency_change_ms": 100,
  "satisfaction_change_pct": 1.0
}
```

**`GET /admin/dashboard/top-questions`**

```json
// Query: ?range=day&limit=5

// Response 200
[
  { "rank": 1, "text": "洗手间在哪里？", "count": 342, "percentage": 32 },
  { "rank": 2, "text": "今天有什么表演？", "count": 289, "percentage": 27 }
]
```

**`GET /admin/dashboard/satisfaction-trend`**

```json
// Query: ?range=month

// Response 200
[
  { "date": "2026-06-01", "score": 98.0 },
  { "date": "2026-06-02", "score": 96.5 },
  { "date": "2026-06-03", "score": 99.1 }
]
```

**`GET /admin/dashboard/word-cloud`**

```json
// Query: ?range=week&limit=50

// Response 200
[
  { "text": "路线", "weight": 0.9, "color": "#3B82F6" },
  { "text": "美食", "weight": 0.85, "color": "#F59E0B" }
]
```

**`GET /admin/dashboard/sentiment`**

```json
// Query: ?range=day

// Response 200
{
  "positive_pct": 75,
  "neutral_pct": 12,
  "negative_pct": 13
}
```

**`GET /admin/dashboard/feedback`**

```json
// Query: ?limit=10

// Response 200
[
  {
    "id": 1,
    "timestamp": "10:42",
    "content": "建议增加英文导览语音选项。",
    "replied": false,
    "reply_text": null
  }
]
```

**`POST /admin/dashboard/feedback/{feedback_id}/reply`**

```json
// Request Body
{ "reply_text": "感谢您的建议，我们已记录。" }

// Response 200 — 无响应体
```

### 3.2 角色管理 (Personas)

**`GET /admin/personas`**

```json
// Response 200
[
  {
    "id": 1,
    "name": "Eira Default",
    "description": "The official digital guide persona.",
    "is_default": true,
    "model_id": "mao_pro_zh",
    "voice_id": null,
    "created_at": "2026-06-01T10:00:00Z",
    "updated_at": "2026-06-01T10:00:00Z"
  }
]
```

**`GET /admin/personas/{id}`** — 返回单个 Persona

**`POST /admin/personas`**

```json
// Request Body
{
  "name": "Historical Scholar",
  "description": "Expert on local history.",
  "model_id": "hiyori_pro_zh",
  "voice_id": null
}

// Response 201 — 返回新创建的 Persona 对象
```

**`PATCH /admin/personas/{id}`** — 部分更新 Persona

```json
// Request Body (所有字段可选)
{
  "name": "Updated Name",
  "description": "Updated description",
  "model_id": "custom_model",
  "voice_id": "voice_02"
}
```

**`DELETE /admin/personas/{id}`** — 删除 → 204

**`POST /admin/personas/{id}/set-default`** — 设为默认角色 → 返回更新后的 Persona

### 3.3 知识库管理

**`GET /admin/knowledge`**

```json
// Response 200
[
  {
    "id": 1,
    "name": "景区导览手册_2026.pdf",
    "size_bytes": 2516582,
    "size_display": "2.4 MB",
    "status": "indexed",
    "progress": null,
    "uploaded_at": "2026-06-03T08:30:00Z"
  },
  {
    "id": 2,
    "name": "票务说明.docx",
    "size_bytes": 153600,
    "size_display": "150 KB",
    "status": "processing",
    "progress": 45,
    "uploaded_at": "2026-06-03T09:00:00Z"
  }
]
```

**`POST /admin/knowledge/upload`**

```
Content-Type: multipart/form-data
字段: file (File) — PDF / DOCX / TXT / MD

Response 201 — 返回 KnowledgeDocument 对象，status 初始为 "pending"
```

**`GET /admin/knowledge/{id}/status`** — 返回单个文档状态（用于轮询处理进度）

**`DELETE /admin/knowledge/{id}`** — 删除文档 → 204

### 3.4 资产管理

**`GET /admin/assets`**

```json
// Response 200
[
  {
    "id": 1,
    "name": "mao_pro_zh",
    "type": "live2d_model",
    "is_default": true,
    "file_size_bytes": 5242880,
    "uploaded_at": "2026-06-01T08:00:00Z"
  }
]
```

**`POST /admin/assets/live2d`**

```
Content-Type: multipart/form-data
字段: file (File) — .zip / .7z / .rar 压缩包

Response 201 — 返回 Asset 对象
```

**`POST /admin/assets/background`**

```
Content-Type: multipart/form-data
字段: file (File) — JPG / PNG / WebP / MP4

Response 201 — 返回 Asset 对象
```

**`POST /admin/assets/{id}/set-default`** — 设为默认资产

**`DELETE /admin/assets/{id}`** — 删除资产 → 204

### 3.5 应用配置

**`GET /admin/config`**

```json
// Response 200
{
  "llm_provider": "deepseek",
  "llm_model": "deepseek-chat",
  "tts_engine": "aliyun_nls",
  "asr_engine": "aliyun_asr",
  "embedding_model": "text-embedding-v3",
  "web_search_provider": "bocha",
  "daily_search_quota": 200,
  "api_key_status": {
    "deepseek": "configured",
    "aliyun_nls": "configured",
    "tavily": "missing"
  },
  "global_background_url": null,
  "voice_persistence": true,
  "user_doc_quota": 100
}
```

**`PATCH /admin/config`**

```json
// Request Body (所有字段可选)
{
  "llm_model": "deepseek-reasoner",
  "daily_search_quota": 500
}

// Response 200 — 返回更新后的完整 config 对象
```

---

## 四、WebSocket 协议（已实现）

```
ws://localhost:8000/ws/chat?token=<access_token>
```

### 客户端 → 服务端

```json
{ "type": "user_text", "session_id": "sess-xxx", "text": "你好", "ts": 1718123456789 }
{ "type": "interrupt" }
```

### 服务端 → 客户端（按序）

| 帧类型 | 示例 |
|--------|------|
| State (thinking) | `{ "type": "state", "phase": "thinking" }` |
| State (streaming) | `{ "type": "state", "phase": "streaming" }` |
| Token | `{ "type": "token", "text": "你好" }` |
| Action | `{ "type": "action", "tag": "Flick" }` |
| Done | `{ "type": "done", "message_id": null, "latency_ms": 123.4, "tokens": { "completion": 79 } }` |
| State (done) | `{ "type": "state", "phase": "done" }` |
| Error | `{ "type": "error", "code": "llm_error", "detail": "..." }` |

### Action Tags（Live2D 动作）

| 标记 | Motion Group |
|------|-------------|
| `[wave]` | Flick |
| `[nod]` | FlickDown |
| `[happy]` | Tap |
| `[greet]` | FlickUp |
| `[tap]` | Tap@Body |
| `[idle]` | Idle |

---

## 五、优先级建议

### P0 — 阻塞上线
- 无需新增端点（现有 auth / conversation / ws/chat 已实现）

### P1 — 核心功能
- `/user/preferences` (GET + PATCH) — 用户设置持久化（**骨架已实现，待接入数据库**）
- `/admin/dashboard/*` (6 个端点) — 运营看板
- `/admin/personas` (CRUD) — 角色管理
- `/admin/knowledge` (CRUD) — 知识库

### P2 — 完善体验
- `/user/background` + `/user/model` — 用户上传（**✅ 已实现**，格式验证/大小限制/响应格式就绪）
- `/voice/asr` — 语音识别
- `/voice/tts` — 文本转语音（**🆕 骨架已实现**，返回 501）
- `/voice/asr/config` — ASR 配置（**🆕 骨架已实现**）
- `/admin/assets` (CRUD) — 资产管理
- `/admin/config` (GET + PATCH) — 系统配置
- `/feedback` — 用户反馈（**✅ 已实现**）
- `/conversations/upload` — 对话附件

---

## 六、前端处理逻辑说明

1. **Dashboard 数据**：前端 `useDashboard` composable 在 API 返回 404/500 时自动回退到结构化 mock 数据。后端实现完成后前端无需任何修改即可使用真实数据。

2. **用户偏好**：`Chat.vue` 在 `onMounted` 时调用 `GET /user/preferences`，静默回退默认值。新增 `voice_input_mode` 字段控制语音输入模式。

3. **Token 刷新**：前端 Axios 拦截器在收到 401 时自动调用 `POST /auth/refresh` 并重试原请求，并发请求排队处理。

4. **管理端 Content 页**：Personas / Knowledge / Live2D 三页的表格和上传功能已接入 API 函数，加载/空态/错误状态已处理。

5. **上传错误分级处理** 🆕：背景/模型上传在前端按错误类型给出不同提示：
   - HTTP 413 → "文件过大（最大 X MB）"
   - HTTP 400 → 后端返回的具体错误原因
   - `ERR_NETWORK` / Network → "网络错误，请检查连接后重试"
   - HTTP 401 → "登录已过期，请重新登录"
   - 其余 → 通用错误提示

6. **反馈双状态确认** 🆕：前端根据 `POST /feedback` 返回的 `success` 字段判断成功/失败，分别展示绿色"✓ 已提交"或红色错误消息。网络错误、401 等单独处理。

7. **语音输入四种模式** 🆕：前端根据 `voice_input_mode` 偏好切换录音行为：
   - `click`：点击开始/再点结束 → 发送到 ASR
   - `persistent`：常驻持续录音
   - `smart`：AudioContext + AnalyserNode 智能检测语音启停
   - `hidden`：完全不响应/不显示
