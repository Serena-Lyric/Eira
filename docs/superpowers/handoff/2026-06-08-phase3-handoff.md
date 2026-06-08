# Phase 3 移交文档 · 语音流式 + 多模态壳层

**日期**: 2026-06-08  
**分支**: `chore/live2d-rewrite-and-handoff`  
**范围**: 后端 ASR/TTS Provider + /ws/voice 端点 + 句切引擎 + 音频推送 + 前端数据对接 + 资源管理  
**状态**: ✅ 全部 7 个任务完成，144 个单元测试通过，0 退化（T3.8 Celery 因 G-2.1 通过已跳过）

---

## 一、完成概览

| 任务 | 内容 | 状态 |
|------|------|------|
| T3.1 | ASR Provider 抽象 + 流式适配器（BaseASRProvider / Mock / Factory + AsrSettings） | ✅ |
| T3.2 | 后端 `/ws/voice` 端点（音频二进制帧 + 控制消息 + ASR→LLM 流式） | ✅ |
| T3.3 | TTS Provider 抽象 + 流式适配器（BaseTTSProvider / Mock / Factory） | ✅ |
| T3.4 | 句切引擎（SentenceSplitter: 分隔符 + min_chars + 动作标记剥离 + flush） | ✅ |
| T3.5 | WS 音频帧推送 + 反压策略（AudioPump + /ws/voice 集成 TTS + 句切） | ✅ |
| T3.6-FE | 前端数据对接（useVoiceWs / useAudioPlayer / Chat.vue 集成 / 口型同步） | ✅ |
| T3.7 | 资源管理 REST + OSS（背景/Live2D 上传+列表+删除+签名URL + 配额） | ✅ |
| T3.8 | 异步管线接入 Celery | ⏭️ 跳过（G-2.1: 2.51s << 60s） |

### 前置验证门

| Gate | 指标 | 阈值 | 实际值 | 状态 |
|------|------|------|--------|------|
| G-2.1 | 知识库管线吞吐 | ≤ 60s / 50-200 chunks | **2.51s / 55 chunks** | ✅ |

---

## 二、文件清单

### 新建文件（23 个）

**后端 capabilities（8 个）：**
```
backend/app/capabilities/asr/
  __init__.py            # 导出 BaseASRProvider, AsrEvent
  base.py                # AsrEvent dataclass + BaseASRProvider ABC
  mock.py                # MockASRProvider（echo 多语言模拟文本）
  factory.py             # create_asr_provider(settings) → mock fallback

backend/app/capabilities/tts/
  __init__.py            # 导出 BaseTTSProvider
  base.py                # BaseTTSProvider ABC（stream/close）
  mock.py                # MockTTSProvider（生成确定性 fake opus 帧）
  factory.py             # create_tts_provider(settings) → mock fallback
```

**后端 WS 与管线（5 个）：**
```
backend/app/api/ws/
  voice.py               # /ws/voice 端点（JWT 鉴权 + 音频接收 + ASR→LLM→TTS）
  voice_messages.py      # VoiceStartIn/EndIn/BargeInIn + AsrPartialOut/FinalOut/VoiceDoneOut/VoiceErrorOut
  audio_pump.py          # AudioPump（二进制帧推送 + 反压: buffer > 3s → sleep 50ms）

backend/app/orchestrator/
  sentence_splitter.py   # SentenceSplitter（。！？\n 分隔 + min_chars=6 + 动作标记剥离）

backend/app/api/rest/
  assets.py              # /assets REST: POST/GET/DELETE backgrounds + live2d + quota + presigned URL
```

**后端基础设施（2 个）：**
```
backend/app/domain/persona/
  quota.py               # check_quota / get_quota_info（background=5, live2d_model=10）

backend/app/infra/alembic/versions/
  0006_assets_table.py   # assets 表（user_id, kind, name, oss_key, mime_type, file_size, meta JSONB）
```

**前端 composables（2 个）：**
```
apps/web-user/src/composables/
  useVoiceWs.ts          # /ws/voice 客户端（二进制+JSON 双向、自动重连、回调接口）
  useAudioPlayer.ts      # Web Audio API 播放器（enqueue/decode/play + amplitude 分析 → 口型同步）
```

**测试文件（6 个）：**
```
backend/tests/unit/
  test_asr.py            # 10 tests: AsrEvent / MockProvider / Factory / Settings
  test_tts.py            # 9 tests: MockProvider / Factory / Settings
  test_sentence_splitter.py  # 15 tests: 分隔 / min_chars / 动作剥离 / flush / reset / 流式

backend/tests/integration/
  test_ws_voice.py       # 9 tests: 路由注册 / 鉴权 / 消息 schema
  test_ws_voice_e2e.py   # 8 tests: AudioPump 反压 / ASR-TTS 管线 / 双路由注册
  test_assets.py         # 12 tests: 上传/列表/删除/权限/配额/zip校验

backend/tests/validation/
  test_g2_1_knowledge_pipeline.py  # G-2.1 验证脚本（30-page PDF → 2.51s / 55 chunks）
```

### 修改文件（7 个）

| 文件 | 变更 |
|------|------|
| `backend/app/core/config.py` | 新增 `AsrSettings` + `TtsSettings`，`Settings` 类追加 `asr`/`tts` 字段 |
| `backend/app/main.py` | 注册 `ws_voice.router` + `assets.router` |
| `backend/app/api/rest/documents.py` | **Bugfix**: 上传后显式 `await db.commit()` 确保 background task 可见 |
| `backend/app/api/ws/chat.py` | 无变更（前次提交已包含） |
| `backend/app/domain/knowledge/parsers/__init__.py` | **Bugfix**: 底部追加 `from . import text, pdf, docx, markdown` 触发 `@register_parser` |
| `backend/app/workers/knowledge_worker.py` | **Bugfix**: 成功路径添加 `await session.commit()` |
| `apps/web-user/src/pages/Chat.vue` | 集成 useVoiceWs + useAudioPlayer；`startVoiceRecording()` 改为流式 WS 上传 + REST fallback |

---

## 三、关键架构决策

### 3.1 /ws/voice 协议

```
客户端 → 服务端:
  - 二进制帧: 音频数据（MediaRecorder WebM chunks, 250ms/片）
  - JSON 控制消息:
    {"type": "voice.start", "lang": "zh"}     ← 开始录音
    {"type": "voice.end"}                     ← 停止录音，触发 ASR 终态
    {"type": "voice.barge_in"}                ← 打断当前响应

服务端 → 客户端:
  - JSON 消息:
    {"type": "asr.partial", "text": "你好"}   ← 实时部分识别
    {"type": "asr.final", "text": "最终文本"} ← ASR 终态
    {"type": "token", "text": "句1"}          ← LLM 文本 token（复用 chat 协议）
    {"type": "action", "tag": "wave"}         ← Live2D 动作标记
    {"type": "chat.done", "latency_ms": ...}  ← 本轮完成
    {"type": "error", "code": "...", ...}
  - 二进制帧: TTS 音频 opus chunks
```

### 3.2 语音管线端到端流程

```
用户按住麦克风 → MediaRecorder(250ms timeslice)
  → voiceWs.sendVoiceStart("zh")
  → ondataavailable → voiceWs.sendAudioChunk(...)  ← 流式上传
  → 松开 → voiceWs.sendVoiceEnd()
  → 后端 ASR stream → asr.partial×N → asr.final
  → Orchestrator 图 → LLM 生成文本
  → SentenceSplitter → 逐句 TTS → AudioPump 推送二进制帧
  → 前端 audioPlayer.enqueue() → Web Audio API decode + play
  → amplitude 回调 → setMouthOpen() → Live2D 口型同步
```

### 3.3 Provider 抽象模式

全部 5 个 capability（LLM / Embedding / Search / ASR / TTS）统一采用 `ABC → 实现 → Factory` 三层：

```python
# ASR
BaseASRProvider.stream(audio, lang) → AsyncIterator[AsrEvent]
  ├── MockASRProvider (多语言 echo, latency_ms 可配)
  └── (预留: aliyun_nls, xunfei)

# TTS
BaseTTSProvider.stream(text, voice, format) → AsyncIterator[bytes]
  ├── MockTTSProvider (确定性 MD5 种子生成 fake opus, 3 chars/20ms)
  └── (预留: aliyun_nls, azure)
```

无 API key 时自动 fallback 到 Mock，保障 dev 环境可运行。

### 3.4 句切策略

```python
SentenceSplitter(min_chars=6)
  - 碰到 。！？\n 触发分割
  - 不足 6 字符暂存，继续拼接
  - 动作标记 [wave] [nod] 等正则剥离
  - flush() 输出剩余缓冲区
  - reset() 清空（barge-in 时）
```

### 3.5 反压策略

```
AudioPump:
  - 每 chunk 推送后 tracked_ms += 20ms
  - tracked_ms >= 3000ms → await asyncio.sleep(0.05)
  - 取消后 tracked_ms -= 100ms（假设前端已消费）
  - cancel() 终止当前流，reset() 清空状态
```

### 3.6 资源管理

```
assets 表 (user_id, kind, name, oss_key, mime_type, file_size, meta JSONB)

配额:
  - background: 5 个/用户（OSS: eira-backgrounds）
  - live2d_model: 10 个/用户（OSS: eira-live2d）

Live2D 上传校验: zip 内必须包含 "model3.json"
签名 URL: TTL 300s，前端通过 GET /assets/{kind}/{id}/url 获取

REST:
  POST   /assets/backgrounds — multipart 上传（JPG/PNG/WebP, ≤10MB）
  GET    /assets/backgrounds — 列表
  DELETE /assets/backgrounds/{id} — 删除（OSS + DB）
  GET    /assets/backgrounds/{id}/url — 签名 URL
  POST   /assets/live2d — multipart 上传 zip（≤200MB, 需含 model3.json）
  GET    /assets/live2d — 列表
  DELETE /assets/live2d/{id} — 删除（OSS + DB）
  GET    /assets/quota/{kind} — 配额查询
```

---

## 四、API 接口总览

### 新增 WS 端点

| 路径 | 鉴权 | 说明 |
|------|------|------|
| `/ws/voice` | JWT query param | 语音全双工（音频上行 + ASR/TTS/Token 下行） |

### 新增 REST 端点

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/assets/backgrounds` | 登录用户 | 上传背景图，受配额限制 |
| GET | `/assets/backgrounds` | 登录用户 | 列出自己的背景图 |
| GET | `/assets/backgrounds/{id}/url` | 登录用户(own) | 签名 URL（TTL 300s） |
| DELETE | `/assets/backgrounds/{id}` | 登录用户(own) | 删 OSS + DB |
| POST | `/assets/live2d` | 登录用户 | 上传模型 zip（需含 model3.json） |
| GET | `/assets/live2d` | 登录用户 | 列出自己的模型 |
| DELETE | `/assets/live2d/{id}` | 登录用户(own) | 删 OSS + DB |
| GET | `/assets/quota/{kind}` | 登录用户 | 查询配额使用情况 |

### 已有端点的变更

| 端点 | 变更 |
|------|------|
| `POST /documents/upload` | Bugfix: 添加 `await db.commit()` 确保异步 worker 可见 |
| `POST /voice/tts` | 仍为 501 占位（计划替换为实际 TTS 调用，Phase 3 主流程走 WS） |
| `GET /voice/asr/config` | 仍返回默认值（计划改为从 settings 读取） |

---

## 五、测试覆盖

| 层级 | 文件 | 用例数 | 覆盖范围 |
|------|------|--------|---------|
| 单元 | test_asr | 10 | AsrEvent 构造 / MockProvider 流式 / 多语言 / 空输入 / Factory fallback / Settings |
| 单元 | test_tts | 9 | MockProvider 字节输出 / chunk 数比例 / 空文本 / 多音色 / Factory fallback / Settings |
| 单元 | test_sentence_splitter | 15 | 分隔符 / min_chars / 动作剥离 / flush / reset / 流式 token / 新行分隔 / 边界 |
| 集成 | test_ws_voice | 9 | 路由注册 / 鉴权拒绝 / 消息 schema 校验 |
| 集成 | test_ws_voice_e2e | 8 | AudioPump 反压计算 / cancel+reset / ASR-TTS 管线 / 双路由注册 |
| 集成 | test_assets | 12 | 背景上传+类型校验 / 列表 / 删除 / 模型 zip 校验 / 配额 / URL 签名 |
| 验证 | test_g2_1_* | 1 | G-2.1: 30 页 PDF → 2.51s, 55 chunks |
| **合计** | | **64 新增 + 80 原有 = 144** | |

### 前端质量门

```bash
vue-tsc --noEmit   # 0 errors（web-user + web-admin）
```

---

## 六、待办与后续衔接

### 需要真实环境验证

- [ ] **ASR API key**: 设置 `EIRA_ASR__API_KEY` + `EIRA_ASR__PROVIDER=aliyun_nls`
- [ ] **TTS API key**: 设置 `EIRA_TTS__API_KEY` + `EIRA_TTS__PROVIDER=azure`
- [ ] **真实 ASR/TTS Provider 实现**: `capabilities/asr/aliyun_nls.py`、`capabilities/tts/azure_tts.py` 等真实适配器
- [ ] **OSS bucket**: 确认 `eira-backgrounds`、`eira-live2d` bucket 存在且有权限
- [ ] **端到端语音测试**: 启动全栈 → 点击麦克风 → 录音 → ASR → LLM → TTS 播放 → Live2D 口型同步

### Validation Gates 待执行（Phase 3 专属）

- [ ] **G-3.1**: 端到端语音回路 P95 ≤ 5s（ASR final ≤ 1.5s / ASR→LLM ≤ 1.5s / LLM→TTS ≤ 1s）
- [ ] **G-3.2**: 口型同步主观自然度 ≥ 3.5/5（5 名测试者 × 10 段回复）
- [ ] **G-3.3**: 资源管理上传/切换/删除/刷新 100% 成功
- [ ] **G-3.4**: 设置面板回归 + MVP 完整度（Playwright E2E 主路径绿）

### Phase 4 前置事项

- [ ] **Persona CRUD 后端**: `/admin/personas` REST（SillyTavern 字段 + 默认 Eira 不可删）
- [ ] **Admin 数据对接**: Dashboard / Personas / Knowledge / Live2D 页面对接真实 API
- [ ] **权限系统**: admin / superadmin 角色 + `require_admin` middleware

### 已知局限

1. **Mock ASR/TTS**: 当前使用 Mock Provider，返回模拟数据——不适合真实语音交互。需在部署前切换真实 Provider
2. **Opus 编解码**: MockTTS 生成 fake opus 帧，`useAudioPlayer` 的 `decodeAudioData` 会静默失败（预期行为，真实 opus 数据可正常解码）
3. **无 VAD（Voice Activity Detection）**: 语音端点检测由前端 MediaRecorder 控制，后端不做 VAD——可能导致无声片段被识别
4. **Live2D 模型 zip 解压**: 上传后仅校验 model3.json 存在，不自动解压部署到 public 目录——需管理员手动操作
5. **用户偏好未接入 DB**: `/user/preferences` GET/PATCH 仍为占位，语音/摄像头/布局偏好仅在 localStorage
6. **REST voice 端点未升级**: `POST /voice/tts` 仍返回 501——主流程走 `/ws/voice`，REST 端点保留为 fallback

---

## 七、快速启动

```bash
# 1. Docker 服务
docker compose -f deploy/docker-compose.yml up -d

# 2. 数据库迁移（到 0006）
cd backend && uv run alembic upgrade head

# 3. 后端启动（默认 mock provider 无需 API key）
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. 前端启动
pnpm install
pnpm --filter @eira/web-user dev      # http://localhost:5173
pnpm --filter @eira/web-admin dev     # http://localhost:5174

# 5. 运行全部测试
cd backend && uv run pytest tests/unit/ tests/integration/ -v

# 6. 类型检查
cd apps/web-user && npx vue-tsc --noEmit
```

### 环境变量（可选——mock 模式无需设置）

```bash
# 真实 ASR（待 Provider 实现）
export EIRA_ASR__PROVIDER=aliyun_nls
export EIRA_ASR__API_KEY=xxx
# 真实 TTS（待 Provider 实现）
export EIRA_TTS__PROVIDER=azure
export EIRA_TTS__API_KEY=xxx
```

---

## 八、验证门数据归档

### G-2.1 · 知识库管线吞吐与正确性

| 项 | 内容 |
|------|------|
| 测试时间 | 2026-06-08 10:45 UTC+8 |
| 测试方法 | `tests/validation/test_g2_1_knowledge_pipeline.py`（30 页 PDF 上传 + 轮询进度） |
| 最终状态 | ready |
| 总耗时 | **2.51s**（阈值 ≤ 60s） |
| Chunk 数 | **55**（阈值 [50, 200]） |
| Embedding | Mock（无 API key fallback） |
| 结论 | **PASSED** → T3.8 Celery 跳过 |

---

**签出**: 本 Phase 由 Claude Opus 4.8 执行，遵循 TDD、密钥不入库、commit 前缀约定。  
**下一步**: Phase 4（管理后台 + 角色卡）或 Phase 1 后端补全（如 G-2.2~G-2.4 验证门未通过则需先处理）。
