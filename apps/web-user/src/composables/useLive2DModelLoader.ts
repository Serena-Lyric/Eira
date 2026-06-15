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
import { useAuthStore } from '../stores/auth'
import { createLive2DLoader } from '@shared/live2d/live2dLoader'
import type { BlobBase, ExtractedModel } from '@shared/live2d/live2dLoader'

const loader = createLive2DLoader()

export interface ModelLoadState {
  loading: boolean
  error: string | null
  /** Blob URL base — 末尾带斜杠，指向解压文件的虚拟目录（仅用于 Cubism SDK 加载 / 本地视图缓存键） */
  baseUrl: string | null
  /** model3.json 文件名（相对于 baseUrl） */
  model3FileName: string | null
  /** 当前加载模型的真实 OSS key（用于持久化到 active_model_id，绝不能用 baseUrl 代替） */
  ossKey: string | null
}

export function useLive2DModelLoader() {
  const state = ref<ModelLoadState>({
    loading: false,
    error: null,
    baseUrl: null,
    model3FileName: null,
    ossKey: null,
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
    state.value = { loading: true, error: null, baseUrl: null, model3FileName: null, ossKey: null }

    try {
      const key = ossKey || await resolveModelId()
      if (!key) {
        state.value.loading = false
        return false
      }

      // 1. 后端直读模型字节（绕开 presigned URL + Vite proxy 改 Host 的签名坑）
      const dlUrl = `/api/user/model/file?oss_key=${encodeURIComponent(key)}`
      const headers: Record<string, string> = {}
      const token = useAuthStore().accessToken
      if (token) headers['Authorization'] = `Bearer ${token}`

      // 2. Download + extract (with IndexedDB cache)
      const extracted: ExtractedModel = await loader.downloadAndExtract(dlUrl, key, { cache: true, headers })

      // 3. Create virtual base URL + install fetch interceptor
      const blobBase: BlobBase = loader.createBlobBase(extracted.files, extracted.model3Path)
      loader.installFetchInterceptor(blobBase.virtualBase, extracted.files)

      state.value = {
        loading: false,
        error: null,
        baseUrl: blobBase.virtualBase,
        model3FileName: blobBase.model3FileName,
        ossKey: key,
      }

      return true
    } catch (err: any) {
      state.value = {
        loading: false,
        error: err?.message || '模型加载失败',
        baseUrl: null,
        model3FileName: null,
        ossKey: null,
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
      ossKey: null,
    }
  }

  return {
    state,
    loadModel,
    resolveModelId,
    cleanup,
  }
}
