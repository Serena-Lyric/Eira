---
name: 2026-05-26-phase3-voice-multimodal-shell
title: Phase 3 · 语音流式 + 多模态壳层
date: 2026-05-26
status: draft
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
overview: docs/superpowers/plans/2026-05-26-overview.md
prev: docs/superpowers/plans/2026-05-26-phase2-knowledge-rag.md
---

# Phase 3 实施计划 · 语音流式 + 多模态壳层

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Phase 1/2 的文本闭环升级为"全双工语音 + Live2D 口型 + 摄像头小窗 + 设置面板 + 资源管理（背景/模型）"的 MVP 完整壳层。语音问答 P95 ≤ 5s（spec 锁定 KPI）。

**Architecture:**
- ASR：流式 WS（云阿里 NLS / Azure / 讯飞），前端 MediaRecorder → WS 二进制帧 → 后端 ASR Provider → 增量识别文本回传 + final → 自动触发 LLM。
- TTS：边出 LLM token 边按句切句 → TTS Provider 流式合成 mp3/opus → WS 推音频帧 → 前端 Web Audio API 顺序播放，同时按音频播放进度驱动 Live2D 嘴巴参数（口型同步）。
- 摄像头小窗：getUserMedia → 本地 video 元素，可切换前后置，可关闭；本 phase **不上传图像**（图像识别留 Phase 7）。
- 设置面板：玻璃磨砂 Modal，控制麦克风/语音/小窗/文字框/快捷问/背景/Live2D 模型/角色卡（最后一个 + 删除约束）。
- 资源管理：背景图片/视频与 Live2D 模型上传到 OSS，前端通过签名 URL 拉取；用户级隔离。

**Tech Stack:** 前端 `MediaRecorder`（webm/opus）、`Web Audio API`、`pixi-live2d-display` 嘴形参数、`getUserMedia`；后端 ASR/TTS Provider 抽象（同 LLM 模式）、`pydub` / `ffmpeg-python`（仅必要时做格式转换）。

**前置条件：** Phase 1 + Phase 2 全部 Validation Gate passed。

**本 Phase 不做：** 图像识别（Phase 7）、用户语音持久化（默认关，spec 已锁）、长期记忆抽取（Phase 6）。

**重述全局约定：** TDD；commit 前缀；密钥不入库；用户音频默认不持久化；OSS 全部走签名 URL；验证门数据归档。

---

## 任务依赖图

```
T3.1 ASR Provider 抽象 + 阿里 NLS 适配器（流式）
  ↓
T3.2 后端 /ws/voice 端点（前端音频帧 → ASR → 触发 chat 图）
  ↓
T3.3 TTS Provider 抽象 + Azure/Aliyun 适配器（流式）
  ↓
T3.4 句切引擎（LLM token → 完整句 → 喂 TTS）
  ↓
T3.5 WS 音频帧推送（mp3/opus 增量）
  ↓
T3.6 前端录音模块 useMicRecorder
  ↓
T3.7 前端音频播放器 useAudioPlayer（顺序队列）
  ↓
T3.8 Live2D 口型同步（音频幅值 → ParamMouthOpenY）
  ↓
T3.9 摄像头小窗 useCamera（前后置切换 / 关闭）
  ↓
T3.10 设置面板 SettingsPanel（开关 / 上传 / 角色卡列表）
  ↓
T3.11 背景上传与渲染（图片/视频，cover/contain/center/stretch/free）
  ↓
T3.12 Live2D 模型上传与切换（zip / 文件夹）
  ↓
T3.13 资源管理 REST + OSS 路由
  ↓
T3.14 异步管线接入 Celery（替换 Phase 2 的 BackgroundTasks）
  ↓
🚦 G-3.1 / G-3.2 / G-3.3 / G-3.4
```

---

## Task 3.1: ASR Provider 抽象 + 流式适配器

**Files:**
- Create: `backend/app/capabilities/asr/__init__.py`
- Create: `backend/app/capabilities/asr/base.py`
- Create: `backend/app/capabilities/asr/aliyun_nls.py`
- Create: `backend/app/capabilities/asr/factory.py`
- Modify: `backend/app/core/config.py`（追加 AsrSettings）
- Create: `backend/tests/unit/test_asr_aliyun.py`（VCR / 录制）

> ⚠️ **要点**：
> - 接口：`async def stream(audio: AsyncIterator[bytes], lang="zh") -> AsyncIterator[AsrEvent{kind, text, is_final}]`。
> - 输入音频格式由 Provider 决定（阿里 NLS：opus/pcm/16k；Azure：pcm/16k/16bit）；前端将 webm/opus 直接喂入，后端 Provider 适配器内部处理（必要时 ffmpeg 转码）。
> - 心跳：每 5 秒发送一个空帧或保持 ws 连接活跃；超时 30 秒未收到音频自动 close。
> - 必填日志：`provider/duration_ms/audio_bytes/text_chars/latency_first_partial_ms`。

- [ ] **Step 1: 失败测试**

```python
# tests/unit/test_asr_aliyun.py
import pytest, pathlib
from app.capabilities.asr.factory import build_asr

@pytest.mark.vcr
@pytest.mark.asyncio
async def test_stream_returns_partial_and_final():
    p = build_asr("aliyun-nls")
    sample = pathlib.Path("tests/fixtures/audio/hello-zh.opus").read_bytes()
    chunks = [sample[i:i+4096] for i in range(0, len(sample), 4096)]
    async def feed():
        for c in chunks: yield c
    seen_partial = False
    final_text = ""
    async for ev in p.stream(feed(), lang="zh"):
        if ev.kind == "partial": seen_partial = True
        if ev.is_final: final_text = ev.text
    assert seen_partial and final_text
```

> 准备 fixture `tests/fixtures/audio/hello-zh.opus`（"你好"约 1 秒）。

- [ ] **Step 2/3: 实现 + 验证 + 提交**

base/factory 与 LLM 同模板。`aliyun_nls.py` 使用阿里 NLS 流式 SDK 或自实现 WS 协议。返回事件统一：

```python
@dataclass
class AsrEvent:
    kind: Literal["partial", "final"]
    text: str
    is_final: bool
    confidence: float = 0.0
    audio_offset_ms: int = 0
```

提交：`feat(asr): provider abstraction with aliyun nls streaming adapter`。

> ⚠️ **延伸**：实测时如果阿里 NLS 协议复杂可优先做 Azure Speech 适配器（SDK 体验好），评测后再决定默认。

---

## Task 3.2: 后端 /ws/voice 端点

**Files:**
- Create: `backend/app/api/ws/voice.py`
- Create: `backend/app/api/ws/voice_messages.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/integration/test_ws_voice.py`

协议：

```
client → server (二进制): 音频帧（webm/opus，~50ms 一帧）
client → server (text): {"type":"start","session_id":1,"lang":"zh","model":"deepseek-chat"}
client → server (text): {"type":"end"}                # 强制 finalize 当前句
client → server (text): {"type":"barge_in"}            # 打断 TTS（spec D-4 预留）
server → client: {"type":"asr.partial","text":"..."}
server → client: {"type":"asr.final","text":"..."}     # 触发 chat 图
server → client: {"type":"chat.token","text":"..."}    # 同 /ws/chat
server → client (二进制): TTS 音频帧（mp3/opus）+ {"type":"audio.chunk_meta","seq":1,"sentence_id":2}
server → client: {"type":"chat.done","message_id":...}
```

实现要点：
- 后端起 ASR provider 流式连接 → 在 final 事件后调用 chat orchestrator → 把 LLM token → 句切 → TTS → ws 推音频（T3.4/T3.5）。
- 每路连接绑定一个 `BroadcastSet`（asr/tts/llm 三个 task），任一异常 → 取消其他 + 发送 error 帧 + close。

提交：`feat(ws): /ws/voice with asr→llm→tts pipeline scaffold`。

---

## Task 3.3: TTS Provider 抽象

**Files:**
- Create: `backend/app/capabilities/tts/__init__.py`
- Create: `backend/app/capabilities/tts/base.py`
- Create: `backend/app/capabilities/tts/aliyun_nls.py`
- Create: `backend/app/capabilities/tts/azure_tts.py`
- Create: `backend/app/capabilities/tts/factory.py`
- Modify: `backend/app/core/config.py`（追加 TtsSettings 含 voice / speed / format）
- Create: `backend/tests/unit/test_tts.py`

> ⚠️ **要点**：
> - 接口：`async def stream(text: str, voice: str, format: Literal["mp3","opus"]="opus") -> AsyncIterator[bytes]`。
> - 音频格式：默认 `opus@24kHz` 节省带宽；浏览器解码兼容性差时降级 `mp3@22.05kHz`。
> - **流式合成**：边输出边返回 chunk，**不要**等整段合成完毕。Azure SDK 原生支持；阿里 NLS 也提供流式。
> - 同时记录 `audio_offset_ms`（首字节相对开始时刻），便于前端时间轴对齐与口型同步。

- [ ] **Step 1/2: 测试 + 实现 + 提交**

```python
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_tts_stream_returns_chunks():
    p = build_tts("azure-zh-female")
    chunks = []
    async for b in p.stream("你好，欢迎来到颐和园。", voice="zh-CN-XiaoxiaoNeural"):
        chunks.append(b)
    blob = b"".join(chunks)
    assert len(blob) > 1024  # 起码 1KB 音频
```

提交：`feat(tts): provider abstraction with azure/aliyun adapters`。

---

## Task 3.4: 句切引擎

**Files:**
- Create: `backend/app/orchestrator/sentence_splitter.py`
- Create: `backend/tests/unit/test_sentence_splitter.py`

> 把 LLM 流出的 token 累积到"完整句"为止再喂 TTS，否则 TTS 输出会割裂。判定：碰到 `。！？\n`（最少 6 字）；连续 1.5s 无新 token 也强制 flush；标记 `[wave]` 之类动作 tag 不计入 TTS 文本但需保留位置。

```python
@dataclass
class Sentence:
    seq: int
    text: str       # 已剥离动作标记
    actions: list[tuple[int, str]]  # (offset_in_text, tag)

class SentenceSplitter:
    def __init__(self): self._buf = ""; self._seq = 0
    def feed(self, delta: str) -> list[Sentence]: ...
    def flush(self) -> list[Sentence]: ...
```

测试：feed 多次部分文本 → 期望返回的句子列表 boundary 正确 + actions 位置正确。

提交：`feat(orchestrator): sentence splitter for llm→tts pipeline`。

---

## Task 3.5: WS 音频帧推送 + 节流策略

**Files:**
- Modify: `backend/app/api/ws/voice.py`（接入 sentence_splitter + tts.stream）
- Create: `backend/app/api/ws/audio_pump.py`（asyncio.Queue 调度）
- Create: `backend/tests/integration/test_ws_voice_e2e.py`

> ⚠️ **要点**：
> - 每生成一句完整句立即送 TTS；TTS 字节流即推 ws；客户端解码消费。
> - 反压：若 ws 发送速率跟不上（前端 buffer > 3s），后端限速：`await asyncio.sleep(0.05)` 喂入。
> - 句间标记 `audio.sentence_meta{seq, text_len, expected_duration_ms}`；客户端用于口型同步基准。

提交：`feat(ws): streaming audio pump with backpressure`。

---

## Task 3.6: 前端录音 useMicRecorder

**Files:**
- Create: `apps/web-user/src/composables/useMicRecorder.ts`
- Modify: `apps/web-user/src/pages/Chat.vue`（接入麦克风按钮）
- Create: `apps/web-user/src/services/voiceWs.ts`（包装 /ws/voice）
- Create: `apps/web-user/tests/unit/useMicRecorder.spec.ts`

```typescript
export function useMicRecorder() {
  const recording = ref(false)
  let stream: MediaStream | null = null
  let recorder: MediaRecorder | null = null
  const onChunk = ref<(buf: ArrayBuffer)=>void>()
  async function start() {
    stream = await navigator.mediaDevices.getUserMedia({ audio: {
      sampleRate: 16000, channelCount: 1, noiseSuppression: true,
      echoCancellation: true, autoGainControl: true,
    } })
    recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus", audioBitsPerSecond: 32000 })
    recorder.ondataavailable = async (e) => {
      if (e.data.size > 0) onChunk.value?.(await e.data.arrayBuffer())
    }
    recorder.start(50)  // 50ms 一帧
    recording.value = true
  }
  function stop() {
    recorder?.stop(); stream?.getTracks().forEach(t => t.stop())
    recording.value = false
  }
  return { recording, start, stop, onChunk }
}
```

提交：`feat(frontend): mic recorder composable with opus chunks`。

> ⚠️ **要点**：iOS Safari 不支持 webm/opus；MVP 不强制 iOS，但要在错误提示中明确告知。生产支持 iOS 时切 `audio/mp4`（AAC）+ 后端转码。

---

## Task 3.7: 前端音频播放队列 useAudioPlayer

**Files:**
- Create: `apps/web-user/src/composables/useAudioPlayer.ts`

```typescript
export function useAudioPlayer() {
  const ctx = new AudioContext({ sampleRate: 24000 })
  const queue: AudioBuffer[] = []
  let playingUntil = 0
  const onAmplitude = ref<(amp: number)=>void>()

  async function enqueue(bytes: ArrayBuffer) {
    const buf = await ctx.decodeAudioData(bytes.slice(0))
    queue.push(buf); maybePlay()
  }
  function maybePlay() {
    while (queue.length) {
      const buf = queue.shift()!
      const src = ctx.createBufferSource()
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      src.buffer = buf
      src.connect(analyser); analyser.connect(ctx.destination)
      const startAt = Math.max(ctx.currentTime, playingUntil)
      src.start(startAt)
      playingUntil = startAt + buf.duration
      const data = new Uint8Array(analyser.frequencyBinCount)
      const tick = () => {
        analyser.getByteTimeDomainData(data)
        const peak = Math.max(...Array.from(data, v => Math.abs(v - 128) / 128))
        onAmplitude.value?.(peak)
        if (ctx.currentTime < playingUntil) requestAnimationFrame(tick)
        else onAmplitude.value?.(0)
      }
      requestAnimationFrame(tick)
    }
  }
  function clear() { queue.length = 0 }
  return { enqueue, clear, onAmplitude }
}
```

提交：`feat(frontend): web audio queue with amplitude callback`。

---

## Task 3.8: Live2D 口型同步

**Files:**
- Modify: `apps/web-user/src/live2d/Live2DStage.ts`（追加 `setMouthOpen(value)`）
- Modify: `apps/web-user/src/composables/useChatSession.ts`（订阅 amplitude）

```typescript
// in Live2DStage
setMouthOpen(v: number) {
  // v ∈ [0, 1]
  this.model?.internalModel.coreModel.setParameterValueById?.("ParamMouthOpenY", Math.min(1, v * 1.4))
}
```

`useChatSession`:

```typescript
audioPlayer.onAmplitude.value = (amp) => live2dRef.value?.setMouthOpen(amp)
```

> ⚠️ **要点**：基于音频振幅的口型同步精度有限；MVP 可接受。Phase 7 升级方案：Azure Viseme 事件（已携带音素）+ Cubism Lip Sync 标准参数对应表。

提交：`feat(live2d): amplitude-based lip sync`。

---

## Task 3.9: 摄像头小窗 useCamera

**Files:**
- Create: `apps/web-user/src/composables/useCamera.ts`
- Create: `apps/web-user/src/components/CameraPreview.vue`
- Modify: `apps/web-user/src/pages/Chat.vue`（右上角嵌入）

```typescript
export function useCamera() {
  const enabled = ref(false)
  const stream = ref<MediaStream | null>(null)
  const devices = ref<MediaDeviceInfo[]>([])
  const currentIdx = ref(0)
  async function refreshDevices() {
    devices.value = (await navigator.mediaDevices.enumerateDevices())
                     .filter(d => d.kind === "videoinput")
  }
  async function start(idx = 0) {
    const id = devices.value[idx]?.deviceId
    stream.value = await navigator.mediaDevices.getUserMedia({
      video: id ? { deviceId: { exact: id } } : true, audio: false,
    })
    enabled.value = true; currentIdx.value = idx
  }
  function stop() { stream.value?.getTracks().forEach(t => t.stop()); enabled.value = false; stream.value = null }
  function next() { stop(); start((currentIdx.value + 1) % devices.value.length) }
  return { enabled, stream, devices, refreshDevices, start, stop, next }
}
```

`CameraPreview.vue` 圆角磨砂边框 + 默认头像 fallback；点击切换；右上角点 X 关闭。

提交：`feat(frontend): camera preview small window with device switch`。

---

## Task 3.10: 设置面板 SettingsPanel

**Files:**
- Create: `apps/web-user/src/components/SettingsPanel.vue`
- Create: `apps/web-user/src/stores/preferences.ts`（pinia + localStorage）
- Modify: `apps/web-user/src/pages/Chat.vue`（齿轮 icon 触发）

设置项（spec 锁定）：

| 项 | 默认 | 说明 |
|---|---|---|
| 摄像头小窗 | 开 | useCamera enabled |
| 角色语音 TTS | 开 | 关闭则跳过 TTS pipeline，仅文字流 |
| 麦克风按钮 | 开 | 关则隐藏 |
| 文字框位置 | 居中 | 居中 / 左下 / 隐藏 |
| 快捷问 | 后端有则展示 | 显式开关 |
| 背景 | 默认色 | 上传图片/视频，模式 cover/contain/center/stretch/free |
| Live2D 模型 | 默认 Hiyori | 上传切换 |
| 角色模板（角色卡） | 默认 Eira | 列表 + 删除（最后一个不可删） |

提交：`feat(frontend): settings panel + preferences store`。

---

## Task 3.11: 背景上传与渲染

**Files:**
- Create: `backend/app/domain/persona/__init__.py`（占位；Phase 4 才完整）
- Create: `backend/app/api/rest/assets.py`（背景 + 模型 + 头像通用 OSS 上传 endpoint）
- Modify: `backend/app/infra/alembic/versions/0005_assets_table.py`
- Create: `apps/web-user/src/components/SceneBackground.vue`

迁移：

```python
op.create_table(
    "asset",
    sa.Column("id", sa.BigInteger, primary_key=True),
    sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id")),
    sa.Column("kind", sa.String(16), nullable=False),  # background/live2d/avatar
    sa.Column("oss_key", sa.String(255), nullable=False),
    sa.Column("mime_type", sa.String(64), nullable=False),
    sa.Column("size_bytes", sa.BigInteger, nullable=False),
    sa.Column("meta_json", sa.JSON, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True),
              server_default=sa.text("now()"), nullable=False),
)
op.create_check_constraint("ck_asset_kind", "asset",
    "kind IN ('background','live2d','avatar')")
```

REST：

```
POST   /assets               multipart upload (kind, file)
GET    /assets?kind=...      列表（user 级）
DELETE /assets/{id}          删 OSS + DB
GET    /assets/{id}/url      返回签名 URL（TTL 300s）
```

`SceneBackground.vue`：根据 preferences 渲染 image/video，模式 cover/contain/center/stretch/free 用 CSS 实现。

提交：`feat(assets): background upload + scene background renderer`。

---

## Task 3.12: Live2D 模型上传与切换

**Files:**
- Modify: `backend/app/api/rest/assets.py`（kind=live2d 时支持 zip 自动解压）
- Create: `backend/app/domain/persona/live2d_unpacker.py`
- Modify: `apps/web-user/src/components/SettingsPanel.vue`（Live2D 列表 + 切换）
- Modify: `apps/web-user/src/components/Live2DCanvas.vue`（动态切换 modelUrl）

> ⚠️ **要点**：
> - Live2D 模型规范：含 `*.model3.json`、`*.moc3`、`*.physics3.json`、textures、motions、expressions。上传 zip 时后端解压到 `eira-live2d/<asset_id>/`，识别 `model3.json` 入口，存 `meta_json.entry_url`。
> - 前端切换：从 `/assets/{id}/url` 拿到 `entry_url` 签名 URL，直接喂给 `Live2DModel.from(url)`。
> - 上传时校验：必须含 model3.json；总大小 ≤ 50MB（spec 锁定）；解压后路径不允许 `../`（防 zip slip）。

提交：`feat(persona): live2d model upload with zip unpacker`。

---

## Task 3.13: 资源管理 REST + 签名 URL TTL

**Files:**
- Modify: `backend/app/api/rest/assets.py`（统一 list/delete/get_url，配额）
- Create: `backend/app/domain/persona/quota.py`（用户配额）
- Create: `backend/tests/integration/test_assets_quota.py`

> ⚠️ **要点**：
> - 单用户配额（默认）：背景 5 个、Live2D 10 个、文档 100 个；超额 413 返回。admin 可后台改。
> - 签名 URL TTL=300s；前端缓存使用，过期前重新拉取。
> - 禁止上传可执行文件：mime 白名单（image/* video/* application/zip 等）。

提交：`feat(assets): quota + signed url with content-type whitelist`。

---

## Task 3.14: 异步管线接入 Celery（可选，Phase 4 前完成）

**Files:**
- Modify: `deploy/docker-compose.yml`（追加 celery worker）
- Create: `backend/app/workers/celery_app.py`
- Modify: `backend/app/workers/knowledge_worker.py`（@celery.task 化）
- Modify: `backend/app/api/rest/documents.py`（用 Celery delay 替换 BackgroundTasks）

> ⚠️ **触发条件**：Phase 2 G-2.1 中如果耗时 > 60s 且 backend 副本 ≥ 2 时必做；否则可推迟到 Phase 4 后台管理上线前。

提交：`feat(workers): switch knowledge pipeline to celery`。

---

## 🚦 Validation Gate G-3.1 · 端到端语音回路延迟（核心 KPI）

| 项 | 内容 |
|---|---|
| 指标 | 用户开口（手按麦克风）→ Eira 第一段音频 outbound 时刻；分别衡量：录音到 ASR final 时间；ASR final 到 LLM 首 token；LLM 首 token 到 TTS 首 chunk |
| 阈值 | 端到端 P95 ≤ 5s（spec 锁定 KPI）；分项理想：录音到 ASR final ≤ 1.5s；ASR→LLM 首 token ≤ 1.5s；LLM 首 token→TTS 首 chunk ≤ 1s |
| 测试方法 | `scripts/bench_voice_e2e.py`：使用预录音 8 个样本（含中英、长短），用 `websockets` 模拟前端推送音频 + 收音频；记录三个分项的 timestamp |
| 数据源 | 脚本 csv + structlog；归档 `docs/superpowers/validations/G-3.1.md` |
| 通过分支 | 进入 G-3.2 |
| 不通过分支 | 端到端 ∈ (5s, 7s)：(a) 检查 ASR final 是否在用户停顿后 600ms 内触发（vad 调参）；(b) LLM 首 token 慢 → 切 deepseek-chat 海外 endpoint 或换 provider；(c) TTS 慢 → 强制流式 + 减小 voice 资源；> 7s：升级 spec，考虑"本地 ASR fallback（whisper.cpp）" 或 "首句使用极短预制语音过渡"决策 |

---

## 🚦 Validation Gate G-3.2 · 口型同步主观自然度

| 项 | 内容 |
|---|---|
| 指标 | 邀请 5 名内部测试人员对 10 段 Eira 回复打分（5 分制）：嘴形与音频对齐 / 不夸张抖动 / 不延迟 |
| 阈值 | 平均分 ≥ 3.5；无人打 < 3 |
| 测试方法 | 录屏 10 段，让评测者按统一表打分 |
| 数据源 | `docs/superpowers/validations/G-3.2.md` 含评分表 |
| 通过分支 | 进入 G-3.3 |
| 不通过分支 | 抖动严重：amplitude 加 EMA 平滑（α=0.4），并把映射改为非线性（sqrt）；延迟感：检查音频 enqueue 与 mouthOpen 调用是否同帧；< 3 多：升级方案到 Phase 7 的 Viseme 事件路径，本 phase 先记入 spec 修订段不阻塞 |

---

## 🚦 Validation Gate G-3.3 · 资源管理稳定性

| 项 | 内容 |
|---|---|
| 指标 | 上传 5 个背景（含 mp4 50MB）、3 个 Live2D zip → 切换/删除/重启浏览器后状态保留；签名 URL 过期前刷新成功率 |
| 阈值 | 100% 上传成功；切换 ≤ 2s（已加载模型）；签名 URL 过期前 30s 刷新成功率 100% |
| 测试方法 | 手动 + Playwright；脚本观察网络面板 |
| 数据源 | `docs/superpowers/validations/G-3.3.md` 含截图 |
| 通过分支 | 进入 G-3.4 |
| 不通过分支 | 切换慢：在前端缓存已下载模型（Map<id, Live2DModel>）；签名失败：检查刷新逻辑（提前 60s 刷新而非等过期） |

---

## 🚦 Validation Gate G-3.4 · 设置面板回归 + MVP 完整度

| 项 | 内容 |
|---|---|
| 指标 | DESIGN.txt 中用户端 UI 全部要素出现且功能正确：设置齿轮、摄像头小窗、文字框、快捷问、输入框（mic 左 / +/send 右）、Live2D 全屏可拖拽缩放、登录页、角色卡列表（最后一个不可删） |
| 阈值 | 全部勾选 + Playwright E2E 主路径绿 |
| 测试方法 | Playwright spec `tests/e2e/mvp-shell.spec.ts` + UI checklist |
| 数据源 | `docs/superpowers/validations/G-3.4.md` 含 checklist |
| 通过分支 | 合入，标 `gate-G-3-passed`；MVP 视为完整可灰度 |
| 不通过分支 | 任一缺失即不通过；回相应 task |

---

## 完成状态

Phase 3 完成 ⇔ G-3.1 / 3.2 / 3.3 / 3.4 全部 passed。MVP 视为达标，可进入 Phase 4 后台管理。
