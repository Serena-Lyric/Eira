# API 契约设计文档 (User & Admin 接口指南)

本文档整理了前端 (User/Admin) 与后端进行对接时需要优先实现的 RESTful 与 WebSocket API 列表。此设计遵循 `2026-05-26-architecture-design.md` 规范。

---

## 1. 景区用户端 (User API)

游客端强调实时交互，主要通过 **WebSocket** 进行多模态的流式通讯。部分静态资源与配置获取走 HTTP。

### 1.1 实时对话 (WebSocket)
**Endpoint**: `ws://<domain>/api/v1/ws/chat?token=<jwt>`

**前端发往后端 (Client -> Server)**
```json
// 1. 发送纯文本查询
{
  "type": "user.text",
  "session_id": "uuid",
  "msg_id": "uuid",
  "payload": {
    "text": "今天有什么表演？"
  },
  "ts": 1716700000
}

// 2. 语音流式分片上传 (可选)
{
  "type": "user.audio.chunk",
  "session_id": "uuid",
  "msg_id": "uuid",
  "payload": {
    "audio_b64": "base64_encoded_pcm_data"
  }
}
// 3. 语音结束标记
{
  "type": "user.audio.end",
  "session_id": "uuid",
  "msg_id": "uuid"
}
```

**后端发往前端 (Server -> Client)**
```json
// 1. AI 思考中占位
{ "type": "agent.thinking" }

// 2. 流式文本下发 (打字效果)
{
  "type": "agent.text.delta",
  "payload": { "delta": "今天下午" }
}

// 3. 动作控制标记 (前端 Live2D 直接响应)
{
  "type": "agent.action",
  "payload": { "tag": "smile", "priority": 1 }
}

// 4. TTS 语音流下发
{
  "type": "agent.audio.chunk",
  "payload": { "audio_b64": "base64_mp3_data" }
}

// 5. 消息结束
{ "type": "agent.text.done" }
{ "type": "agent.audio.done" }
```

### 1.2 资源与设置 (HTTP)
*   **POST** `/api/v1/backgrounds`
    *   *用途*: 用户上传本地照片作为背景 (目前保存在本地态，需结合租户机制上云)。
    *   *Payload*: `multipart/form-data` (file: Image)
    *   *返回*: `{ "url": "https://oss.../bg.jpg" }`

*   **POST** `/api/v1/messages/attachments`
    *   *用途*: 针对输入框内 `+` 号的文件上传（如上传照片让 AI 分析）。
    *   *Payload*: `multipart/form-data`
    *   *返回*: `{ "attachment_id": "xxx" }`

---

## 2. 管理后台端 (Admin API)

Admin 端主要是 CRUD 和数据统计分析。所有的请求都需要在 HTTP Header 中携带 `Authorization: Bearer <token>`。

### 2.1 运营看板分析 (Analytics)
*   **GET** `/api/v1/admin/analytics/overview`
    *   *参数*: `range=day|week|month`
    *   *返回*: `{ "served_users": 1258, "interactions": 8432, "avg_latency": "1.2s", "satisfaction_rate": 0.985 }`

*   **GET** `/api/v1/admin/analytics/charts`
    *   *参数*: `range=day|week|month`
    *   *返回*: 包含 ECharts 所需的结构化数据，如满意度折线图点位、TOP5 问题排行表等。

*   **GET** `/api/v1/admin/analytics/wordcloud`
    *   *返回*: 词云列表 `[{"word": "路线", "weight": 100}, {"word": "天气", "weight": 85}]`

### 2.2 资产与形象管理
*   **GET** `/api/v1/personas/active`
    *   *用途*: 获取当前选中的激活形象。
    *   *返回*: `{ "id": "...", "name": "Eira Default", "model_id": "hiyori_v3", ... }`

*   **POST** `/api/v1/live2d-models`
    *   *用途*: 上传新的 Live2D Cubism 模型包 (Zip 格式)。
    *   *Payload*: `multipart/form-data`
    *   *返回*: `{ "model_id": "xxx", "status": "processing|ready" }`

### 2.3 知识库管理
*   **POST** `/api/v1/knowledge`
    *   *用途*: 上传景区 PDF/Docx 文档。
*   **POST** `/api/v1/knowledge/:id/index`
    *   *用途*: 触发向量化任务 (RAG)。
*   **GET** `/api/v1/knowledge/jobs/:job_id`
    *   *用途*: 轮询向量化任务进度。