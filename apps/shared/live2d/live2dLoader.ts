// apps/shared/live2d/live2dLoader.ts
/**
 * Live2D 共享加载器 — zip 下载解压 + fetch 拦截器 + IndexedDB 缓存 + 纹理加载。
 *
 * 非 Vue 依赖的纯工具模块，web-user 和 web-admin 的 composable 各自包装。
 */

import JSZip from 'jszip'

const DB_NAME = 'eira-live2d-cache'
const DB_VERSION = 1
const STORE_NAME = 'model-files'

export interface Live2DLoaderOptions {
  /** 是否使用 IndexedDB 缓存（web-user: true, web-admin: false） */
  cache?: boolean
  /** 自定义 HTTP 请求头（如 Authorization） */
  headers?: Record<string, string>
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
//
// 全局只 patch 一次 window.fetch；用 virtualBase → files 的注册表支持同时存在多个模型。
// 修复点：旧实现 `if (_originalFetch) return` 会导致 admin 连续/并发加载多个模型时，
// 后装的拦截器被跳过，第二个模型的文件请求落到第一个模型的 base/files 上 → 加载错文件。
// 现在每个模型独立注册一份 base→files，互不覆盖。

let _originalFetch: typeof fetch | null = null
const _interceptors = new Map<string, Map<string, Blob>>()

function _ensurePatched(): void {
  if (_originalFetch) return
  _originalFetch = window.fetch
  const original = _originalFetch
  window.fetch = async function (input: RequestInfo | URL, init?: RequestInit) {
    const url = typeof input === 'string' ? input :
      input instanceof URL ? input.href :
      input instanceof Request ? input.url : String(input)

    // 遍历所有已注册模型的 virtualBase，命中即返回对应 Blob
    for (const [base, files] of _interceptors) {
      if (url.startsWith(base)) {
        const blob = files.get(url.slice(base.length))
        if (blob) {
          return new Response(blob, {
            status: 200,
            headers: { 'Content-Type': blob.type || 'application/octet-stream' },
          })
        }
      }
    }

    return original.call(window, input, init)
  } as typeof fetch
}

function installFetchInterceptor(virtualBase: string, files: Map<string, Blob>): void {
  _ensurePatched()
  _interceptors.set(virtualBase, files)
}

function uninstallFetchInterceptor(): void {
  // 清空所有已注册模型并恢复原始 fetch
  _interceptors.clear()
  if (_originalFetch) {
    window.fetch = _originalFetch
    _originalFetch = null
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
    const fetchOpts: RequestInit = {}
    if (options?.headers) {
      fetchOpts.headers = options.headers
    }
    const response = await fetch(url, fetchOpts)
    if (!response.ok) {
      throw new Error(`下载模型失败: HTTP ${response.status}`)
    }
    const zipData = await response.arrayBuffer()

    // 3. JSZip 解压
    const zip = await JSZip.loadAsync(zipData)

    const rawFiles: Array<{ path: string; data: ArrayBuffer }> = []
    for (const [path, entry] of Object.entries(zip.files)) {
      const file = entry as JSZip.JSZipObject
      if (file.dir) continue
      rawFiles.push({ path, data: await file.async('arraybuffer') })
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
