# Live2D 模型加载修复 · 设计文档

> **日期**: 2026-06-14
> **来源**: 实机测试 — web-user 和 web-admin 均报 Live2D 模型加载失败
> **方案**: A（精确外科修复） + B（共享模块抽取）

---

## 1. 问题诊断

### 1.1 web-user: 纹理加载绕过 fetch 拦截器

**现象**：
```
GET eira-model://live2d/8767b36fcc6c/mao_pro_zh.zip/mao_pro_zh/runtime/mao_pro.4096/texture_00.png
net::ERR_UNKNOWN_URL_SCHEME
```

**根因链**：

1. `useLive2DModelLoader.ts` 劫持了 `window.fetch`，将 `eira-model://` 自定义协议请求映射到内存中的 Blob。
2. Cubism SDK 加载 model3.json / moc3 / physics / pose / expression / motion 等 JSON/二进制文件时，通过 `fetch()` 发起——被拦截器成功处理 ✅。
3. **纹理（PNG）加载走的是 `Image.src = path`**（`lapptexturemanager.ts:145`）。`Image` 构造函数**不经过 `window.fetch`**，浏览器直接尝试解析 `eira-model://` URL → `ERR_UNKNOWN_URL_SCHEME` ❌。
4. 纹理加载失败 → 模型无法完成 setup（`CompleteSetup` 永远达不到）→ `useLive2DController` 超时 → 报 "所有 Live2D 模型加载失败"。

**影响范围**：所有使用方案 D（OSS zip + JSZip + fetch 拦截器）加载的模型，纹理均无法显示。

### 1.2 web-admin: OSS 签名 URL 代理失败 + 模型匹配失败

**现象**：
```
GET oss/.../MaidCyrene...zip?X-Amz-Algorithm=...&X-Amz-Signature=...
net::ERR_INVALID_HTTP_RESPONSE

GET oss/.../haru.zip?X-Amz-...
net::ERR_CONTENT_LENGTH_MISMATCH

[Live2D Admin] Unknown model: live2d/8767b36fcc6c/mao_pro_zh.zip
```

**根因**：

**a) OSS 代理故障**：`useLive2DPreview.ts` 通过 Vite proxy 转发带 `X-Amz-*` 签名参数的 MinIO URL。签名 URL 的 `Signature` 包含了 `Host` header，但 Vite proxy 修改了 Host（`changeOrigin: true`），导致 MinIO 签名验证失败（`ERR_INVALID_HTTP_RESPONSE`）。部分请求还出现内容截断（`ERR_CONTENT_LENGTH_MISMATCH`）。

**b) 模型匹配断裂**：`fetchAvailableModels()` 构建的 `availableModels` 列表中，`id` 字段是显示名（如 `"mao_pro_zh"`），但 `persona_config.active_model_id` 存储的是 OSS key（如 `"live2d/8767b36fcc6c/mao_pro_zh.zip"`）。`changeModel` 的匹配逻辑中 `_ossKey` 是数字 asset ID（如 `128`），OSS key 字符串无法匹配到任何条目 → "Unknown model"。

**c) Dashboard API 401**：独立于 Live2D 的 auth token 过期/缺失问题，不在本次修复范围。

### 1.3 代码重复问题

两端各有 ~200 行几乎相同的逻辑：
- fetch 拦截器安装/卸载
- JSZip 下载 + 解压
- 文件映射（path → Blob）
- model3.json 路径查找

当前两份代码独立维护，修复 bug 需要双倍工作。

---

## 2. 设计概览

```
apps/shared/live2d/
└── live2dLoader.ts          ← 新增：共享纯工具模块

apps/web-user/src/
├── composables/
│   └── useLive2DModelLoader.ts  ← 精简为薄包装（~80 行）
└── live2d/
    └── lapptexturemanager.ts    ← 纹理加载改用 fetch → blob URL

apps/web-admin/src/
├── composables/
│   └── useLive2DPreview.ts      ← 精简 + 纹理修复 + 模型匹配修复
└── live2d/
    └── lapptexturemanager.ts    ← 同 web-user 的纹理修复

backend/app/api/rest/
└── admin_assets.py              ← 新增 GET /admin/assets/{id}/file
```

### 2.1 数据流（修复后）

```
┌──────────────┐     ┌─────────────────┐     ┌──────────┐
│ Backend      │     │ Shared Loader    │     │ Cubism   │
│ /assets/{id} │────▶│ downloadAndExtract│    │ SDK      │
│ /file        │     │                  │     │          │
└──────────────┘     │ zip → JSZip     │     │ fetch()──┤
                     │ → Blob map      │     │          │
                     │ → IndexedDB(opt)│     │ Image.src│
                     │                  │     │          │
                     │ installFetch     │◀────│          │
                     │ Interceptor      │     │          │
                     │                  │     │          │
                     │ textureViaFetch──│────▶│          │
                     └─────────────────┘     └──────────┘
```

关键路径：
- **JSON/二进制文件**：Cubism SDK `fetch()` → 拦截器 → Blob Response ✅（不变）
- **PNG 纹理**：Cubism SDK `Image.src` → `textureViaFetch()` → `fetch()` → 拦截器 → Blob → `URL.createObjectURL()` → 真实 blob URL ✅（修复）

---

## 3. 详细设计

### 3.1 共享模块 `live2dLoader.ts`

**位置**：`apps/shared/live2d/live2dLoader.ts`

**接口**：

```typescript
export interface Live2DLoaderOptions {
  /** 是否使用 IndexedDB 缓存（web-user: true, web-admin: false） */
  cache?: boolean
}

export interface ExtractedModel {
  /** 相对路径 → Blob 的映射 */
  files: Map<string, Blob>
  /** model3.json 在 zip 中的完整路径，如 "mao_pro_zh/runtime/mao_pro.model3.json" */
  model3Path: string
}

export interface BlobBase {
  /** fetch 拦截器识别的前缀，如 "eira-model://live2d/xxx/mao_pro_zh/runtime/" */
  virtualBase: string
  /** model3.json 文件名（不含目录），如 "mao_pro.model3.json" */
  model3FileName: string
}

export function createLive2DLoader() {
  return {
    /**
     * 下载 zip 并解压。若 options.cache=true，优先读 IndexedDB。
     * @param url      下载 URL（后端 /file 端点或 Vite proxy /oss/）
     * @param cacheKey 缓存键（通常为 OSS key）
     */
    async downloadAndExtract(
      url: string,
      cacheKey: string,
      options?: Live2DLoaderOptions,
    ): Promise<ExtractedModel>,

    /**
     * 从解压后的文件映射创建虚拟 base URL + model3 文件名。
     * 虚拟 base URL 使用 eira-model:// 协议，会被 installFetchInterceptor 识别。
     */
    createBlobBase(files: Map<string, Blob>, model3Path: string): BlobBase,

    /** 安装 fetch 拦截器 */
    installFetchInterceptor(virtualBase: string, files: Map<string, Blob>): void,

    /** 卸载 fetch 拦截器 */
    uninstallFetchInterceptor(): void,

    /**
     * 通过 fetch（经拦截器）加载纹理，返回 HTMLImageElement。
     * 解决 Image.src 不走 fetch 拦截器的问题。
     */
    textureViaFetch(url: string): Promise<HTMLImageElement>,
  }
}
```

**实现要点**：

- `downloadAndExtract`：将当前分散在两端 `useLive2DModelLoader.ts` 和 `useLive2DPreview.ts` 中的 IndexedDB 操作、fetch zip、JSZip 解压逻辑集中。
- `textureViaFetch`：`fetch(url)` → `response.blob()` → `URL.createObjectURL(blob)` → `new Image(); img.src = blobUrl` → `onload` resolve。**这是本次最关键的 bug 修复**。
- 全局单例：`installFetchInterceptor` / `uninstallFetchInterceptor` 使用模块级闭包变量，确保同时只有一个拦截器活跃（与当前行为一致）。

### 3.2 web-user 修改

#### 3.2.1 `useLive2DModelLoader.ts` — 精简

删除以下内部实现（迁移至共享模块）：
- `openDB()`, `checkCache()`, `storeFiles()`, `loadAllFiles()` — IndexedDB helpers
- `findModel3()`, `dirOf()` — 路径工具
- `installFetchInterceptor()`, `uninstallFetchInterceptor()` — fetch 劫持
- zip 下载 + JSZip 解压逻辑

保留：
- Vue 响应式 state（`ref<ModelLoadState>`）
- `resolveModelId()` — 从 user preferences 获取 OSS key（涉及后端 API 调用）
- `loadModel()` — 委托给共享模块，只负责更新 Vue state

`cleanup()` 调用 `loader.uninstallFetchInterceptor()`。

#### 3.2.2 `lapptexturemanager.ts` — 纹理修复

`createTextureFromPngFile()` 方法中有**两处**用了 `img.src = fileName`：

1. **缓存命中路径**（line 55）：复用已加载纹理条目时
2. **首次加载路径**（line 145）：创建新纹理条目时

两处都必须改为通过 fetch 拦截器加载。由于 `LAppTextureManager` 不是 Vue composable，通过模块级 import 获取 loader：

```typescript
// 文件顶部
import { createLive2DLoader } from '@shared/live2d/live2dLoader'
const loader = createLive2DLoader()
```

两处 `img.src = fileName` 替换为：

```typescript
// After（两处相同）
loader.textureViaFetch(fileName).then(img => {
  // ...原有 WebGL 纹理上传 / 缓存逻辑不变
}).catch(() => {
  // 加载失败时保持与原有行为一致：纹理缺失，模型仍可渲染（无纹理）
})
```

纹理元数据的 `fileName` 比对逻辑不变——它们比对的是 `fileName` 字符串而非 Image 对象，不受影响。

#### 3.2.3 `useLive2DController.ts` — 微小调整

- 将 `modelLoader.cleanup()` 替换为 `loader.uninstallFetchInterceptor()`（如果 cleanup 不再存在于精简后的 composable 中）
- 实际上改动极小：`loadModel()` 签名不变，`state` 结构不变

### 3.3 web-admin 修改

#### 3.3.1 后端：`GET /admin/assets/{id}/file`

在 `backend/app/api/rest/admin_assets.py` 新增端点：

```python
@router.get("/admin/assets/{id}/file")
async def download_asset_file(
    id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """流式下载 asset 原始文件（供 Live2D 模型加载使用）。
    
    绕过前端 Vite proxy → MinIO 签名 URL 的兼容性问题，
    由后端直接从 OSS 流式返回。
    """
    asset = await asset_service.get_by_id(db, id)
    if not asset:
        raise HTTPException(status_code=404)
    
    stream = await oss_service.stream_object(asset.oss_bucket, asset.oss_key)
    return StreamingResponse(
        stream,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={asset.name}.zip"},
    )
```

**安全**：`get_current_admin` 确保只有管理员可下载。

#### 3.3.2 `useLive2DPreview.ts` — 精简 + 匹配修复

**精简**：与 web-user 对称，删除内联的 zip 下载 / JSZip 解压 / fetch 拦截逻辑，委托给共享模块。

`loadModel()` 中的下载 URL 改为：

```typescript
// Before
const { url: presignedUrl } = await assetApi.getDownloadUrl(assetId)
const dlUrl = presignedUrl.replace('http://localhost:9000/', '/oss/')

// After
const dlUrl = `/api/admin/assets/${assetId}/file`
```

**模型匹配修复**：`fetchAvailableModels()` 增加 `ossKey` 字段：

```typescript
availableModels.value = live2dModels.map((a: any) => ({
  id: a.name,                      // "mao_pro_zh"
  ossKey: a.oss_key,               // "live2d/8767b36fcc6c/mao_pro_zh.zip"  ← 新增
  _ossKey: a.id,                   // 数字 asset ID
  _ossKeyStr: String(a.id),
  // ...
}))
```

`changeModel` 匹配扩展为四向：

```typescript
const desc = availableModels.value.find((m: any) =>
  m.id === modelId ||
  String(m._ossKey) === modelId ||
  m._ossKeyStr === modelId ||
  m.ossKey === modelId          // ← 新增：按 OSS key 匹配
)
```

#### 3.3.3 `lapptexturemanager.ts` — 纹理修复

与 web-user 完全相同的修改：`img.src = fileName` → `loader.textureViaFetch(fileName)`。

### 3.4 Vite 配置

两个 `vite.config.ts` 均新增 alias：

```typescript
alias: {
  '@shared/live2d': path.resolve(__dirname, '../shared/live2d'),
  // ...existing aliases
}
```

---

## 4. 文件变更清单

| 操作 | 文件 | 行数估计 |
|:--:|------|:--:|
| ➕ | `apps/shared/live2d/live2dLoader.ts` | ~200 |
| ✏️ | `apps/web-user/src/composables/useLive2DModelLoader.ts` | -180 / +80 |
| ✏️ | `apps/web-user/src/live2d/lapptexturemanager.ts` | +15 |
| ✏️ | `apps/web-user/vite.config.ts` | +1 |
| ✏️ | `apps/web-admin/src/composables/useLive2DPreview.ts` | -80 / +60 |
| ✏️ | `apps/web-admin/src/live2d/lapptexturemanager.ts` | +15 |
| ✏️ | `apps/web-admin/vite.config.ts` | +1 |
| ✏️ | `backend/app/api/rest/admin_assets.py` | +20 |

**净效果**：删除 ~260 行重复代码，新增 ~200 行共享代码 + ~110 行分散修改，总代码量减少。

---

## 5. 错误处理

| 场景 | 处理方式 |
|------|---------|
| zip 下载失败（HTTP 非 200） | 抛出 `Error("下载模型失败: HTTP {status}")`，composable 捕获后设置 `loadError` |
| zip 中无 model3.json | 抛出 `Error("模型包中未找到 model3.json 文件")` |
| IndexedDB 不可用（隐私模式等） | `checkCache` 返回 false，走网络下载；`storeFiles` 静默失败 |
| 纹理 fetch 失败 | `textureViaFetch` reject Promise → `img.onerror` → Cubism SDK 按原逻辑报 `Failed to load file` |
| 后端 /file 端点 MinIO 不可达 | 返回 502，前端显示加载失败 |
| 非 admin 访问 /file 端点 | 401 Unauthorized（网关层拦截） |

---

## 6. 测试策略

| 层级 | 测试 |
|------|------|
| **后端** | `test_admin_assets.py`：验证 `/admin/assets/{id}/file` 返回 200 + 正确 Content-Type；验证 401（非 admin）；验证 404（无效 ID） |
| **前端（实机）** | web-user 聊天页加载模型 → 纹理显示 + 动作正常；web-admin Dashboard 加载模型 → 纹理显示 + 热切换正常 |
| **回归** | `backend python -m pytest tests/ -v --tb=short` 全部通过 |

---

## 7. 不在本次范围

| 问题 | 原因 |
|------|------|
| web-admin Dashboard API 401 | 独立的 auth token 管理问题，非 Live2D 加载问题 |
| web-user 气泡回答展示异常 | 用户标注为"后续再修复" |
| `active_model_id` 旧格式兼容 | 已在 `user.py` 中增加 `"/" not in str(current_model)` 检测，本次不重复处理 |
| admin 模型预览图显示 | `resolveModelMeta()` 的 vtube.json 读取依赖 fetch 拦截器，可能仍有问题——若加载后预览图仍不显示，后续再修 |
| Service Worker 方案 | 方案 B 已覆盖共享抽取，不引入 SW 的额外复杂度 |

---

## 8. 迁移路径

1. 创建 `apps/shared/live2d/live2dLoader.ts`（新模块，无破坏性）
2. 修改两个 `vite.config.ts` 添加 alias
3. 修改 web-user 端 3 个文件
4. 修改 web-admin 端 3 个文件 + 后端 1 个文件
5. 重启后端 + 两端前端 dev server
6. 实机验证：打开 user 聊天页 → 模型应正常显示纹理和动作；打开 admin Dashboard → 模型应正常加载 + 可热切换
7. 运行 `python -m pytest tests/ -v --tb=short` 确认无回归
