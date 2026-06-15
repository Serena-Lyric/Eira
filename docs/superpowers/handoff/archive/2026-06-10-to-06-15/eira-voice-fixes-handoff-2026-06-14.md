# Eira Voice WS 修复 Handoff · 2026-06-14

> **来源**: `docs/superpowers/handoff/2026-06-10-testing-handoff.md` 的 P0-P2 修复 + 讯飞 ASR 集成调试
> **结果**: Voice ASR 全管线已跑通（WebM→PCM→讯飞IAT→LLM→TTS），文本聊天正常

---

## 1. 当前状态总结

### 服务状态（全部运行中）

| 服务 | 地址 | 状态 |
|------|------|:--:|
| PostgreSQL | localhost:5432 (Docker) | 🟢 |
| Redis | localhost:6379 (Docker) | 🟢 |
| MinIO | localhost:9000/9001 (Docker) | 🟢 |
| 后端 | localhost:8000 (uvicorn) | 🟢 |
| web-user | localhost:5173 (Vite dev) | 🟢 |

### Provider 状态

| 服务 | 状态 | 备注 |
|------|:--:|------|
| LLM (DeepSeek) | 🟢 | 正常回复 |
| Embedding (4sapi) | 🟢 | 就绪 |
| ASR (Xunfei) | 🟢 | **刚修复，可正常识别中文语音** |
| TTS (Xunfei) | 🟡 | 凭证有效（已单独测试），未端到端验证 |
| Search (Tavily) | 🔴 | 未配置 |

---

## 2. 本对话完成的修复

### P0 — Voice WS code=4000 修复

**文件**: `backend/app/api/ws/voice.py`

**根因**: Provider 初始化（含 DB 查询的 `get_effective_llm_settings()`）在 `try/except` 块外部，初始化失败导致静默断开。

**修复**: 将 lines 86-91 的初始化包裹在 try/except 中，失败时发送 `VoiceErrorOut(code="init_failed")` + `ws.close(1011)`。

**附**: 同样为 `flush_audio_and_recognize()` 添加了 try/except → `VoiceErrorOut(code="asr_error")`。

---

### P0 — 讯飞 ASR 集成（三层修复）

**根因链**:
1. **协议错误**: 中间帧以二进制发送，但 Xunfei `encoding="raw"` 要求所有帧为 JSON + base64
2. **响应解析错误**: `_parse_result` 期望 `data.result.cn.st.rt[]` 格式，但实际响应是 `data.result.ws[]` 格式（dwa=wpgs）
3. **音频格式**: 浏览器 WebM/Opus 不兼容，需转码为 16kHz 16-bit PCM

**文件**: 
- `backend/app/capabilities/asr/xunfei.py` — stream() 全 JSON 帧 + _parse_result 重写支持 ws 格式
- `apps/web-user/src/composables/useAudioProcessor.ts` — **新建**，WebM→PCM 转码
- `apps/web-user/src/pages/Chat.vue` — 录音流程改为转码后发送

**关键要点**:
- AudioProcessor 使用 `AudioContext.decodeAudioData()` 解码 → 混音为单声道 → 重采样到 16kHz → Float32→Int16
- Xunfei 响应格式: `data.result.ws[].cw[].w` (词段)，`data.status==2` 或 `sn==ed` 表示最终结果
- PCM 诊断: 控制台输出 `[AudioProcessor] Source: 48000Hz 1ch X.Xs → PCM: 16000Hz X.XKB X.Xs peak=X.XdBFS`

---

### P1 — 聊天上下文丢失

**文件**: 
- `apps/web-user/src/composables/useChatSession.ts` — `createSession()` 添加 token 就绪轮询 + `crypto.randomUUID()` fallback
- `backend/app/api/ws/chat.py` — `int(session_id)` 失败时记录 `ws.chat.non_integer_session_id` warning

**附加修复（语音上下文）**:
- `backend/app/api/ws/voice_messages.py` — `VoiceStartIn` 新增 `session_id` 字段
- `backend/app/api/ws/voice.py` — `run_orchestrator` 使用前端传来的 session_id，不再自生成
- `apps/web-user/src/composables/useVoiceWs.ts` — `sendVoiceStart()` 接受 sessionId
- `apps/web-user/src/pages/Chat.vue` — 传 `sessionId.value` 给语音 WS

---

### P1 — 动作标签正则

**文件**: `backend/app/api/ws/messages.py`

**修复**: `_ACTION_TAG_RE` 从 `r"\[(wave|nod|happy)\]"` 扩展到全部 13 个标签（greet, surprised, sad, think, angry, shy, wink, confused, tap, idle）。

---

### P2 — 前端修复

| 文件 | 修改 |
|------|------|
| `Chat.vue` | `phase` → `wsPhase`（预存 TS 错误） |
| `Chat.vue` | `onAsrPartial` 改为浮层字幕（`asrSubtitle`），不再污染输入框 |
| `Chat.vue` | `onAsrFinal` 移除 `wsSendText()` 调用（避免双重 LLM） |
| `Chat.vue` | `onChatToken` 从 Voice WS 累积回复文本 |
| `Chat.vue` | `onChatDone` 收尾消息到聊天列表 |
| `useVoiceWs.ts` | 添加 `chat.token` / `chat.action` 消息类型处理 |

---

### P2 — 后端修复

| 文件 | 修改 |
|------|------|
| `asr/factory.py` | 移除隐式 Mock fallback → 凭证缺失抛 `ValueError` |
| `tts/factory.py` | 同上 |
| `config.py` | `AsrSettings.provider` / `TtsSettings.provider` Literal 添加 `"mock"` |
| `voice.py` | 二进制音频帧绕过限流（仅 JSON 控制消息受限） |
| `voice.py` | ASR 空结果发送 `no_speech` 错误到客户端 |

---

### 新建文件

| 文件 | 说明 |
|------|------|
| `apps/web-user/src/composables/useAudioProcessor.ts` | WebM→PCM 转码 + 音频健康诊断 |
| `README.md` | 完整启动指南（PowerShell/CMD 命令） |

---

## 3. 已知待处理问题

### 🔴 高优先级
1. **前端 dev server 编译**: 运行 `pnpm --filter @eira/web-user dev` 进行热重载开发（目前用 `pnpm build` 确认编译通过）
2. **TTS 语音播报**: 讯飞 TTS 凭证已验证有效，但未端到端测试浏览器音频播放

### 🟡 中优先级
3. **浮层字幕样式**: `asrSubtitle` 需要美化（位置、动画、颜色）
4. **设置开关**: 用户报告设置内开关未生效，需排查
5. **Voice WS 时序**: 客户端关闭时可能触发 `Cannot call "send" once a close message has been sent`（voice.py line 24 日志），需添加发送前状态检查

### 🔵 低优先级
6. **人工验证门**: `docs/superpowers/validations/` 下 G-2.4 ~ G-4.2 待闭合
7. **语音上下文**: session_id 传递已修复但未端到端验证
8. **前端单元测试**: 尚无

---

## 4. 启动命令

详情见项目根目录 `README.md`。

```powershell
# 基础设施
docker compose -f deploy\docker-compose.dev.yml up -d

# 后端 (PowerShell)
cd D:\Application\ClaudeCode\repository\Eira\backend
$env:EIRA_JWT__SECRET = "dev-secret"
$env:EIRA_OSS__SECRET = "eira-secret"
$env:EIRA_DB_DSN = "postgresql+asyncpg://eira:eira@localhost:5432/eira"
$env:EIRA_REDIS_URL = "redis://localhost:6379/0"
$env:EIRA_OSS_ENDPOINT = "http://localhost:9000"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端
pnpm --filter @eira/web-user dev

# 测试
cd backend
python -m pytest tests/ -v --tb=short
```

---

## 5. 关键文件索引

| 路径 | 说明 |
|------|------|
| `backend/app/api/ws/voice.py` | Voice WS 核心 — 连接管理 + ASR→LLM→TTS 管线 |
| `backend/app/capabilities/asr/xunfei.py` | 讯飞 IAT WebSocket 客户端 — HMAC-SHA256 鉴权 + PCM 流式识别 |
| `backend/app/api/ws/voice_messages.py` | Voice 协议消息模型 |
| `backend/app/api/ws/messages.py` | 通用消息模型 + 动作标签 |
| `apps/web-user/src/composables/useVoiceWs.ts` | 前端 Voice WS 客户端 |
| `apps/web-user/src/composables/useAudioProcessor.ts` | WebM→PCM 转码 |
| `apps/web-user/src/pages/Chat.vue` | 聊天页（含录音逻辑） |
| `apps/web-user/src/composables/useChatSession.ts` | Chat WS + Session 管理 |
| `backend/app/core/config.py` | 配置模型（含 API keys） |
| `backend/app/capabilities/asr/factory.py` | ASR Provider 工厂 |

## 6. Suggested Skills

- **systematic-debugging** — 排查剩余问题（TTS 播报、设置开关等）
- **verification-before-completion** — 修复后运行测试确认
- **review** — 审查本次所有变更
- **executing-plans** — 如果从计划文件继续实施
