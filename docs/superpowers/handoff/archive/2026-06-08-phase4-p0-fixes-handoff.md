# Phase 4 P0 紧急修复 Handoff — 前后端 API 格式不匹配

> 日期: 2026-06-08
> 分支: `chore/live2d-rewrite-and-handoff`
> 范围: 后端 3 文件 + 前端 4 文件

---

## 修复概览

| # | 优先级 | 问题 | 状态 |
|---|--------|------|------|
| P0-1 | 🔴 P0 | AppConfig 保存格式完全不匹配 — 后端返 422，前端静默失败 | ✅ |
| P0-2 | 🔴 P0 | Asset 列表返回格式不匹配 — 表格渲染异常 | ✅ |
| P0-3 | 🔴 P0 | POST /voice/asr 端点缺失 — 语音识别 REST 路径完全不可用 | ✅ |
| — | 🔴 P0 | Alembic 迁移链断裂 — 双 0008 head，所有集成测试无法运行 | ✅ |

---

## 文件清单

### 后端 (业务代码)

| 文件 | 操作 | 涉及问题 |
|------|------|----------|
| `backend/app/api/rest/admin_settings.py` | 修改 | P0-1 |
| `backend/app/domain/system/service.py` | 修改 | P0-1 |
| `backend/app/api/rest/voice.py` | 新增端点 | P0-3 |

### 后端 (迁移修复)

| 文件 | 操作 | 涉及问题 |
|------|------|----------|
| `backend/app/infra/alembic/versions/0008_user_preferences.py` → `0009_user_preferences.py` | 重命名+更新 | 迁移链 |
| `backend/app/infra/alembic/versions/0009_system_setting.py` → `0010_system_setting.py` | 重命名+更新 | 迁移链 |
| `backend/app/infra/alembic/versions/0010_audit_log.py` → `0011_audit_log.py` | 重命名+更新 | 迁移链 |

### 后端 (测试)

| 文件 | 操作 | 涉及问题 |
|------|------|----------|
| `backend/tests/integration/test_admin_settings.py` | 追加 4 测试 | P0-1 |
| `backend/tests/integration/test_admin_assets.py` | 新建 6 测试 | P0-2 |
| `backend/tests/integration/test_voice.py` | 新建 6 测试 | P0-3 |

### 前端

| 文件 | 操作 | 涉及问题 |
|------|------|----------|
| `apps/web-admin/src/services/api.ts` | 修改 | P0-1, P0-2 |
| `apps/web-admin/src/services/types.ts` | 修改 | P0-2 |
| `apps/web-admin/src/pages/Dashboard.vue` | 修改 | P0-2 |
| `apps/web-admin/src/pages/Content/Live2D.vue` | 修改 | P0-2 |

---

## P0-1: AppConfig 保存格式不匹配

### 问题诊断

**前端** (`configApi.update(partial)`):
```typescript
// api.ts 旧代码：直接发送 flat object
http.patch("/admin/settings", partial)
// → 请求体: {llm_provider: "deepseek", llm_model: "deepseek-chat", ...}
```

**后端** (`PATCH /admin/settings`):
```python
# admin_settings.py 旧 schema
class SettingsPatchIn(BaseModel):
    settings: dict[str, dict]  # 期望 {settings: {key: value}}
```

**结果**: 后端 Pydantic 校验失败 → 422 Unprocessable Entity → 前端 `catch` 块只打 `console.log`，保存按钮永远静默失败。

### 修复内容

#### 前端: `apps/web-admin/src/services/api.ts`

```typescript
// configApi.get() — 解包 data.settings
async get(): Promise<AppConfig> {
  const { data } = await http.get("/admin/settings")
  return data.settings ?? data  // ← 后端返回 {settings: {...}}，取 settings
}

// configApi.update() — 包装 {settings: partial}
async update(partial: Partial<AppConfig>): Promise<AppConfig> {
  const { data } = await http.patch("/admin/settings", { settings: partial })
  return data.settings ?? data
}
```

#### 后端: `backend/app/api/rest/admin_settings.py`

```python
# 类型放宽：dict → Any，允许值为 string / int / bool 等非 dict 类型
from typing import Any

class SettingsOut(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)

class SettingsPatchIn(BaseModel):
    settings: dict[str, Any] = Field(description="Key-value pairs to upsert")
```

#### 后端: `backend/app/domain/system/service.py`

```python
# 方法签名同步放宽
from typing import Any

async def get(self, key: str) -> Any | None: ...
async def set(self, key: str, value: Any, description: str = "") -> SystemSetting: ...
async def get_all(self) -> dict[str, Any]: ...
async def set_many(self, settings: dict[str, Any]) -> list[SystemSetting]: ...
```

### 修复后数据流

```
前端 save({llm_provider: "deepseek", ...})
  → wrap → {settings: {llm_provider: "deepseek", ...}}
  → PATCH /admin/settings ✅
  → 后端解析 SettingsPatchIn.settings ✅ (Any 接受 string 值)
  → set_many({llm_provider: "deepseek", ...}) ✅
  → JSONB 存储 ✅
  → 返回 {settings: {llm_provider: "deepseek", ...}}
  → 前端 unwrap data.settings → {llm_provider: "deepseek", ...} ✅
```

---

## P0-2: Asset 列表返回格式不匹配

### 问题诊断

**前端** (`assetApi.list()`):
```typescript
// 声明返回 Asset[]，直接将响应赋给数组
async list(): Promise<Asset[]> {
  const { data } = await http.get("/admin/assets")
  return data  // ← 实际返回 {items: [...], total: number}
}
```

**前端 Asset 类型**（旧）:
```typescript
interface Asset {
  id: number; name: string
  type: "live2d_model" | "background_image" | "background_video"  // ← 不存在
  is_default: boolean           // ← 后端无此字段
  file_size_bytes: number       // ← 后端字段名 file_size
  uploaded_at: string           // ← 后端字段名 created_at
}
```

**后端返回** (`AdminAssetListOut`):
```python
class AdminAssetListOut(BaseModel):
    items: list[AdminAssetOut]
    total: int

class AdminAssetOut(BaseModel):
    id: int; kind: str; name: str; mime_type: str | None
    file_size: int | None; user_id: int; created_at: str | None
```

**结果**: `Dashboard.vue:556` 和 `Content/Live2D.vue:73` 直接将 `{items, total}` 赋给 `Asset[]`。`data-table` 期望数组但收到对象，模板中 `row.type` 访问 `undefined`，类型标签渲染为空。

### 修复内容

#### 前端: `apps/web-admin/src/services/types.ts`

```typescript
// Asset 接口对齐 AdminAssetOut
export interface Asset {
  id: number
  kind: string                    // ← 原 type
  name: string
  mime_type: string | null        // ← 新增
  file_size: number | null        // ← 原 file_size_bytes
  user_id: number                 // ← 新增
  created_at: string | null       // ← 原 uploaded_at
  is_default?: boolean            // ← 改为可选（后端不支持，始终 false）
}
```

#### 前端: `apps/web-admin/src/services/api.ts`

```typescript
async list(): Promise<Asset[]> {
  const { data } = await http.get("/admin/assets")
  return data.items ?? data  // ← 解包 items 数组
}
```

#### 前端: Dashboard.vue + Live2D.vue

```typescript
// typeLabel 对齐后端 kind 值
const assetTypeLabel: Record<string, string> = {
  live2d_model: 'Live2D Model',
  background: 'Background',        // ← 原 background_image / background_video
}

// 列定义 key: 'type' → 'kind'
{ title: '类型', key: 'kind',
  render(row: Asset) {
    return h(NTag, { type: row.kind === 'live2d_model' ? 'info' : 'warning' },
      { default: () => assetTypeLabel[row.kind] || row.kind })
  },
}
```

---

## P0-3: POST /voice/asr 端点缺失

### 问题诊断

**前端** (`voiceApi.sendAudio()`):
```typescript
// web-user/src/services/api.ts
async sendAudio(audioBlob: Blob): Promise<{ text: string }> {
  const fd = new FormData()
  fd.append('audio', audioBlob, 'recording.webm')
  const { data } = await http.post("/voice/asr", fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
```

**后端路由表**: `voice.py` 中只有 `POST /voice/tts` 和 `GET /voice/asr/config`，无 `POST /voice/asr`。

**结果**: 语音识别 REST 路径返回 404。前端 `useVoiceWs.ts` 的 fallback 路径完全不可用。

### 修复内容

#### 后端: `backend/app/api/rest/voice.py`

**新增 schema**:
```python
class AsrResultOut(BaseModel):
    """ASR 识别结果。"""
    text: str = Field(description="识别出的文本内容")
```

**新增端点**:
```python
@router.post("/asr", response_model=AsrResultOut, summary="语音识别（REST fallback）")
async def speech_to_text(
    audio: UploadFile = File(..., description="音频文件（webm / wav / mp3 等）"),
    user: User = Depends(get_current_user),
) -> AsrResultOut:
    """将语音音频识别为文本。

    异步方式：读取完整音频后一次性送入 ASR provider 进行识别。
    实时语音识别应优先使用 WebSocket（/ws/voice）。
    """
    from app.core.config import get_settings
    from app.capabilities.asr.factory import create_asr_provider

    settings = get_settings()
    provider = create_asr_provider(settings.asr)

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="音频文件为空")

    try:
        # 分块送入 streaming 接口（4096 字节/chunk）
        async def _audio_chunks():
            chunk_size = 4096
            for i in range(0, len(audio_bytes), chunk_size):
                yield audio_bytes[i : i + chunk_size]

        final_text = ""
        async for event in provider.stream(_audio_chunks()):
            final_text = event.text
            if event.is_final:
                break

        return AsrResultOut(text=final_text)
    finally:
        await provider.close()
```

### 架构说明

```
前端 sendAudio(blob)
  → POST /voice/asr (multipart/form-data)
  → speech_to_text()
    → create_asr_provider(settings.asr)
      ├─ provider == "mock" → MockASRProvider (返回模拟中文文本)
      ├─ 无 api_key → fallback MockASRProvider
      └─ 未来: aliyun_nls / xunfei 真实 provider (工厂已预留)
    → provider.stream(audio_chunks)
      → 收集 AsrEvent，提取 is_final=true 的 text
  → 返回 {text: "你好，今天天气不错..."}
```

**注意**: 开发/测试环境下 ASR 使用 Mock provider，返回固定中文模拟文本，不依赖任何外部服务。配置真实 API key 后自动切换。

---

## 已知遗留问题

### 1. Asset 上传路径不匹配（未修复）

前端 `assetApi` 的 upload 路径与后端实际路由不一致：

| 前端调用 | 后端实际端点 |
|----------|-------------|
| `POST /admin/assets/live2d` | `POST /assets/live2d` (用户路由，无 admin 前缀) |
| `POST /admin/assets/background` | `POST /assets/backgrounds` (用户路由，且路径有 `s`) |
| `POST /admin/assets/{id}/set-default` | **不存在** |

**影响**: Admin 面板上传 Live2D / 背景图功能不可用，设置默认资产功能不可用。

**建议**: 在 `admin_assets.py` 中添加 admin 专有的 upload 和 set-default 端点，或让前端调用已有的 user-facing `/assets/*` 端点。

### 2. Asset `is_default` 字段后端不支持

当前后端 assets 表没有 `is_default` 列。前端 `Asset` 类型中 `is_default` 设为可选（始终 `undefined` → 渲染为 "否"）。`setDefault` 按钮的存在暗示此功能需要后端支持。

**建议**: 在 assets 表中添加 `is_default` 字段，实现设置/取消默认资产的逻辑（设置一个为默认时清除同类其他默认）。

---

## 附随修复: Alembic 迁移链断裂

**问题**: 两个文件共享 revision `0008`（`0008_persona_table.py` + `0008_user_preferences.py`），产生双头分支，`alembic upgrade head` 报错，导致所有集成测试无法运行（DB 停留在 0006，缺少 `users.disabled` 等列）。

**修复**: 重编号为线性链:
```
0007 → 0008(persona) → 0009(user_preferences) → 0010(system_setting) → 0011(audit_log)
```

**涉及文件**: `backend/app/infra/alembic/versions/0008_user_preferences.py` → `0009_user_preferences.py`（重命名 + revision/branch 更新），`0009_system_setting.py` → `0010`，`0010_audit_log.py` → `0011`。

---

## 测试

### 新增测试文件

| 文件 | 测试数 | 覆盖 |
|------|--------|------|
| `tests/integration/test_admin_settings.py` | 9 (4 原有 + 4 新增 P0-1 + 1 原有) | flat string/int/bool 值保存、round-trip、与 dict 值共存 |
| `tests/integration/test_admin_assets.py` | 6 (全部新增) | list 格式、字段 schema、权限检查、kind 过滤、delete |
| `tests/integration/test_voice.py` | 6 (全部新增) | ASR 端点注册、auth 检查、识别返回 text、空文件拒绝、TTS 回归、ASR config |

### 测试运行结果

```
pytest tests/integration/test_admin_settings.py \
       tests/integration/test_admin_assets.py \
       tests/integration/test_voice.py -v

============================= 21 passed in 12.48s =============================
```

### Bootstrap 机制

所有 admin 测试面临同一个问题: 新注册用户 role=visitor，而 admin 端点需要 admin 角色。
解决方案: `_bootstrap_admin()` helper 通过直接 INSERT 到 users 表（旁路 register 端点）创建第一个 admin 用户，后续测试复用此模式。

---

## 验证清单

- [x] TypeScript 编译通过 (`vue-tsc --noEmit`)
- [x] Python 语法通过 (`py_compile` 全部文件)
- [x] P0-1 flat-value settings 集成测试（4 新增）
- [x] P0-2 admin assets 集成测试（6 新增 — list 格式/字段/权限/过滤/删除）
- [x] P0-3 POST /voice/asr 集成测试（6 新增 — 端点注册/auth/识别/错误处理/TTS 回归）
- [x] Alembic 迁移链修复 + `alembic upgrade head` 成功
- [x] 全部 21 个新旧测试通过
