# Live2D 模型加载修复 · 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 web-user 和 web-admin 的 Live2D 模型加载失败，并抽取共享加载模块消除两端重复代码。

**Architecture:** 新建 `apps/shared/live2d/live2dLoader.ts` 共享工具模块，提供 zip 下载解压、fetch 拦截器、IndexedDB 缓存、纹理加载。web-user 和 web-admin 的 lapptexturemanager.ts 改用 `textureViaFetch()` 修复 `Image.src` 绕过 fetch 拦截器的根因。web-admin 后端新增 `GET /admin/assets/{id}/file` 流式下载端点替代 Vite proxy 直连 MinIO。

**Tech Stack:** TypeScript, Vue 3, JSZip, Cubism SDK for Web 5, Python/FastAPI, boto3/MinIO, IndexedDB

---

## 文件结构

```
apps/shared/live2d/
└── live2dLoader.ts          ← 新增：共享纯工具模块 (~200 行)

apps/web-user/src/
├── composables/
│   └── useLive2DModelLoader.ts  ← 精简：删除 zip/IDB/拦截器逻辑
└── live2d/
    └── lapptexturemanager.ts    ← 修复：两处 img.src → textureViaFetch

apps/web-admin/src/
├── composables/
│   └── useLive2DPreview.ts      ← 精简 + 模型匹配四向扩展
└── live2d/
    └── lapptexturemanager.ts    ← 修复：与 web-user 相同

apps/web-user/vite.config.ts     ← 新增 alias
apps/web-admin/vite.config.ts    ← 新增 alias

backend/app/api/rest/admin_assets.py  ← 新增 GET /admin/assets/{id}/file
```

---

## 共享模块接口定义

所有 Task 共享此接口签名（先定义，各 Task 按签名实现或引用）：

```typescript
// apps/shared/live2d/live2dLoader.ts

export interface Live2DLoaderOptions {
  cache?: boolean
}

export interface ExtractedModel {
  files: Map<string, Blob>
  model3Path: string
}

export interface BlobBase {
  virtualBase: string
  model3FileName: string
}

export interface Live2DLoader {
  downloadAndExtract(url: string, cacheKey: string, options?: Live2DLoaderOptions): Promise<ExtractedModel>
  createBlobBase(files: Map<string, Blob>, model3Path: string): BlobBase
  installFetchInterceptor(virtualBase: string, files: Map<string, Blob>): void
  uninstallFetchInterceptor(): void
  textureViaFetch(url: string): Promise<HTMLImageElement>
}

export function createLive2DLoader(): Live2DLoader
```

---

### Task 1: 创建共享加载模块

**Files:**
- Create: `apps/shared/live2d/live2dLoader.ts`

- [ ] **Step 1: 创建目录和文件骨架**

```bash
mkdir -p apps/shared/live2d
```

- [ ] **Step 2: 写入完整模块代码**

```typescript
// apps/shared/live2d/live2dLoader.ts
/**
 * Live2D 共享加载器 — zip 下载解压 + fetch 拦截器 + IndexedDB 缓存 + 纹理加载。
 *
 * 非 Vue 依赖的纯工具模块，web-user 和 web-admin 的 composable 各自包装。
 */

const DB_NAME = 'eira-live2d-cache'
const DB_VERSION = 1
const STORE_NAME = 'model-files'

export interface Live2DLoaderOptions {
  /** 是否使用 IndexedDB 缓存（web-user: true, web-admin: false） */
  cache?: boolean
}

export interface ExtractedModel {
  /** 相对路径 → Blob 的映射（zip 内全量文件） */
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

// ── IndexedDB helpers ────────────────────────────────────────────────────────

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'path' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function checkCache(cacheKey: string): Promise<boolean> {
  try {
    const db = await openDB()
    return new Promise((resolve) => {
      const tx = db.transaction(STORE_NAME, 'readonly')
      const store = tx.objectStore(STORE_NAME)
      const req = store.get(`${cacheKey}/_manifest`)
      req.onsuccess = () => resolve(!!req.result)
      req.onerror = () => resolve(false)
    })
  } catch {
    return false
  }
}

async function storeFiles(
  cacheKey: string,
  files: Array<{ path: string; data: ArrayBuffer }>,
): Promise<void> {
  try {
    const db = await openDB()
    return new Promise((resolve, _reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite')
      const store = tx.objectStore(STORE_NAME)
      for (const f of files) {
        store.put({ path: `${cacheKey}/${f.path}`, data: f.data })
      }
      store.put({ path: `${cacheKey}/_manifest`, data: new ArrayBuffer(0) })
      tx.oncomplete = () => resolve()
      tx.onerror = () => resolve() // 静默失败，下次重新下载
    })
  } catch {
    // IndexedDB 不可用（隐私模式等），静默跳过
  }
}

async function loadAllFiles(cacheKey: string): Promise<Map<string, Blob>> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const store = tx.objectStore(STORE_NAME)
    const prefix = `${cacheKey}/`
    const req = store.getAll()
    req.onsuccess = () => {
      const fileMap = new Map<string, Blob>()
      for (const item of req.result) {
        if (!item.path.startsWith(prefix)) continue
        const relPath = item.path.slice(prefix.length)
        if (relPath === '_manifest') continue
        fileMap.set(relPath, new Blob([item.data]))
      }
      resolve(fileMap)
    }
    req.onerror = () => reject(req.error)
  })
}

// ── 路径工具 ─────────────────────────────────────────────────────────────────

function findModel3Path(files: Array<{ path: string }>): string | null {
  for (const f of files) {
    if (f.path.endsWith('model3.json')) return f.path
  }
  return null
}

function dirOf(path: string): string {
  const i = path.lastIndexOf('/')
  return i >= 0 ? path.slice(0, i + 1) : ''
}

// ── Fetch 拦截器 ─────────────────────────────────────────────────────────────

let _originalFetch: typeof fetch | null = null
let _interceptBase: string | null = null
let _interceptFiles: Map<string, Blob> | null = null

function installFetchInterceptor(virtualBase: string, files: Map<string, Blob>): void {
  if (_originalFetch) return

  _originalFetch = window.fetch
  _interceptBase = virtualBase
  _interceptFiles = files

  const original = _originalFetch
  window.fetch = async function (input: RequestInfo | URL, init?: RequestInit) {
    const url = typeof input === 'string' ? input :
      input instanceof URL ? input.href :
      input instanceof Request ? input.url : String(input)

    if (_interceptBase && url.startsWith(_interceptBase)) {
      const relativePath = url.slice(_interceptBase.length)
      const blob = _interceptFiles?.get(relativePath)
      if (blob) {
        return new Response(blob, {
          status: 200,
          headers: { 'Content-Type': blob.type || 'application/octet-stream' },
        })
      }
    }

    return original.call(window, input, init)
  } as typeof fetch
}

function uninstallFetchInterceptor(): void {
  if (_originalFetch) {
    window.fetch = _originalFetch
    _originalFetch = null
    _interceptBase = null
    _interceptFiles = null
  }
}

// ── 纹理加载（修复核心：Image.src 绕过 fetch 拦截器） ────────────────────────

async function textureViaFetch(url: string): Promise<HTMLImageElement> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to fetch texture: ${url} (HTTP ${response.status})`)
  }
  const blob = await response.blob()
  const blobUrl = URL.createObjectURL(blob)
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      // blob URL 可在 image load 后立即 revoke，Image 已解码
      URL.revokeObjectURL(blobUrl)
      resolve(img)
    }
    img.onerror = () => {
      URL.revokeObjectURL(blobUrl)
      reject(new Error(`Failed to load texture image: ${url}`))
    }
    img.src = blobUrl
  })
}

// ── 公开 API ─────────────────────────────────────────────────────────────────

export interface Live2DLoader {
  downloadAndExtract(url: string, cacheKey: string, options?: Live2DLoaderOptions): Promise<ExtractedModel>
  createBlobBase(files: Map<string, Blob>, model3Path: string): BlobBase
  installFetchInterceptor(virtualBase: string, files: Map<string, Blob>): void
  uninstallFetchInterceptor(): void
  textureViaFetch(url: string): Promise<HTMLImageElement>
}

export function createLive2DLoader(): Live2DLoader {
  async function downloadAndExtract(
    url: string,
    cacheKey: string,
    options?: Live2DLoaderOptions,
  ): Promise<ExtractedModel> {
    // 1. 检查 IndexedDB 缓存
    if (options?.cache) {
      const cached = await checkCache(cacheKey)
      if (cached) {
        const fileMap = await loadAllFiles(cacheKey)
        let model3Path: string | null = null
        for (const [path] of fileMap) {
          if (path.endsWith('model3.json')) { model3Path = path; break }
        }
        if (!model3Path) throw new Error('缓存中未找到 model3.json')
        return { files: fileMap, model3Path }
      }
    }

    // 2. 下载 zip
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`下载模型失败: HTTP ${response.status}`)
    }
    const zipData = await response.arrayBuffer()

    // 3. JSZip 解压
    const JSZip = (await import('jszip')).default
    const zip = await JSZip.loadAsync(zipData)

    const rawFiles: Array<{ path: string; data: ArrayBuffer }> = []
    for (const [path, entry] of Object.entries(zip.files)) {
      if (entry.dir) continue
      rawFiles.push({ path, data: await entry.async('arraybuffer') })
    }

    if (rawFiles.length === 0) {
      throw new Error('模型包为空')
    }

    const model3Path = findModel3Path(rawFiles)
    if (!model3Path) {
      throw new Error('模型包中未找到 model3.json 文件')
    }

    // 4. 转换为 Map<string, Blob>
    const fileMap = new Map<string, Blob>()
    for (const f of rawFiles) {
      fileMap.set(f.path, new Blob([f.data]))
    }

    // 5. 缓存到 IndexedDB
    if (options?.cache) {
      await storeFiles(cacheKey, rawFiles)
    }

    return { files: fileMap, model3Path }
  }

  function createBlobBase(files: Map<string, Blob>, model3Path: string): BlobBase {
    const baseDir = dirOf(model3Path)
    const model3FileName = model3Path.slice(baseDir.length)

    // Re-key fileMap：去除 baseDir 前缀，使拦截器 lookup 匹配
    // Cubism SDK 的 fetch URL 是相对于 _modelHomeDir（即 virtualBase）的
    if (baseDir) {
      const rekeyed = new Map<string, Blob>()
      for (const [path, blob] of files) {
        if (path.startsWith(baseDir)) {
          rekeyed.set(path.slice(baseDir.length), blob)
        } else {
          rekeyed.set(path, blob)
        }
      }
      files.clear()
      for (const [k, v] of rekeyed) files.set(k, v)
    }

    const virtualBase = `eira-model://${model3Path.slice(0, model3Path.lastIndexOf('/') + 1)}`
    return { virtualBase, model3FileName }
  }

  return {
    downloadAndExtract,
    createBlobBase,
    installFetchInterceptor,
    uninstallFetchInterceptor,
    textureViaFetch,
  }
}
```

- [ ] **Step 3: 提交**

```bash
git add apps/shared/live2d/live2dLoader.ts
git commit -m "feat: add shared Live2D loader module — zip download, fetch interceptor, IndexedDB cache, texture fetch

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: 更新 Vite 配置添加共享 alias

**Files:**
- Modify: `apps/web-user/vite.config.ts`
- Modify: `apps/web-admin/vite.config.ts`

- [ ] **Step 1: web-user vite.config.ts 新增 alias**

将现有 alias 块：

```typescript
alias: {
  "@framework": path.resolve(__dirname, "src/live2d-framework"),
},
```

改为：

```typescript
alias: {
  "@shared/live2d": path.resolve(__dirname, "../shared/live2d"),
  "@framework": path.resolve(__dirname, "src/live2d-framework"),
},
```

- [ ] **Step 2: web-admin vite.config.ts 新增 alias**

将现有 alias 块：

```typescript
alias: {
  "@framework": path.resolve(__dirname, "src/live2d-framework"),
},
```

改为：

```typescript
alias: {
  "@shared/live2d": path.resolve(__dirname, "../shared/live2d"),
  "@framework": path.resolve(__dirname, "src/live2d-framework"),
},
```

- [ ] **Step 3: 验证编译**

```bash
pnpm --filter @eira/web-user build 2>&1 | tail -5
pnpm --filter @eira/web-admin build 2>&1 | tail -5
```

预期：两个项目均编译成功（可能有未使用 import 警告，后续 Task 消除）。

- [ ] **Step 4: 提交**

```bash
git add apps/web-user/vite.config.ts apps/web-admin/vite.config.ts
git commit -m "chore: add @shared/live2d alias in both vite configs

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: 后端新增流式下载端点

**Files:**
- Modify: `backend/app/api/rest/admin_assets.py`

- [ ] **Step 1: 添加 import**

在文件顶部已有的 `from fastapi import ...` 行追加 `StreamingResponse`：

```python
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse  # ← 新增
```

- [ ] **Step 2: 添加流式下载端点**

在 `get_asset_download_url` 端点之后（约 line 369）、`# Cleanup test artifacts` 注释之前插入：

```python
# ── Download (streaming file) ───────────────────────────────────────────


@router.get("/{asset_id}/file")
async def download_asset_file(
    asset_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Stream the raw asset file from OSS.

    Used by the admin frontend to download Live2D model zips directly
    from the backend, avoiding Vite proxy → MinIO signed URL issues.
    """
    result = await db.execute(
        text("SELECT oss_key, kind, name FROM assets WHERE id = :id"),
        {"id": asset_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "资源不存在")

    oss_key, kind, name = row[0], row[1], row[2]
    bucket = BUCKETS.get(kind, "eira-backgrounds")

    from app.infra.oss import get_oss_client

    try:
        s3_response = get_oss_client().get_object(Bucket=bucket, Key=oss_key)
        return StreamingResponse(
            s3_response["Body"].iter_chunks(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{name}.zip"',
                "Content-Length": str(s3_response["ContentLength"]),
            },
        )
    except Exception as e:
        logger.error("oss_stream_failed", asset_id=asset_id, error=str(e))
        raise HTTPException(502, "OSS 读取失败")
```

- [ ] **Step 3: 快速验证端点注册**

```bash
cd backend
EIRA_JWT__SECRET=dev-secret EIRA_OSS__SECRET=eira-secret \
EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
EIRA_REDIS_URL=redis://localhost:6379/0 \
EIRA_OSS_ENDPOINT=http://localhost:9000 \
python -c "from app.main import app; routes = [r.path for r in app.routes if hasattr(r, 'path')]; print([r for r in routes if 'file' in r])"
```

预期输出包含：`['/admin/assets/{asset_id}/file']`

- [ ] **Step 4: 提交**

```bash
git add backend/app/api/rest/admin_assets.py
git commit -m "feat: add GET /admin/assets/{id}/file streaming download endpoint

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: 修复 web-user lapptexturemanager 纹理加载

**Files:**
- Modify: `apps/web-user/src/live2d/lapptexturemanager.ts`

- [ ] **Step 1: 添加 import**

在文件顶部（`// @ts-nocheck` 之后）添加：

```typescript
import { createLive2DLoader } from '@shared/live2d/live2dLoader'
const _textureLoader = createLive2DLoader()
```

- [ ] **Step 2: 修改缓存命中路径（约 line 54-63）**

将：

```typescript
        this._textures[i].img = new Image();
        this._textures[i].img.addEventListener(
          'load',
          (): void => callback(this._textures[i]),
          {
            passive: true
          }
        );
        this._textures[i].img.src = fileName;
        return;
```

改为：

```typescript
        const cached = this._textures[i]
        _textureLoader.textureViaFetch(fileName).then(img => {
          cached.img = img
          callback(cached)
        }).catch(() => {
          // 纹理加载失败，静默跳过（与原有 Image.src onerror 行为一致）
        })
        return;
```

- [ ] **Step 3: 修改首次加载路径（约 line 68-145）**

将：

```typescript
    // データのオンロードをトリガーにする
    const img = new Image();
    img.addEventListener(
      'load',
      (): void => {
        // テクスチャオブジェクトの作成
        const tex: WebGLTexture = this._glManager.getGl().createTexture();
        // ... (后续 WebGL 逻辑不变)
      },
      { passive: true }
    );
    img.src = fileName;
```

改为：

```typescript
    // データのオンロードをトリガーにする（fetch 拦截器経由）
    _textureLoader.textureViaFetch(fileName).then(img => {
      // テクスチャオブジェクトの作成
      const tex: WebGLTexture = this._glManager.getGl().createTexture();

      // テクスチャを選択
      this._glManager.getGl().bindTexture(this._glManager.getGl().TEXTURE_2D, tex);

      // テクスチャにピクセルを書き込む
      this._glManager.getGl().texParameteri(
        this._glManager.getGl().TEXTURE_2D,
        this._glManager.getGl().TEXTURE_MIN_FILTER,
        this._glManager.getGl().LINEAR_MIPMAP_LINEAR
      );
      this._glManager.getGl().texParameteri(
        this._glManager.getGl().TEXTURE_2D,
        this._glManager.getGl().TEXTURE_MAG_FILTER,
        this._glManager.getGl().LINEAR
      );

      // Premult処理を行わせる
      if (usePremultiply) {
        this._glManager.getGl().pixelStorei(
          this._glManager.getGl().UNPACK_PREMULTIPLY_ALPHA_WEBGL,
          1
        );
      }

      // テクスチャにピクセルを書き込む
      this._glManager.getGl().texImage2D(
        this._glManager.getGl().TEXTURE_2D,
        0,
        this._glManager.getGl().RGBA,
        this._glManager.getGl().RGBA,
        this._glManager.getGl().UNSIGNED_BYTE,
        img
      );

      // ミップマップを生成
      this._glManager.getGl().generateMipmap(this._glManager.getGl().TEXTURE_2D);

      // テクスチャをバインド
      this._glManager.getGl().bindTexture(this._glManager.getGl().TEXTURE_2D, null);

      const textureInfo: TextureInfo = new TextureInfo();
      if (textureInfo != null) {
        textureInfo.fileName = fileName;
        textureInfo.width = img.width;
        textureInfo.height = img.height;
        textureInfo.id = tex;
        textureInfo.img = img;
        textureInfo.usePremultply = usePremultiply;
        if (this._textures != null) {
          this._textures.push(textureInfo);
        }
      }

      callback(textureInfo);
    }).catch(() => {
      // 纹理加载失败，静默跳过
    });
```

- [ ] **Step 4: 验证编译**

```bash
pnpm --filter @eira/web-user build 2>&1 | tail -5
```

预期：编译成功。

- [ ] **Step 5: 提交**

```bash
git add apps/web-user/src/live2d/lapptexturemanager.ts
git commit -m "fix: route PNG textures through fetch interceptor in web-user

Image.src bypasses the fetch interceptor, causing ERR_UNKNOWN_URL_SCHEME
for eira-model:// texture URLs. Now uses textureViaFetch() which
goes through fetch → interceptor → blob URL → Image.src.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: 精简 web-user useLive2DModelLoader

**Files:**
- Modify: `apps/web-user/src/composables/useLive2DModelLoader.ts`

- [ ] **Step 1: 重写文件**

用以下内容完整替换文件：

```typescript
/**
 * Live2D 模型加载器（web-user）— 方案 D: OSS zip → JSZip 解压 → IndexedDB 缓存 → Cubism SDK
 *
 * 优先级: 用户自定义模型 > admin 全局默认
 *
 * 此 composable 是共享模块 createLive2DLoader 的薄包装，仅负责 Vue 响应式 state
 * 和 user preferences 解析。zip 下载、解压、fetch 拦截器由共享模块处理。
 */

import { ref } from 'vue'
import { userApi } from '../services/api'
import type { UserPreferences } from '../services/api'
import { createLive2DLoader } from '@shared/live2d/live2dLoader'
import type { BlobBase, ExtractedModel } from '@shared/live2d/live2dLoader'

const loader = createLive2DLoader()

export interface ModelLoadState {
  loading: boolean
  error: string | null
  /** Blob URL base — 末尾带斜杠，指向解压文件的虚拟目录 */
  baseUrl: string | null
  /** model3.json 文件名（相对于 baseUrl） */
  model3FileName: string | null
}

export function useLive2DModelLoader() {
  const state = ref<ModelLoadState>({
    loading: false,
    error: null,
    baseUrl: null,
    model3FileName: null,
  })

  /** Resolve which model to load from user preferences */
  async function resolveModelId(): Promise<string | null> {
    const prefs: UserPreferences | null = await userApi.getPreferences()
    if (!prefs?.active_model_id) {
      state.value.error = '没有可用的 Live2D 模型'
      return null
    }
    return prefs.active_model_id
  }

  /**
   * Load a model by OSS key.
   *
   * After calling this, the fetch interceptor is active and Cubism
   * can load files from `state.baseUrl + state.model3FileName`.
   */
  async function loadModel(ossKey?: string): Promise<boolean> {
    state.value = { loading: true, error: null, baseUrl: null, model3FileName: null }

    try {
      const key = ossKey || await resolveModelId()
      if (!key) {
        state.value.loading = false
        return false
      }

      // 1. Get presigned URL from backend
      const { url: presignedUrl } = await userApi.getModelDownloadUrl(key)
      const dlUrl = presignedUrl.replace('http://localhost:9000/', '/oss/')

      // 2. Download + extract (with IndexedDB cache)
      const extracted: ExtractedModel = await loader.downloadAndExtract(dlUrl, key, { cache: true })

      // 3. Create virtual base URL + install fetch interceptor
      const blobBase: BlobBase = loader.createBlobBase(extracted.files, extracted.model3Path)
      loader.installFetchInterceptor(blobBase.virtualBase, extracted.files)

      state.value = {
        loading: false,
        error: null,
        baseUrl: blobBase.virtualBase,
        model3FileName: blobBase.model3FileName,
      }

      return true
    } catch (err: any) {
      state.value = {
        loading: false,
        error: err?.message || '模型加载失败',
        baseUrl: null,
        model3FileName: null,
      }
      return false
    }
  }

  /** Clean up: remove fetch interceptor */
  function cleanup(): void {
    loader.uninstallFetchInterceptor()
    state.value = {
      loading: false,
      error: null,
      baseUrl: null,
      model3FileName: null,
    }
  }

  return {
    state,
    loadModel,
    resolveModelId,
    cleanup,
  }
}
```

- [ ] **Step 2: 验证编译**

```bash
pnpm --filter @eira/web-user build 2>&1 | tail -10
```

预期：编译成功。

- [ ] **Step 3: 补充 useLive2DController 的 cleanup 调用**

`useLive2DController.ts` 的 `onUnmounted` 缺少 `modelLoader.cleanup()` 调用，导致组件卸载后 fetch 拦截器残留。

在 `onUnmounted` 回调中（约 line 340），`LAppDelegate.releaseInstance()` 之前添加：

```typescript
// 卸载 fetch 拦截器，恢复原始 window.fetch
modelLoader.cleanup()
```

完整修改位置：

```typescript
  onUnmounted(() => {
    modelLoader.cleanup()  // ← 新增：卸载 fetch 拦截器
    if (wheelHandler && containerRef.value) {
      containerRef.value.removeEventListener('wheel', wheelHandler)
    }
    // ... 其余不变
  })
```

- [ ] **Step 4: 提交**

```bash
git add apps/web-user/src/composables/useLive2DModelLoader.ts apps/web-user/src/composables/useLive2DController.ts
git commit -m "refactor: simplify useLive2DModelLoader — delegate to shared loader module + add cleanup on unmount

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: 修复 web-admin lapptexturemanager 纹理加载

**Files:**
- Modify: `apps/web-admin/src/live2d/lapptexturemanager.ts`

- [ ] **Step 1: 添加 import**

在文件顶部（`// @ts-nocheck` 之后）添加（与 Task 4 Step 1 完全相同）：

```typescript
import { createLive2DLoader } from '@shared/live2d/live2dLoader'
const _textureLoader = createLive2DLoader()
```

- [ ] **Step 2: 修改缓存命中路径（约 line 54-63）**

与 Task 4 Step 2 完全相同的修改：

```typescript
        const cached = this._textures[i]
        _textureLoader.textureViaFetch(fileName).then(img => {
          cached.img = img
          callback(cached)
        }).catch(() => {
          // 纹理加载失败，静默跳过
        })
        return;
```

- [ ] **Step 3: 修改首次加载路径（约 line 68-145）**

与 Task 4 Step 3 完全相同的修改。将 `new Image()` + `img.src = fileName` 替换为 `_textureLoader.textureViaFetch(fileName).then(img => { ... })`，WebGL 纹理上传逻辑保持不变。

- [ ] **Step 4: 验证编译**

```bash
pnpm --filter @eira/web-admin build 2>&1 | tail -10
```

预期：编译成功。

- [ ] **Step 5: 提交**

```bash
git add apps/web-admin/src/live2d/lapptexturemanager.ts
git commit -m "fix: route PNG textures through fetch interceptor in web-admin

Same fix as web-user: Image.src bypasses the fetch interceptor,
causing ERR_UNKNOWN_URL_SCHEME for custom protocol texture URLs.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: 精简 web-admin useLive2DPreview + 模型匹配修复

**Files:**
- Modify: `apps/web-admin/src/composables/useLive2DPreview.ts`

- [ ] **Step 1: 更新 import**

在现有 import 之后添加：

```typescript
import { createLive2DLoader } from '@shared/live2d/live2dLoader'
import type { ExtractedModel, BlobBase } from '@shared/live2d/live2dLoader'

const loader = createLive2DLoader()
```

- [ ] **Step 2: 更新 ModelDescriptor 接口**

在 `ModelDescriptor` 接口中新增 `ossKey` 字段（约 line 19-30）：

```typescript
export interface ModelDescriptor {
  id: string
  label: string
  dir: string
  fileName: string
  /** 预览图（相对路径，用于 persona card） */
  previewImage?: string
  /** 显示名称（从 vtube.json / 目录名解析） */
  displayName?: string
  /** OSS key，用于 changeModel 匹配，如 "live2d/8767b36fcc6c/mao_pro_zh.zip" */
  ossKey?: string
  /** 从 vtube.json 探测到的动作文件列表 */
  discoveredMotions?: Array<{ group: string; index: number; label: string; file: string }>
}
```

- [ ] **Step 3: fetchAvailableModels 增加 ossKey 字段**

修改 `fetchAvailableModels()` 中的 map 逻辑（约 line 136-143），将：

```typescript
      availableModels.value = live2dModels.map((a: any) => ({
        id: a.name,           // Match by display name
        label: a.name,
        dir: '',              // Will be resolved at load time via JSZip
        fileName: '',
        _ossKey: a.id,        // Asset ID for download endpoint
        _ossKeyStr: String(a.id),  // String form for matching by asset ID
      }))
```

改为：

```typescript
      availableModels.value = live2dModels.map((a: any) => ({
        id: a.name,
        label: a.name,
        dir: '',
        fileName: '',
        ossKey: a.oss_key || '',       // OSS key for matching (e.g., "live2d/.../model.zip")
        _ossKey: a.id,
        _ossKeyStr: String(a.id),
      }))
```

- [ ] **Step 4: 替换 loadModel 中的内联下载/解压/拦截逻辑**

删除文件中部约 line 395-455 的内联 `_fetchFiles` / `_fetchBase` 变量和 fetch 拦截器代码，替换为共享模块调用。

修改 `loadModel` 函数（约 line 398-477）：

将整个 try 块中的 zip 下载逻辑替换：

```typescript
    // §4 fix: Two-step — download via backend streaming endpoint, extract via shared loader
    try {
      const dlUrl = `/api/admin/assets/${assetId}/file`
      const extracted: ExtractedModel = await loader.downloadAndExtract(dlUrl, String(assetId), { cache: false })

      // Create virtual base + install fetch interceptor
      const blobBase: BlobBase = loader.createBlobBase(extracted.files, extracted.model3Path)
      loader.installFetchInterceptor(blobBase.virtualBase, extracted.files)

      desc = { ...desc, dir: blobBase.virtualBase, fileName: blobBase.model3FileName }
    } catch (err: any) {
      console.error('[Live2D Admin] Download failed:', err.message)
      return false
    }
```

（删除原有的 `assetApi.getDownloadUrl` → `/oss/` proxy → JSZip 内联解压 → 内联 fetch 拦截器代码。）

- [ ] **Step 5: changeModel 匹配扩展为四向**

修改 `changeModel` 函数（约 line 480-488），将匹配逻辑：

```typescript
    const desc = availableModels.value.find((m: any) =>
      m.id === modelId ||
      String(m._ossKey) === modelId ||
      m._ossKeyStr === modelId
    )
```

改为：

```typescript
    const desc = availableModels.value.find((m: any) =>
      m.id === modelId ||
      String(m._ossKey) === modelId ||
      m._ossKeyStr === modelId ||
      m.ossKey === modelId
    )
```

- [ ] **Step 6: 清理 initLive2D 中的残留 fetch 拦截器状态**

在文件顶部删除模块级变量声明（如果存在旧的内联拦截器状态）：

```typescript
// 删除这两行（如果有）：
// let _fetchFiles: Map<string, Blob> | null = null
// let _fetchBase: string | null = null
```

这些变量约在 line 395-396。

- [ ] **Step 7: 验证编译**

```bash
pnpm --filter @eira/web-admin build 2>&1 | tail -10
```

预期：编译成功。

- [ ] **Step 8: 提交**

```bash
git add apps/web-admin/src/composables/useLive2DPreview.ts
git commit -m "refactor: simplify useLive2DPreview — delegate to shared loader + fix model matching

- Replace inline zip download/interceptor with createLive2DLoader calls
- Add ossKey field to ModelDescriptor for OSS key matching
- Extend changeModel matching to 4-way (id, asset ID, string ID, ossKey)
- Switch from Vite /oss/ proxy to backend /admin/assets/{id}/file endpoint

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: 端到端构建验证

- [ ] **Step 1: TypeScript 编译检查**

```bash
pnpm --filter @eira/web-user build 2>&1 | tail -5
pnpm --filter @eira/web-admin build 2>&1 | tail -5
```

预期：两个项目均编译成功，无 TypeScript 错误。

- [ ] **Step 2: 后端测试**

```bash
cd backend
EIRA_JWT__SECRET=test-secret EIRA_OSS__SECRET=eira-secret \
EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
EIRA_REDIS_URL=redis://localhost:6379/0 \
EIRA_OSS_ENDPOINT=http://localhost:9000 \
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

预期：所有测试通过（无回归）。

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "chore: final build verification after Live2D fixes

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: 实机验证（手动）

启动全栈服务后执行：

- [ ] **Step 1: 启动服务**

```bash
# 后端
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# web-user
pnpm --filter @eira/web-user dev

# web-admin
pnpm --filter @eira/web-admin dev
```

- [ ] **Step 2: 验证 web-user**

1. 打开 http://localhost:5173
2. 登录任意用户
3. 观察控制台：应无 `ERR_UNKNOWN_URL_SCHEME` 错误
4. 观察 Live2D 模型：纹理应正常显示（角色有皮肤/衣服/眼睛着色）
5. 拖拽/滚轮交互正常
6. 刷新页面：模型从 IndexedDB 缓存加载（观察 console 无 zip 下载日志）

- [ ] **Step 3: 验证 web-admin**

1. 打开 http://localhost:5174
2. 登录 admin@eira.dev / admin123
3. Dashboard 中间栏应显示 Live2D 模型（带纹理）
4. 点击模型选择器切换模型：应无 "Unknown model" 警告
5. 观察控制台 Network 标签：`/api/admin/assets/{id}/file` 请求返回 200

- [ ] **Step 4: 验证 Console 无残留错误**

web-user console 检查：
- ❌ 不应有：`ERR_UNKNOWN_URL_SCHEME`
- ❌ 不应有：`所有 Live2D 模型加载失败`
- ✅ 应有：`[Live2D] Successfully loaded via model loader`

web-admin console 检查：
- ❌ 不应有：`ERR_INVALID_HTTP_RESPONSE`
- ❌ 不应有：`ERR_CONTENT_LENGTH_MISMATCH`
- ❌ 不应有：`Unknown model: live2d/...`
- ❌ 不应有：`All models failed`
- ✅ 应有：`[Live2D Admin] Loaded: <模型名>`

---

## 任务依赖图

```
Task 1 (shared module) ──┬── Task 4 (user texture) ──┬── Task 8 (build verify)
                         │                           │
Task 2 (vite aliases) ───┤                           │
                         │                           │
Task 3 (backend endpoint) │                           │
                         │                           │
                         ├── Task 5 (user loader) ────┤
                         │                           │
                         ├── Task 6 (admin texture) ──┤
                         │                           │
                         └── Task 7 (admin loader) ───┘
                                                        │
                                                    Task 9 (manual verify)
```

Task 1-3 可并行执行。Task 4-7 依赖 Task 1-2 完成。Task 3 仅被 Task 7 依赖。Task 8 依赖所有前序任务。
