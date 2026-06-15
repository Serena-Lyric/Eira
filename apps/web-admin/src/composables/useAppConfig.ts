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
    } catch (e: any) {
      // §7 fix: show real error, not fake success
      error.value = e?.response?.data?.detail || e?.message || '保存失败，请检查网络连接'
      savedMessage.value = false
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
    // §5 fix: default values aligned with backend provider support
    llm_provider: 'deepseek',
    llm_model: 'deepseek-chat',
    tts_provider: 'xunfei',
    asr_provider: 'xunfei',
    embedding_provider: 'openai',
    embedding_model: 'text-embedding-3-small',
    search_provider: 'tavily',
    daily_search_quota: 100,
    // §6 fix: api_key_status is now provided by backend, empty by default
    api_key_status: {},
    global_background_url: '',
    voice_persistence: true,
    user_doc_quota: 100,
  }
}
