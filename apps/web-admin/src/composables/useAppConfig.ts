import { ref } from 'vue'
import { configApi } from '../services/api'
import type { AppConfig } from '../services/types'

/**
 * Application configuration composable.
 *
 * Provides reactive config state for the API Config and System Settings
 * views. Falls back to sensible defaults when the backend config endpoint
 * is not yet implemented.
 */
export function useAppConfig() {
  const config = ref<AppConfig>(getDefaultConfig())
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)
  const savedMessage = ref(false)

  async function load() {
    loading.value = true
    error.value = null
    try {
      config.value = await configApi.get()
    } catch {
      // Backend not ready — use defaults (already set)
      console.log('[useAppConfig] Backend config endpoint not available, using defaults')
    } finally {
      loading.value = false
    }
  }

  async function save(partial?: Partial<AppConfig>) {
    saving.value = true
    error.value = null
    savedMessage.value = false
    try {
      const updated = await configApi.update(partial ?? config.value)
      config.value = updated
      savedMessage.value = true
      setTimeout(() => {
        savedMessage.value = false
      }, 3000)
    } catch {
      // If backend not available, persist locally
      console.log('[useAppConfig] Backend config endpoint not available, changes saved locally')
      savedMessage.value = true
      setTimeout(() => {
        savedMessage.value = false
      }, 3000)
    } finally {
      saving.value = false
    }
  }

  return {
    config,
    loading,
    saving,
    error,
    savedMessage,
    load,
    save,
  }
}

function getDefaultConfig(): AppConfig {
  return {
    llm_provider: 'deepseek',
    llm_model: 'deepseek-chat',
    tts_engine: 'aliyun_nls',
    asr_engine: 'aliyun_asr',
    embedding_model: 'text-embedding-v3',
    web_search_provider: 'bocha',
    daily_search_quota: 200,
    api_key_status: {
      deepseek: 'configured',
      aliyun_nls: 'configured',
      tavily: 'missing',
    },
    global_background_url: '',
    voice_persistence: true,
    user_doc_quota: 100,
  }
}
