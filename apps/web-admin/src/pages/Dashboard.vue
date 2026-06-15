<script setup lang="tsx">
import { ref, computed, onMounted, watch, h, type Ref } from 'vue'
import {
  NDataTable,
  NButton,
  NSpace,
  NTag,
  NUpload,
  NModal,
  NForm,
  NFormItem,
  NInput,
  NSpin,
  NCollapse,
  NCollapseItem,
  NSelect,
  NSwitch,
  useMessage,
} from 'naive-ui'
import { useDashboard } from '../composables/useDashboard'
import { useAppConfig } from '../composables/useAppConfig'
import { useLive2DPreview } from '../composables/useLive2DPreview'
import { personaConfigApi, personaApi, knowledgeApi, assetApi } from '../services/api'
import { useAuthStore } from '../stores/auth'
import type { TimeRange } from '../composables/useDashboard'
import type { MotionOption, Persona, PersonaCreate, KnowledgeDocument, ChunkInfo, DocumentDetail, Asset } from '../services/types'
import type { UploadFileInfo } from 'naive-ui'

const message = useMessage()
const auth = useAuthStore()
const currentUser = computed(() => auth.user)

// ── Dashboard composable ──────────────────────────────────────────
const {
  currentRange,
  metrics,
  topQuestions,
  satisfactionTrend,
  satisfactionTrendMonth,
  wordCloud,
  sentiment,
  feedback,
  loading: dashLoading,
  setRange,
  replyToFeedback,
} = useDashboard()

// ── App config composable ─────────────────────────────────────────
const {
  config,
  error: configError,
  saving: configSaving,
  save: saveConfig,
} = useAppConfig()

// §7 fix: Independent save state per view
const apiSaved = ref(false)
const apiSaving = ref(false)
const apiError = ref<string | null>(null)
const settingsSaved = ref(false)
const settingsSaving = ref(false)
const settingsError = ref<string | null>(null)

async function saveApiConfig() {
  apiSaving.value = true
  apiError.value = null
  apiSaved.value = false
  try {
    await saveConfig()
    apiSaved.value = true
    setTimeout(() => { apiSaved.value = false }, 3000)
  } catch (e: any) {
    apiError.value = e?.response?.data?.detail || e?.message || '保存失败'
  } finally {
    apiSaving.value = false
  }
}

async function saveSettingsConfig() {
  settingsSaving.value = true
  settingsError.value = null
  settingsSaved.value = false
  try {
    await saveConfig()
    settingsSaved.value = true
    setTimeout(() => { settingsSaved.value = false }, 3000)
  } catch (e: any) {
    settingsError.value = e?.response?.data?.detail || e?.message || '保存失败'
  } finally {
    settingsSaving.value = false
  }
}

// ── Live2D Preview composable ────────────────────────────────────
const {
  containerRef: l2dContainerRef,
  isLoaded: l2dLoaded,
  activeModelId: l2dActiveModelId,
  loadError: l2dError,
  availableModels: l2dModels,
  availableMotions: l2dAvailableMotions,
  refreshAvailableMotions: l2dRefreshMotions,
  changeModel: l2dChangeModel,
  applyIdleMotionToModel: l2dApplyIdleMotion,
} = useLive2DPreview()

// ── UI state ──────────────────────────────────────────────────────
const isHovered = ref<string | null>(null)
const isPressed = ref<string | null>(null)
const activeTab = ref('day')
const isLeftPanelOpen = ref(true)
const isRightPanelOpen = ref(true)
const currentView = ref('dashboard')

// 右侧卡片展开状态
const expandedCard = ref<string | null>(null)

// 日期范围
const showDatePicker = ref(false)
const dateRangeText = ref('自定义日期范围')
const tempStartDate = ref<number | null>(null)
const tempEndDate = ref<number | null>(null)

// Live2D 模型选择（与 useLive2DPreview 同步）
const showModelSelector = ref(false)
const selectedModel = ref(l2dModels.value[0]?.id || 'mao_pro_zh')

// ── Persona card 元数据：从当前选中模型目录解析图片与名称 ──────────
const currentModelMeta = computed(() =>
  l2dModels.value.find((m) => m.id === selectedModel.value) ?? null,
)

// 待机动作选择
const showIdleMotionSelector = ref(false)
const selectedIdleMotion = ref<MotionOption | null>(null)
const showOfflineMotionSelector = ref(false)
const selectedOfflineMotion = ref<MotionOption | null>(null)
const showSpeechRateSelector = ref(false)

// 默认语速
const adminSpeechRate = ref(1.0)

// 模型切换：同步 Live2D 和 UI
watch(l2dActiveModelId, (id) => {
  if (id) selectedModel.value = id
})

async function handleModelChange(modelId: string) {
  selectedModel.value = modelId
  showModelSelector.value = false
  // 切换模型时清除旧的待机动作选择
  selectedIdleMotion.value = null
  selectedOfflineMotion.value = null
  await l2dChangeModel(modelId)
  // 模型切换后刷新动作列表并通知后端
  setTimeout(() => {
    l2dRefreshMotions()
    savePersonaConfig()
  }, 1000)
}

function selectIdleMotion(motion: MotionOption) {
  selectedIdleMotion.value = motion
  showIdleMotionSelector.value = false
  l2dApplyIdleMotion(motion.group, motion.index)
  savePersonaConfig()
}

function selectOfflineMotion(motion: MotionOption) {
  selectedOfflineMotion.value = motion
  showOfflineMotionSelector.value = false
  savePersonaConfig()
}

function handleSpeechRateChange(rate: number) {
  adminSpeechRate.value = rate
  showSpeechRateSelector.value = false
  savePersonaConfig()
}

let personaConfigTimer: ReturnType<typeof setTimeout> | null = null
async function savePersonaConfig() {
  if (personaConfigTimer) clearTimeout(personaConfigTimer)
  personaConfigTimer = setTimeout(async () => {
    try {
      // active_model_id 统一存 OSS key（user 端只认 OSS key）。
      // selectedModel 是显示名（UI 选中态），这里转换成对应模型的 ossKey 再持久化。
      const sel: any = l2dModels.value.find((m: any) => m.id === selectedModel.value)
      const modelOssKey: string | undefined = sel?.ossKey || undefined
      await personaConfigApi.update({
        active_model_id: modelOssKey,
        idle_motion_group: selectedIdleMotion.value?.group ?? null,
        idle_motion_index: selectedIdleMotion.value?.index ?? null,
        offline_idle_motion_group: selectedOfflineMotion.value?.group ?? null,
        offline_idle_motion_index: selectedOfflineMotion.value?.index ?? null,
        default_speech_rate: adminSpeechRate.value,
      })
    } catch (err: any) {
      console.error('[savePersonaConfig] Failed:', err?.response?.data?.detail || err?.message || err)
    }
  }, 500)
}

// 加载 persona 配置
async function loadPersonaConfig() {
  try {
    const cfg = await personaConfigApi.get()
    if (cfg.active_model_id) {
      // active_model_id 现在统一是 OSS key。UI 选中态需要显示名，这里按 ossKey 映射回显示名；
      // 映射不到（如旧显示名格式 / 模型列表未就绪）时，watch(l2dActiveModelId) 会在加载成功后兜底修正。
      const m: any = l2dModels.value.find((x: any) => x.ossKey === cfg.active_model_id || x.id === cfg.active_model_id)
      selectedModel.value = m?.id ?? cfg.active_model_id
      // 真正切换 Live2D 模型（changeModel 四向匹配，兼容 ossKey 和旧显示名）
      setTimeout(() => l2dChangeModel(cfg.active_model_id!), 1500)
    }
    if (cfg.idle_motion_group != null) {
      selectedIdleMotion.value = {
        group: cfg.idle_motion_group,
        index: cfg.idle_motion_index ?? 0,
        label: `${cfg.idle_motion_group}_${cfg.idle_motion_index ?? 0}`,
      }
      // 延迟应用待机动作（等待模型加载完成后生效）
      setTimeout(() => {
        l2dApplyIdleMotion(cfg.idle_motion_group!, cfg.idle_motion_index ?? 0)
      }, 2000)
    }
    if (cfg.offline_idle_motion_group != null) {
      selectedOfflineMotion.value = {
        group: cfg.offline_idle_motion_group,
        index: cfg.offline_idle_motion_index ?? 0,
        label: `${cfg.offline_idle_motion_group}_${cfg.offline_idle_motion_index ?? 0}`,
      }
    }
    if (typeof cfg.default_speech_rate === 'number') {
      adminSpeechRate.value = cfg.default_speech_rate
    }
    if (cfg.default_background_url) {
      bgUrl.value = cfg.default_background_url
    }
  } catch {
    // 后端未就绪，使用默认值
  }
}

// 服务建议回复框状态
const replyingTo = ref<number | null>(null)
const replyText = ref('')
const replySuccess = ref<number | null>(null)

// ── 智能计算小卡片可展示的建议条数 (1-3) ─────────────────────────
// 根据前几条内容的累计字符数决定：内容短可多展示，内容长则少展示
// 不做缩放，通过调整条目间距适配卡片高度
const visibleFeedbackCount = computed(() => {
  const items = feedback.value
  if (items.length === 0) return 0
  let chars = 0
  const max = Math.min(items.length, 3)
  for (let i = 0; i < max; i++) {
    chars += items[i].content.length
  }
  // 策略：前3条累计 <= 80 字可展示3条，<= 120 字展示2条，否则仅1条
  if (chars <= 80) return max
  if (chars <= 120) return Math.min(items.length, 2)
  return 1
})

const visibleFeedback = computed(() =>
  feedback.value.slice(0, visibleFeedbackCount.value),
)

// ── Feedback reply debounce ──────────────────────────────────────────
const replySending = ref(false)

const bgUrl = ref('')  // 无背景时显示蓝色占位（CSS fallback）
const fileInput = ref<HTMLInputElement | null>(null)
const live2dUploadRef = ref<{ clearFiles: () => void } | null>(null)
const bgUploadRef = ref<{ clearFiles: () => void } | null>(null)

// ── Derived: formatted metrics for template ───────────────────────
const safeMetrics = computed(() => metrics.value || { total_visitors: 0, total_conversations: 0, avg_response_latency_ms: 0, satisfaction_pct: 0, visitors_change_pct: 0, conversations_change_pct: 0, latency_change_ms: 0, satisfaction_change_pct: 0 })
const fmtVisitors = computed(() => (safeMetrics.value.total_visitors ?? 0).toLocaleString())
const fmtConversations = computed(() => (safeMetrics.value.total_conversations ?? 0).toLocaleString())
const fmtLatency = computed(() => `${((safeMetrics.value.avg_response_latency_ms ?? 0) / 1000).toFixed(1)}s`)
const fmtSatisfaction = computed(() => `${(safeMetrics.value.satisfaction_pct ?? 0).toFixed(1)}%`)
const fmtVisitorsChange = computed(() => {
  const v = safeMetrics.value.visitors_change_pct ?? 0
  return `环比${v >= 0 ? '＋' : ''}${v.toFixed(1)}%`
})
const fmtConversationsChange = computed(() => {
  const v = safeMetrics.value.conversations_change_pct ?? 0
  return `环比${v >= 0 ? '＋' : ''}${v.toFixed(1)}%`
})
const fmtLatencyChange = computed(() => {
  const v = safeMetrics.value.latency_change_ms ?? 0
  return `${v >= 0 ? '＋' : ''}${(v / 1000).toFixed(1)}s`
})
const fmtSatisfactionChange = computed(() => {
  const v = safeMetrics.value.satisfaction_change_pct ?? 0
  return `${v >= 0 ? '＋' : ''}${v.toFixed(1)}%`
})

// ── Derived: chart data ───────────────────────────────────────────
const sentimentDonutDash = computed(() => {
  const p = sentiment.value.positive_pct
  return `${p * 0.9},100`
})

function _trendComputed(pts: Ref<{date: string; score: number}[]>, x0: number) {
  const x1 = 95, y0 = 8, y1 = 40, smin = 0, smax = 100
  const polyline = computed(() => {
    const items = pts.value
    if (!items.length) return ''
    return items.map((p, i) => {
      const x = x0 + (i / Math.max(items.length - 1, 1)) * (x1 - x0)
      const y = y1 - ((p.score - smin) / (smax - smin)) * (y1 - y0)
      return `${i === 0 ? '' : ' '}${x.toFixed(1)},${y.toFixed(1)}`
    }).join('')
  })
  const path = computed(() => polyline.value ? `M${x0},40 L${polyline.value} L95,40 Z` : '')
  const dates = computed(() => pts.value.map(p => p.date))
  const circles = computed(() => {
    const items = pts.value
    return items.map((p, i) => {
      const x = x0 + (i / Math.max(items.length - 1, 1)) * (x1 - x0)
      const y = y1 - ((p.score - smin) / (smax - smin)) * (y1 - y0)
      return { cx: x.toFixed(1), cy: y.toFixed(1), date: p.date, score: p.score, index: i }
    })
  })
  return { polyline, path, dates, circles }
}

// Week trend (card) — x0=15 aligned with card grid
const trendPoints = computed(() => satisfactionTrend.value)
const { polyline: trendPolyline, path: trendPath, dates: trendDates, circles: trendCircles } = _trendComputed(trendPoints, 15)

// Month trend (expanded) — x0=10 aligned with expanded grid
const trendPointsMonth = computed(() => satisfactionTrendMonth.value)
const { polyline: trendPolylineMonth, path: trendPathMonth, dates: trendDatesMonth, circles: trendCirclesMonth } = _trendComputed(trendPointsMonth, 10)

// Hover tooltip state for expanded detail
const trendTooltip = ref<{ cx: string; cy: string; date: string; score: number } | null>(null)

// ── Actions ───────────────────────────────────────────────────────
function setTab(tab: string) {
  activeTab.value = tab
  dateRangeText.value = '自定义日期范围'
  setRange(tab as TimeRange)
}

function toggleBothPanels() {
  if (isLeftPanelOpen.value || isRightPanelOpen.value) { isLeftPanelOpen.value = false; isRightPanelOpen.value = false }
  else { isLeftPanelOpen.value = true; isRightPanelOpen.value = true }
}
function toggleCard(cardId: string) { expandedCard.value = expandedCard.value === cardId ? null : cardId }
async function handleBgUpload(e: Event) {
  const t = e.target as HTMLInputElement
  const file = t.files?.[0]
  if (!file) return

  try {
    const formData = new FormData()
    formData.append('file', file)
    const result = await assetApi.uploadBackground(formData)
    message.success('背景图片上传成功')
    // 设为默认背景
    if (result.id) {
      await assetApi.setDefault(result.id)
      await loadPersonaConfig()  // 刷新配置以更新 bgUrl
    }
    t.value = ''
    await loadAssets()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '上传失败')
  }
}
const datePickerYear = computed(() => new Date().getFullYear())
const datePickerMonth = computed(() => new Date().getMonth() + 1)
function selectMockDate(d: number) {
  if (tempStartDate.value === null) tempStartDate.value = d
  else if (tempEndDate.value === null) { if (d >= tempStartDate.value!) tempEndDate.value = d; else { tempEndDate.value = tempStartDate.value; tempStartDate.value = d } }
  else { tempStartDate.value = d; tempEndDate.value = null }
}
function confirmDateRange() {
  const y = datePickerYear.value, m = String(datePickerMonth.value).padStart(2, '0')
  if (tempStartDate.value && tempEndDate.value) dateRangeText.value = `${y}.${m}.${String(tempStartDate.value).padStart(2,'0')} - ${m}.${String(tempEndDate.value).padStart(2,'0')}`
  else if (tempStartDate.value) dateRangeText.value = `${y}.${m}.${String(tempStartDate.value).padStart(2,'0')}`
  showDatePicker.value = false; activeTab.value = 'custom'
}
async function handleReply(idx: number) {
  if (replySending.value) return
  const fb = feedback.value[idx]
  if (fb && replyText.value.trim()) {
    replySending.value = true
    try {
      await replyToFeedback(fb.id, replyText.value)
      replySuccess.value = fb.id
      setTimeout(() => { replySuccess.value = null }, 2500)
    } catch {
      message.error('回复发送失败')
    } finally {
      replySending.value = false
    }
  }
  replyingTo.value = null
  replyText.value = ''
}

// ══════════════════════════════════════════════════════════════════════
// Personas View — 角色卡管理
// ══════════════════════════════════════════════════════════════════════

const personaCols = [
  { title: '名称', key: 'name' },
  { title: '描述', key: 'description' },
  {
    title: '默认',
    key: 'is_default',
    render(row: Persona) {
      return h(NTag, { type: row.is_default ? 'success' : 'default' }, { default: () => row.is_default ? '是' : '否' })
    },
  },
  {
    title: '操作',
    key: 'actions',
    render(row: Persona) {
      return (
        <NSpace>
          <NButton size="small" onClick={() => openPersonaEdit(row)}>Edit</NButton>
          <NButton size="small" type="info" ghost onClick={() => handlePersonaSetDefault(row)}>Set Default</NButton>
          <NButton size="small" type="error" ghost onClick={() => handlePersonaDelete(row)}>Delete</NButton>
        </NSpace>
      )
    },
  },
]

const personaData = ref<Persona[]>([])
const personaLoading = ref(false)
const personaError = ref<string | null>(null)

// Persona modal
const showPersonaModal = ref(false)
const personaSaving = ref(false)
const editingPersona = ref<Persona | null>(null)
const personaForm = ref({
  name: '',
  description: '',
  personality: '',
  scenario: '',
  first_mes: '',
  mes_example: '',
  system_prompt: '',
  live2d_asset_id: '',
  voice_id: '',
  tags: [] as string[],
  scope: 'public',
  is_default: false,
})
const tagsInput = ref('')
const personaFormRules = {
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }],
  system_prompt: [{ required: true, message: '请输入系统提示词（至少10个字符）', trigger: 'blur', min: 10 }],
}

// JSON import
const jsonFileInput = ref<HTMLInputElement | null>(null)

async function loadPersonas() {
  personaLoading.value = true
  personaError.value = null
  try {
    personaData.value = await personaApi.list()
  } catch (e: any) {
    personaError.value = e?.response?.data?.detail || e?.message || 'Failed to load personas'
    message.error('Failed to load personas')
  } finally {
    personaLoading.value = false
  }
}

function openPersonaCreate() {
  editingPersona.value = null
  personaForm.value = {
    name: '',
    description: '',
    personality: '',
    scenario: '',
    first_mes: '',
    mes_example: '',
    system_prompt: '',
    live2d_asset_id: '',
    voice_id: '',
    tags: [],
    scope: 'public',
    is_default: false,
  }
  tagsInput.value = ''
  showPersonaModal.value = true
}

function openPersonaEdit(row: Persona) {
  editingPersona.value = row
  personaForm.value = {
    name: row.name,
    description: row.description || '',
    personality: row.personality || '',
    scenario: row.scenario || '',
    first_mes: row.first_mes || '',
    mes_example: row.mes_example || '',
    system_prompt: row.system_prompt || '',
    live2d_asset_id: row.live2d_asset_id != null ? String(row.live2d_asset_id) : '',
    voice_id: row.voice_id || '',
    tags: row.tags || [],
    scope: row.scope || 'public',
    is_default: row.is_default || false,
  }
  tagsInput.value = (row.tags || []).join(', ')
  showPersonaModal.value = true
}

async function handlePersonaSubmit() {
  personaSaving.value = true
  try {
    // Build tags from comma-separated input
    const tags = tagsInput.value
      .split(',')
      .map(s => s.trim())
      .filter(Boolean)
    // Parse live2d_asset_id: NInput binds as string, convert to number|null
    const rawId = personaForm.value.live2d_asset_id
    const live2d_asset_id = rawId !== null && rawId !== undefined && String(rawId).trim() !== ''
      ? Number(rawId)
      : null
    const payload = { ...personaForm.value, tags, live2d_asset_id }

    if (editingPersona.value) {
      await personaApi.update(editingPersona.value.id, payload)
      message.success('角色卡已更新')
    } else {
      await personaApi.create(payload as PersonaCreate)
      message.success('角色卡已创建')
    }
    showPersonaModal.value = false
    await loadPersonas()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '操作失败')
  } finally {
    personaSaving.value = false
  }
}

function triggerJsonImport() {
  jsonFileInput.value?.click()
}

async function handleJsonImport(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    const text = await file.text()
    const jsonData = JSON.parse(text)
    await personaApi.import(jsonData)
    message.success(`"${file.name}" 导入成功`)
    await loadPersonas()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || 'JSON 导入失败')
  } finally {
    input.value = ''
  }
}

async function handlePersonaSetDefault(row: Persona) {
  try {
    await personaApi.setDefault(row.id)
    message.success(`"${row.name}" 已设为默认`)
    await loadPersonas()
  } catch { message.error('设置默认失败') }
}

async function handlePersonaDelete(row: Persona) {
  try {
    await personaApi.delete(row.id)
    message.success(`"${row.name}" 已永久删除`)
    await loadPersonas()
  } catch { message.error('删除失败') }
}

// ══════════════════════════════════════════════════════════════════════
// Knowledge View — 知识库与 RAG
// ══════════════════════════════════════════════════════════════════════

const knowledgeCols = [
  { title: '文档名称', key: 'filename' },
  { title: '大小', key: 'size_display' },
  {
    title: '状态',
    key: 'status',
    render(row: KnowledgeDocument) {
      const statusMap: Record<string, { type: 'success' | 'warning' | 'info' | 'error'; label: string }> = {
        ready: { type: 'success', label: 'Ready' },
        pending: { type: 'warning', label: 'Pending' },
        processing: { type: 'info', label: `Processing (${row.progress ?? 0}%)` },
        failed: { type: 'error', label: row.error ? `Failed: ${row.error.slice(0, 30)}` : 'Failed' },
      }
      const s = statusMap[row.status] || { type: 'info' as const, label: row.status }
      return h(NTag, { type: s.type }, { default: () => s.label })
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 280,
    render(row: KnowledgeDocument) {
      return (
        <NSpace style="flex-wrap:nowrap">
          <NButton size="small" type="primary" ghost disabled={row.status === 'processing'} onClick={() => handleVectorize(row)}>Vectorize</NButton>
          <NButton size="small" onClick={() => handleKnowledgePreview(row)}>Preview RAG</NButton>
          <NButton size="small" type="error" ghost onClick={() => handleKnowledgeDelete(row)}>Delete</NButton>
        </NSpace>
      )
    },
  },
]

const knowledgeData = ref<KnowledgeDocument[]>([])
const knowledgeLoading = ref(false)
const knowledgeError = ref<string | null>(null)
const knowledgeUploading = ref(false)

// Knowledge Preview modal
const showKnowledgePreview = ref(false)
const previewDoc = ref<KnowledgeDocument | null>(null)
const previewChunks = ref<ChunkInfo[]>([])
const previewLoading = ref(false)

async function loadKnowledge() {
  knowledgeLoading.value = true
  knowledgeError.value = null
  try {
    const result = await knowledgeApi.list()
    // Compute human-readable size for display
    knowledgeData.value = (result || []).map((doc: KnowledgeDocument) => ({
      ...doc,
      size_display: doc.file_size
        ? doc.file_size > 1024 * 1024
          ? `${(doc.file_size / 1024 / 1024).toFixed(1)} MB`
          : `${(doc.file_size / 1024).toFixed(1)} KB`
        : '-',
    }))
  } catch (e: any) {
    knowledgeError.value = e?.response?.data?.detail || e?.message || 'Failed to load documents'
    message.error('Failed to load knowledge base')
  } finally {
    knowledgeLoading.value = false
  }
}

async function handleKnowledgeUpload(options: { file: UploadFileInfo; onFinish: () => void; onError: () => void }) {
  knowledgeUploading.value = true
  try {
    const formData = new FormData()
    if (options.file.file) formData.append('file', options.file.file)
    await knowledgeApi.upload(formData)
    message.success('File uploaded successfully')
    options.onFinish()
    await loadKnowledge()
  } catch {
    message.error('Upload failed')
    options.onError()
  } finally {
    knowledgeUploading.value = false
  }
}

async function handleVectorize(row: KnowledgeDocument) {
  try {
    await knowledgeApi.reprocess(row.id)
    message.success(`"${row.filename}" 已触发重新向量化`)
    await loadKnowledge()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '向量化失败')
  }
}

async function handleKnowledgePreview(row: KnowledgeDocument) {
  previewDoc.value = row
  showKnowledgePreview.value = true
  previewLoading.value = true
  previewChunks.value = []
  try {
    const detail: DocumentDetail = await knowledgeApi.getDetail(row.id)
    previewChunks.value = detail.chunks || []
  } catch {
    message.error('获取文档详情失败')
  } finally {
    previewLoading.value = false
  }
}

async function handleKnowledgeDelete(row: KnowledgeDocument) {
  try {
    await knowledgeApi.delete(row.id)
    message.success(`"${row.filename}" 已删除`)
    await loadKnowledge()
  } catch { message.error('删除失败') }
}

function truncateText(text: string, maxLen = 150): string {
  if (!text) return ''
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}

// ══════════════════════════════════════════════════════════════════════
// Live2D Assets View — 模型资产管理
// ══════════════════════════════════════════════════════════════════════

const assetTypeLabel: Record<string, string> = {
  live2d_model: 'Live2D Model',
  background: 'Background',
}

const assetCols = [
  { title: '资产名称', key: 'name' },
  {
    title: '类型', key: 'kind',
    render(row: Asset) {
      return h(NTag, { type: row.kind === 'live2d_model' ? 'info' : 'warning' }, { default: () => assetTypeLabel[row.kind] || row.kind })
    },
  },
  {
    title: '默认', key: 'is_default',
    render(row: Asset) {
      return h(NTag, { type: row.is_default ? 'success' : 'default' }, { default: () => row.is_default ? '是' : '否' })
    },
  },
  {
    title: '操作', key: 'actions',
    render(row: Asset) {
      return (
        <NSpace>
          <NButton size="small" type="primary" ghost onClick={() => handleAssetSetDefault(row)}>Set Default</NButton>
          <NButton size="small" type="error" ghost onClick={() => handleAssetDelete(row)}>Delete</NButton>
        </NSpace>
      )
    },
  },
]

const assetData = ref<Asset[]>([])
const assetLoading = ref(false)
const assetError = ref<string | null>(null)
const assetUploading = ref(false)

async function loadAssets() {
  assetLoading.value = true
  assetError.value = null
  try {
    assetData.value = await assetApi.list()
  } catch (e: any) {
    assetError.value = e?.response?.data?.detail || e?.message || 'Failed to load assets'
    message.error('Failed to load assets')
  } finally {
    assetLoading.value = false
  }
}

async function handleAssetUpload(options: { file: UploadFileInfo; onFinish: () => void; onError: () => void }, type: 'live2d' | 'background') {
  assetUploading.value = true
  try {
    const formData = new FormData()
    if (options.file.file) formData.append('file', options.file.file)
    if (type === 'live2d') await assetApi.uploadLive2D(formData)
    else await assetApi.uploadBackground(formData)
    message.success('上传成功')
    options.onFinish()
    // 清空上传列表
    if (type === 'live2d') live2dUploadRef.value?.clearFiles()
    else bgUploadRef.value?.clearFiles()
    await loadAssets()
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.message || '上传失败'
    const status = err?.response?.status ? ` [HTTP ${err.response.status}]` : ''
    message.error(`上传失败: ${detail}${status}`)
    options.onError()
  } finally {
    assetUploading.value = false
  }
}

async function handleAssetSetDefault(row: Asset) {
  try {
    await assetApi.setDefault(row.id)
    message.success(`"${row.name}" 已设为默认`)
    await loadAssets()
  } catch { message.error('设置默认失败') }
}

async function handleAssetDelete(row: Asset) {
  try {
    await assetApi.delete(row.id)
    message.success(`"${row.name}" 已删除`)
    await loadAssets()
  } catch { message.error('删除失败') }
}

// ══════════════════════════════════════════════════════════════════════
// View load-on-enter
// ══════════════════════════════════════════════════════════════════════

watch(currentView, (view) => {
  if (view === 'personas') loadPersonas()
  else if (view === 'knowledge') loadKnowledge()
  else if (view === 'live2d') loadAssets()
})

// ── Load data on mount ────────────────────────────────────────────
onMounted(() => {
  setRange('day')
  loadPersonaConfig()
})
</script>

<template>
  <div class="admin-root">
    <div class="layout-wrapper">
      <img class="fullscreen-bg" :src="bgUrl" alt="BG" />

      <!-- Navbar -->
      <header class="navbar">
        <div class="logo-zone">
          <svg class="logo-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
          <div class="logo-text"><span class="logo-cn">人物形象管理</span><span class="logo-en">Avatar Management System</span></div>
        </div>
        <nav class="nav-menu">
          <button class="nav-item" :class="{active:currentView==='dashboard'}" @click="currentView='dashboard'">数据概览</button>
          <button class="nav-item" :class="{active:currentView==='api'}" @click="currentView='api'">API 配置</button>
          <button class="nav-item" :class="{active:currentView==='personas'}" @click="currentView='personas'">角色卡</button>
          <button class="nav-item" :class="{active:currentView==='knowledge'}" @click="currentView='knowledge'">知识库</button>
          <button class="nav-item" :class="{active:currentView==='live2d'}" @click="currentView='live2d'">Live2D</button>
          <button class="nav-item" :class="{active:currentView==='settings'}" @click="currentView='settings'">系统设置</button>
        </nav>
        <div class="user-glass">
          <button class="bell-btn"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#6B7280" stroke-width="2"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg></button>
          <div class="text-avatar">A</div>
          <span class="username">{{ currentUser?.display_name || '管理员' }}</span>
        </div>
      </header>

      <!-- ==================== DASHBOARD VIEW ==================== -->
      <main v-show="currentView==='dashboard'" class="main-container">
        <!-- Left peek handle -->
        <div class="peek left-peek" :class="{show:!isLeftPanelOpen}" @click="isLeftPanelOpen=true"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></div>

        <!-- Left Panel -->
        <aside class="left-panel" :class="{hidden:!isLeftPanelOpen}">
          <div class="panel-hd"><h3>形象库与配置</h3><button class="icon-btn" @click="isLeftPanelOpen=false"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg></button></div>
          <div class="persona-grid">
            <div class="persona-card active">
              <img
                v-if="currentModelMeta?.previewImage"
                :src="currentModelMeta.previewImage"
                :alt="currentModelMeta?.displayName || selectedModel"
              />
              <div v-else class="no-icon">No Icon</div>
              <div class="card-name">{{ currentModelMeta?.displayName || selectedModel }}</div>
            </div>
            <div class="persona-card">
              <img
                v-if="currentModelMeta?.previewImage"
                :src="currentModelMeta.previewImage"
                :alt="currentModelMeta?.displayName || selectedModel"
              />
              <div v-else class="no-icon">No Icon</div>
              <div class="card-name">{{ (currentModelMeta?.displayName || selectedModel)  }}</div>
            </div>
          </div>
          <div class="setting-tabs"><div class="stab active">外观</div><div class="stab" title="待后续版本实现">服装</div><div class="stab" title="待后续版本实现">声音</div></div>
          <div class="setting-list">
            <div class="sitem"><span>Live2D 模型</span><span class="sval model-link" @click="showModelSelector=!showModelSelector">{{ selectedModel }}</span></div>
            <!-- Model selector dropdown -->
            <div v-if="showModelSelector" class="model-drop">
              <div v-for="m in l2dModels" :key="m.id" class="model-opt" :class="{sel: m.id === selectedModel}" @click="handleModelChange(m.id)">{{ m.label }}</div>
            </div>
            <div class="sitem"><span>待机动作</span><span class="sval model-link" @click="showIdleMotionSelector=!showIdleMotionSelector">{{ selectedIdleMotion?.label || '未选择' }}</span></div>
            <!-- Idle motion selector dropdown -->
            <div v-if="showIdleMotionSelector" class="model-drop">
              <div class="model-opt" :class="{sel: !selectedIdleMotion}" @click="selectedIdleMotion = null; showIdleMotionSelector = false; l2dApplyIdleMotion(null, null); savePersonaConfig()">(默认)</div>
              <div v-for="m in l2dAvailableMotions" :key="'idle-'+m.group+m.index" class="model-opt" :class="{sel: selectedIdleMotion?.group === m.group && selectedIdleMotion?.index === m.index}" @click="selectIdleMotion(m)">{{ m.label }}</div>
            </div>
            <div class="sitem"><span>待机动作（失去网络时）</span><span class="sval model-link" @click="showOfflineMotionSelector=!showOfflineMotionSelector">{{ selectedOfflineMotion?.label || '未选择' }}</span></div>
            <!-- Offline idle motion selector dropdown -->
            <div v-if="showOfflineMotionSelector" class="model-drop">
              <div class="model-opt" :class="{sel: !selectedOfflineMotion}" @click="selectedOfflineMotion = null; showOfflineMotionSelector = false; savePersonaConfig()">(默认)</div>
              <div v-for="m in l2dAvailableMotions" :key="'off-'+m.group+m.index" class="model-opt" :class="{sel: selectedOfflineMotion?.group === m.group && selectedOfflineMotion?.index === m.index}" @click="selectOfflineMotion(m)">{{ m.label }}</div>
            </div>
            <div class="sitem"><span>默认语速</span><span class="sval model-link" @click="showSpeechRateSelector=!showSpeechRateSelector">{{ adminSpeechRate }}x</span></div>
            <!-- Speech rate selector dropdown -->
            <div v-if="showSpeechRateSelector" class="model-drop">
              <div v-for="rate in [0.5, 0.75, 1.0, 1.25, 1.5]" :key="'sr-'+rate"
                class="model-opt" :class="{sel: adminSpeechRate === rate}"
                @click="handleSpeechRateChange(rate)">{{ rate }}x</div>
            </div>
          </div>
        </aside>

        <!-- Center Panel (Fixed width to prevent shifting) -->
        <section class="center-panel">
          <div class="preview-box" ref="l2dContainerRef">
            <!-- Frosted placeholder: shown while loading or on error -->
            <div v-if="!l2dLoaded || l2dError" class="sdk-holder">
              <svg viewBox="0 0 24 24" width="56" height="56" fill="none" stroke="rgba(255,255,255,0.7)" stroke-width="1.2"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
              <span v-if="l2dError" class="ph-text" style="color:#EF4444">{{ l2dError }}</span>
              <span v-else class="ph-text">Live2D 渲染区</span>
            </div>
          </div>
          <div class="center-actions">
            <button class="act-pill active" @click="toggleBothPanels">形象预览</button>
            <button class="act-pill" disabled title="待后续版本实现">动作设置</button>
            <button class="act-pill" disabled title="待后续版本实现">语音测试</button>
            <button class="act-pill" disabled title="待后续版本实现">更多设置</button>
          </div>
        </section>

        <!-- Right peek handle -->
        <div class="peek right-peek" :class="{show:!isRightPanelOpen}" @click="isRightPanelOpen=true"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg></div>

        <!-- Right Panel -->
        <aside class="right-panel" :class="{hidden:!isRightPanelOpen}">
          <div class="rp-inner">
            <div class="rp-hd"><button class="icon-btn" @click="isRightPanelOpen=false"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></button><h2>运营数据概览</h2></div>

            <!-- 日期筛选行 -->
            <div class="date-row">
              <div class="db-tabs">
                <button class="tbtn" :class="{active:activeTab==='day'}" @click="setTab('day')">今日</button>
                <button class="tbtn" :class="{active:activeTab==='week'}" @click="setTab('week')">本周</button>
                <button class="tbtn" :class="{active:activeTab==='month'}" @click="setTab('month')">本月</button>
              </div>
              <div class="date-picker-wrap">
                <button class="dp-btn" :class="{active:activeTab==='custom'}" @click="showDatePicker=!showDatePicker"><span>{{ dateRangeText }}</span> <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg></button>
                <div v-if="showDatePicker" class="cal-drop">
                  <div class="cal-month">{{ datePickerYear }}年 {{ datePickerMonth }}月</div>
                  <div class="cal-grid"><div class="cal-dow" v-for="d in ['日','一','二','三','四','五','六']" :key="d">{{d}}</div><div class="cal-empty" v-for="i in 5" :key="'e'+i"></div><div v-for="d in 31" :key="d" class="cal-day" :class="{sel:tempStartDate===d||tempEndDate===d,mid:tempStartDate&&tempEndDate&&d>tempStartDate&&d<tempEndDate}" @click="selectMockDate(d)">{{d}}</div></div>
                  <div class="cal-btns"><button @click="showDatePicker=false">取消</button><button class="ok" @click="confirmDateRange">确认</button></div>
                </div>
              </div>
            </div>

            <div class="metric-grid">
              <div class="mcard"><div class="mt">服务人次</div><div class="mv">{{ fmtVisitors }}</div><div class="mtr" :class="safeMetrics.visitors_change_pct >= 0 ? 'up' : 'dn'"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg> {{ fmtVisitorsChange }}</div></div>
              <div class="mcard"><div class="mt">交互对话数</div><div class="mv">{{ fmtConversations }}</div><div class="mtr" :class="safeMetrics.conversations_change_pct >= 0 ? 'up' : 'dn'"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg> {{ fmtConversationsChange }}</div></div>
              <div class="mcard"><div class="mt">平均响应延迟</div><div class="mv">{{ fmtLatency }}</div><div class="mtr" :class="safeMetrics.latency_change_ms <= 0 ? 'up' : 'dn'"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/></svg> {{ fmtLatencyChange }}</div></div>
              <div class="mcard"><div class="mt">用户满意度</div><div class="mv">{{ fmtSatisfaction }}</div><div class="mtr" :class="safeMetrics.satisfaction_change_pct >= 0 ? 'up' : 'dn'"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg> {{ fmtSatisfactionChange }}</div></div>
            </div>

            <!-- 可点击展开卡片行 -->
            <div class="charts2col">
              <!-- TOP5 卡片 -->
              <div class="cchart" @click="toggleCard('top5')"><h3>高频问答 TOP5</h3><div class="top5-list"><div v-for="q in topQuestions" :key="q.rank" class="t5row"><span class="t5idx" :class="'r' + (q.rank <= 3 ? q.rank : 4)">{{ q.rank }}</span><span class="t5txt">{{ q.text }}</span><span class="t5cnt">{{ q.count }}次</span></div></div></div>
              <!-- 满意度折线 -->
              <div class="cchart" @click="toggleCard('trend')"><h3>用户满意度趋势 (%)</h3>
                <svg viewBox="0 0 100 60" preserveAspectRatio="none" style="width:100%;flex:1;overflow:visible">
                  <g stroke="rgba(0,0,0,0.05)" stroke-width=".5">
                    <line x1="15" y1="8" x2="95" y2="8"/><line x1="15" y1="16" x2="95" y2="16"/>
                    <line x1="15" y1="24" x2="95" y2="24"/><line x1="15" y1="32" x2="95" y2="32"/>
                    <line x1="15" y1="40" x2="95" y2="40"/>
                  </g>
                  <g fill="#9CA3AF" font-size="4" text-anchor="end">
                    <text x="13" y="9">100</text><text x="13" y="17">75</text>
                    <text x="13" y="25">50</text><text x="13" y="33">25</text>
                    <text x="13" y="41">0</text>
                  </g>
                  <g fill="#9CA3AF" font-size="4" text-anchor="middle">
                    <text v-for="(d, i) in trendDates" :key="d" :x="15 + (i / Math.max(trendDates.length - 1, 1)) * 80" y="46">{{ d.slice(5) }}</text>
                  </g>
                  <defs><linearGradient id="g2" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="rgba(59,130,246,0.25)"/><stop offset="100%" stop-color="rgba(59,130,246,0)"/></linearGradient></defs>
                  <path :d="trendPath" fill="url(#g2)"/>
                  <polyline :points="trendPolyline" fill="none" stroke="#3B82F6" stroke-width="1.5" stroke-linecap="round"/>
                  <circle v-for="(c, i) in trendCircles" :key="'c'+i" :cx="c.cx" :cy="c.cy" r="1.5" fill="#FFF" stroke="#3B82F6" stroke-width=".8"/>
                </svg>
              </div>
            </div>

            <div class="charts3col">
              <div class="cchart" @click="toggleCard('cloud')"><h3>游客关注词云</h3><div class="cloud"><span v-for="(w, i) in wordCloud.slice(0, 9)" :key="i" class="cw" :class="'c' + (i + 1)" :style="{ color: w.color }">{{ w.text }}</span></div></div>
              <div class="cchart" @click="toggleCard('sentiment')"><h3>情感分析</h3><div class="donut"><svg viewBox="0 0 36 36" width="100%"><path d="M18 2a16 16 0 110 32 16 16 0 010-32" fill="none" stroke="#E5E7EB" stroke-width="4"/><path d="M18 2a16 16 0 110 32" fill="none" stroke="#10B981" stroke-width="4" :stroke-dasharray="sentiment.positive_pct + ',100'"/><text x="18" y="20.5" font-size="8" text-anchor="middle" fill="#1F2937" font-weight="700">{{ sentiment.positive_pct }}%</text></svg></div></div>
              <div class="cchart" @click="toggleCard('feedback')"><h3>最新服务建议</h3><div class="fb-list" :style="{ gap: visibleFeedbackCount === 1 ? '16px' : visibleFeedbackCount === 2 ? '10px' : '6px' }"><div v-for="(f, i) in visibleFeedback" :key="f.id" class="fbi" :style="{ paddingBottom: i < visibleFeedbackCount - 1 ? (visibleFeedbackCount === 1 ? '0' : visibleFeedbackCount === 2 ? '8px' : '6px') : '0' }"><span class="fbt">{{ f.timestamp }}<span v-if="f.replied" style="color:#10B981;margin-left:6px;font-size:10px">已回复</span></span><span class="fbtxt">{{ f.content }}</span></div><div v-if="feedback.length === 0" style="text-align:center;color:#9CA3AF;font-size:13px;padding:12px 0">暂无建议</div></div></div>
            </div>
          </div>
        </aside>

        <!-- 展开卡片覆盖层 -->
        <transition name="fade">
          <div v-if="expandedCard" class="expand-overlay" @click.self="expandedCard=null">
            <div class="expand-card">
              <button class="x-btn" @click="expandedCard=null"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
              <!-- TOP5 expanded -->
              <template v-if="expandedCard==='top5'"><h2 style="margin:0 0 24px;color:#1F2937">高频问答 TOP5 · 详细</h2><div style="display:flex;flex-direction:column;gap:14px;font-size:16px"><div v-for="q in topQuestions" :key="q.rank" style="display:flex;align-items:center;gap:12px"><span :style="{background:q.rank===1?'#FEF2F2':q.rank===2?'#FFFBEB':q.rank===3?'#ECFDF5':'#F3F4F6',color:q.rank===1?'#EF4444':q.rank===2?'#F59E0B':q.rank===3?'#10B981':'#6B7280',width:'28px',height:'28px',display:'flex',alignItems:'center',justifyContent:'center',borderRadius:'8px',fontWeight:700}">{{ q.rank }}</span><span style="flex:1;color:#374151;font-weight:600">{{ q.text }}</span><span style="color:#9CA3AF">{{ q.count }}次</span><div style="width:100px;height:8px;background:#F3F4F6;border-radius:4px;overflow:hidden"><div :style="{width:q.percentage + '%',background:q.rank===1?'#EF4444':q.rank===2?'#F59E0B':q.rank===3?'#10B981':'#3B82F6',height:'100%'}"/></div></div></div></template>
              <!-- Trend expanded -->
              <template v-if="expandedCard==='trend'"><h2 style="margin:0 0 24px;color:#1F2937">用户满意度趋势 · 详细</h2>
                <div style="position:relative;flex:1;min-height:400px;width:100%">
                  <svg viewBox="0 0 100 60" preserveAspectRatio="none" style="width:100%;height:100%">
                    <g stroke="rgba(0,0,0,0.06)" stroke-width=".4">
                      <line x1="10" y1="40" x2="95" y2="40"/><line x1="10" y1="32" x2="95" y2="32"/>
                      <line x1="10" y1="24" x2="95" y2="24"/><line x1="10" y1="16" x2="95" y2="16"/>
                      <line x1="10" y1="8" x2="95" y2="8"/>
                    </g>
                    <g fill="#9CA3AF" font-size="4" text-anchor="end">
                      <text x="9" y="41">0</text><text x="9" y="33">25</text>
                      <text x="9" y="25">50</text><text x="9" y="17">75</text>
                      <text x="9" y="9">100</text>
                    </g>
                    <g fill="#9CA3AF" font-size="2.5" text-anchor="middle">
                      <template v-for="(d, i) in trendDatesMonth" :key="'ed'+i">
                        <text v-if="i % 5 === 0 || i === trendDatesMonth.length - 1" :x="10 + (i / Math.max(trendDatesMonth.length - 1, 1)) * 85" y="44">{{ d.slice(5) }}</text>
                      </template>
                    </g>
                    <defs><linearGradient id="g3" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="rgba(59,130,246,0.3)"/><stop offset="100%" stop-color="rgba(59,130,246,0)"/></linearGradient></defs>
                    <path :d="trendPathMonth" fill="url(#g3)"/>
                    <polyline :points="trendPolylineMonth" fill="none" stroke="#3B82F6" stroke-width=".45" stroke-linecap="round"/>
                    <circle v-for="c in trendCirclesMonth" :key="'ec'+c.index" :cx="c.cx" :cy="c.cy" r=".3" fill="#FFF" stroke="#3B82F6" stroke-width=".2" style="cursor:pointer" @mouseenter="trendTooltip = c" @mouseleave="trendTooltip = null"/>
                  </svg>
                  <div v-if="trendTooltip" class="trend-tooltip" :style="{ left: (parseFloat(trendTooltip.cx) / 100 * 100) + '%', top: (parseFloat(trendTooltip.cy) / 60 * 100) + '%' }">{{ trendTooltip.date }}: {{ trendTooltip.score }}%</div>
                  </div>
              </template>
              <!-- Cloud expanded -->
              <template v-if="expandedCard==='cloud'"><h2 style="margin:0 0 24px;color:#1F2937">游客关注词云 · 详细</h2><div class="cloud cloud-lg"><span v-for="(w, i) in wordCloud" :key="i" class="cw" :class="'c' + (Math.min(i, 6) + 1)" :style="{ fontSize: (12 + w.weight * 30) + 'px', color: w.color }">{{ w.text }}</span></div></template>
              <!-- Sentiment expanded -->
              <template v-if="expandedCard==='sentiment'"><h2 style="margin:0 0 24px;color:#1F2937">情感分析 · 详细</h2><div style="display:flex;align-items:center;gap:40px;flex:1"><div style="width:180px;height:180px"><svg viewBox="0 0 36 36" width="100%"><path d="M18 2a16 16 0 110 32 16 16 0 010-32" fill="none" stroke="#E5E7EB" stroke-width="4"/><path d="M18 2a16 16 0 110 32" fill="none" stroke="#10B981" stroke-width="4" :stroke-dasharray="sentiment.positive_pct + ',100'"/><path d="M18 2a16 16 0 010 32" fill="none" stroke="#F59E0B" stroke-width="4" :stroke-dasharray="sentiment.neutral_pct + ',100'" :stroke-dashoffset="-(sentiment.positive_pct)"/><text x="18" y="20.5" font-size="7" text-anchor="middle" fill="#1F2937" font-weight="700">{{ sentiment.positive_pct }}%</text></svg></div><div style="display:flex;flex-direction:column;gap:12px;font-size:14px"><div style="display:flex;align-items:center;gap:8px"><span style="width:12px;height:12px;border-radius:3px;background:#10B981"/><span style="color:#374151">正面 ({{ sentiment.positive_pct }}%)</span></div><div style="display:flex;align-items:center;gap:8px"><span style="width:12px;height:12px;border-radius:3px;background:#F59E0B"/><span style="color:#374151">中性 ({{ sentiment.neutral_pct }}%)</span></div><div style="display:flex;align-items:center;gap:8px"><span style="width:12px;height:12px;border-radius:3px;background:#EF4444"/><span style="color:#374151">负面 ({{ sentiment.negative_pct }}%)</span></div></div></div></template>
              <!-- Feedback expanded -->
              <template v-if="expandedCard==='feedback'">
                <h2 style="margin:0 0 24px;color:#1F2937">最新服务建议 · 详细回复</h2>
                <div v-if="feedback.length === 0" style="text-align:center;color:#9CA3AF;padding:40px 0;font-size:15px">暂无服务建议</div>
                <div v-else class="fb-expand-list">
                  <div v-for="(f, i) in feedback" :key="f.id" class="fb-expand-item">
                    <div class="fb-content-row">
                      <span class="fb-t">{{ f.timestamp }}</span>
                      <span class="fb-txt">{{ f.content }}</span>
                      <button v-if="!f.replied" class="fb-reply-trigger" @click="replyingTo = replyingTo === i ? null : i">{{ replyingTo === i ? '取消' : '回复' }}</button>
                      <span v-else style="font-size:12px;color:#10B981;font-weight:600;white-space:nowrap">✓ 已回复</span>
                    </div>
                    <!-- 已有回复展示 -->
                    <div v-if="f.replied && f.reply_text" class="fb-admin-reply">
                      <span style="font-size:11px;color:#9CA3AF;font-weight:600;margin-bottom:4px;display:block">管理员回复</span>
                      <span style="font-size:14px;color:#374151;line-height:1.5">{{ f.reply_text }}</span>
                    </div>
                    <!-- 回复输入框 -->
                    <transition name="slide-down">
                      <div v-if="replyingTo === i && !f.replied" class="fb-reply-box">
                        <textarea v-model="replyText" class="fb-textarea" placeholder="输入回复内容..."></textarea>
                        <button class="fb-submit" :disabled="!replyText.trim() || replySending" @click="handleReply(i)">{{ replySending ? '发送中...' : '发送回复' }}</button>
                      </div>
                    </transition>
                    <!-- 回复成功提示 -->
                    <div v-if="replySuccess === f.id" style="margin-top:8px;font-size:13px;color:#10B981;font-weight:600;display:flex;align-items:center;gap:4px">
                      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg> 回复已发送
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </transition>
      </main>

      <!-- ==================== API CONFIG VIEW ==================== -->
      <main v-show="currentView==='api'" class="settings-container">
        <div class="settings-glass-card">
          <div class="sc-hd"><h2>API 与引擎配置</h2><p>管理后端驱动所需的 AI 服务及接口参数</p></div>
          <div class="sc-body">
            <div class="srow"><div class="sinfo"><h3>LLM 引擎提供商</h3><p>切换数字人后端驱动的语言模型</p></div><select class="ssel" v-model="config.llm_provider"><option value="deepseek">DeepSeek</option><option value="tongyi">通义千问</option><option value="openai">OpenAI (兼容)</option></select></div>
            <div class="srow"><div class="sinfo"><h3>LLM 默认模型</h3><p>当前 provider 的默认模型变体</p></div><select class="ssel" v-model="config.llm_model"><option value="deepseek-chat">deepseek-chat</option><option value="deepseek-reasoner">deepseek-reasoner</option></select></div>
            <div class="srow"><div class="sinfo"><h3>TTS 语音引擎</h3><p>数字人流式语音合成服务</p></div><select class="ssel" v-model="config.tts_provider"><option value="xunfei">讯飞流式</option><option value="mock">Mock (开发用)</option></select></div>
            <div class="srow"><div class="sinfo"><h3>ASR 语音识别</h3><p>用户语音输入识别引擎</p></div><select class="ssel" v-model="config.asr_provider"><option value="xunfei">讯飞流式 ASR</option><option value="mock">Mock (开发用)</option></select></div>
            <div class="srow"><div class="sinfo"><h3>Embedding 模型</h3><p>知识库向量化模型</p></div><select class="ssel" v-model="config.embedding_model"><option value="text-embedding-3-small">text-embedding-3-small</option><option value="text-embedding-3-large">text-embedding-3-large</option></select></div>
            <div class="srow"><div class="sinfo"><h3>Web Search 服务</h3><p>互联网检索兜底提供商</p></div><select class="ssel" v-model="config.search_provider"><option value="tavily">Tavily</option><option value="mock">Mock (开发用)</option></select></div>
            <div class="srow"><div class="sinfo"><h3>每日搜索配额</h3><p>Web Search 每日调用上限</p></div><input type="number" v-model.number="config.daily_search_quota" class="sinput" /></div>
            <div class="srow"><div class="sinfo"><h3>API Key 状态</h3><p>各 Provider 密钥不显示，仅展示配置与否</p></div><div style="display:flex;flex-direction:column;gap:6px;font-size:13px"><span v-for="(status, name) in config.api_key_status" :key="name" :style="{ color: status === 'configured' ? '#10B981' : '#F59E0B' }">{{ status === 'configured' ? '✅' : '⚠️' }} {{ name }}{{ status === 'missing' ? ' 未配置' : '' }}</span></div></div>
          </div>
          <div class="sc-actions">
            <span v-if="apiError" style="color:#EF4444;margin-right:16px;font-size:14px">{{ apiError }}</span>
            <span v-else-if="apiSaved" style="color:#10B981;margin-right:16px;font-size:14px">✓ 已保存</span>
            <button class="pbtn" @click="currentView='dashboard'">返回</button>
            <button class="pbtn" style="margin-left:12px;background:#3B82F6" @click="saveApiConfig()" :disabled="apiSaving">{{ apiSaving ? '保存中...' : '保存配置' }}</button>
          </div>
        </div>
      </main>

      <!-- ==================== PERSONAS VIEW ==================== -->
      <main v-show="currentView==='personas'" class="settings-container">
        <div class="settings-glass-card" style="max-width:900px">
          <div class="sc-hd">
            <h2>角色卡管理</h2>
            <p>创建和管理角色卡，设置默认角色</p>
          </div>
          <div class="sc-body">
            <div style="margin-bottom:16px;display:flex;gap:12px">
              <NButton type="primary" @click="openPersonaCreate">创建新角色卡</NButton>
              <NButton @click="triggerJsonImport">导入 JSON</NButton>
              <input ref="jsonFileInput" type="file" accept=".json" style="display:none" @change="handleJsonImport" />
            </div>
            <NDataTable :columns="personaCols" :data="personaData" :bordered="false" :loading="personaLoading" />
            <div v-if="personaError" class="error-banner">{{ personaError }}</div>
          </div>
        </div>
      </main>

      <!-- ==================== KNOWLEDGE VIEW ==================== -->
      <main v-show="currentView==='knowledge'" class="settings-container">
        <div class="settings-glass-card" style="max-width:900px">
          <div class="sc-hd">
            <h2>知识库与 RAG</h2>
            <p>上传文档构建知识库，支持 PDF / DOCX / TXT / MD 格式</p>
          </div>
          <div class="sc-body">
            <div class="knowledge-upload-zone">
              <NUpload multiple directory-dnd :max="5" :custom-request="handleKnowledgeUpload">
                <div class="upload-dragger">
                  <p>点击或拖拽文件到此处上传</p>
                  <p style="font-size:13px;color:#888">支持 PDF、DOCX、TXT、MD 格式</p>
                </div>
              </NUpload>
            </div>
            <NDataTable :columns="knowledgeCols" :data="knowledgeData" :bordered="false" :loading="knowledgeLoading || knowledgeUploading" style="margin-top:20px" />
            <div v-if="knowledgeError" class="error-banner">{{ knowledgeError }}</div>
          </div>
        </div>
      </main>

      <!-- ==================== LIVE2D ASSETS VIEW ==================== -->
      <main v-show="currentView==='live2d'" class="settings-container">
        <div class="settings-glass-card" style="max-width:900px">
          <div class="sc-hd">
            <h2>Live2D 模型资产</h2>
            <p>管理 Live2D 模型包和背景图片资产</p>
          </div>
          <div class="sc-body">
            <div style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap">
              <NUpload ref="live2dUploadRef" :max="1" accept=".zip,.7z,.rar" :custom-request="(o: any) => handleAssetUpload(o, 'live2d')">
                <NButton type="primary" ghost>上传 Live2D 模型</NButton>
              </NUpload>
              <NUpload ref="bgUploadRef" :max="1" accept=".jpg,.jpeg,.png,.webp" :custom-request="(o: any) => handleAssetUpload(o, 'background')">
                <NButton type="primary" ghost>上传背景图片</NButton>
              </NUpload>
            </div>
            <NDataTable :columns="assetCols" :data="assetData" :bordered="false" :loading="assetLoading || assetUploading" />
            <div v-if="assetError" class="error-banner">{{ assetError }}</div>
          </div>
        </div>
      </main>

      <!-- ==================== SYSTEM SETTINGS VIEW ==================== -->
      <main v-show="currentView==='settings'" class="settings-container">
        <div class="settings-glass-card">
          <div class="sc-hd"><h2>全局系统设置</h2><p>管理整个系统的通用外观与行为配置</p></div>
          <div class="sc-body">
            <div class="srow"><div class="sinfo"><h3>全局背景主题</h3><p>上传图片以更改管理端与用户端的主题背景</p></div><div style="display:flex;align-items:center;gap:12px"><img v-if="bgUrl" :src="bgUrl" style="width:80px;height:45px;object-fit:cover;border-radius:6px;border:1px solid rgba(255,255,255,0.15)" /><button class="upbtn" @click="fileInput?.click()">更换图片</button></div><input type="file" ref="fileInput" @change="handleBgUpload" accept="image/*" style="display:none"/></div>
            <div class="srow"><div class="sinfo"><h3>语音持久化</h3><p>是否保存用户语音录音文件</p></div><div class="tgl" :class="{active: config.voice_persistence}" @click="config.voice_persistence = !config.voice_persistence"><div class="tgl-knob"/></div></div>
            <div class="srow"><div class="sinfo"><h3>用户文档配额</h3><p>每用户最多上传文档数</p></div><input type="number" v-model.number="config.user_doc_quota" class="sinput" /></div>
          </div>
          <div class="sc-actions">
            <span v-if="settingsError" style="color:#EF4444;margin-right:16px;font-size:14px">{{ settingsError }}</span>
            <span v-else-if="settingsSaved" style="color:#10B981;margin-right:16px;font-size:14px">✓ 已保存</span>
            <button class="pbtn" @click="currentView='dashboard'">返回</button>
            <button class="pbtn" style="margin-left:12px;background:#3B82F6" @click="saveSettingsConfig()" :disabled="settingsSaving">{{ settingsSaving ? '保存中...' : '保存并返回' }}</button>
          </div>
        </div>
      </main>

      <!-- ==================== PERSONA MODAL ==================== -->
      <NModal v-model:show="showPersonaModal" :mask-closable="!personaSaving">
        <div class="persona-modal">
          <div class="modal-header">
            <h3>{{ editingPersona ? '编辑角色卡' : '创建新角色卡' }}</h3>
            <button class="modal-close" @click="showPersonaModal = false" :disabled="personaSaving">✕</button>
          </div>
          <NForm ref="formRef" :model="personaForm" :rules="personaFormRules" label-placement="top">
            <!-- 基础信息（默认展开） -->
            <NCollapse :default-expanded-names="['basic']">
              <NCollapseItem name="basic" title="基础信息">
                <NFormItem label="名称" path="name" required>
                  <NInput v-model:value="personaForm.name" placeholder="例如：导游小助手" />
                </NFormItem>
                <NFormItem label="描述" path="description">
                  <NInput v-model:value="personaForm.description" type="textarea" placeholder="简要描述角色卡的用途和特点" :autosize="{ minRows: 2, maxRows: 4 }" />
                </NFormItem>
              </NCollapseItem>
              <!-- 角色定义（可折叠） -->
              <NCollapseItem name="personality" title="角色定义（SillyTavern）">
                <NFormItem label="性格 (personality)" path="personality">
                  <NInput v-model:value="personaForm.personality" type="textarea" placeholder="角色的性格特征描述" :autosize="{ minRows: 2, maxRows: 4 }" />
                </NFormItem>
                <NFormItem label="场景 (scenario)" path="scenario">
                  <NInput v-model:value="personaForm.scenario" type="textarea" placeholder="对话发生的场景背景" :autosize="{ minRows: 2, maxRows: 4 }" />
                </NFormItem>
                <NFormItem label="开场白 (first_mes)" path="first_mes">
                  <NInput v-model:value="personaForm.first_mes" type="textarea" placeholder="角色首次对话的开场白" :autosize="{ minRows: 2, maxRows: 4 }" />
                </NFormItem>
                <NFormItem label="对话示例 (mes_example)" path="mes_example">
                  <NInput v-model:value="personaForm.mes_example" type="textarea" placeholder="示例对话，用于指导模型风格" :autosize="{ minRows: 3, maxRows: 6 }" />
                </NFormItem>
                <NFormItem label="系统提示词 (system_prompt)" path="system_prompt">
                  <NInput v-model:value="personaForm.system_prompt" type="textarea" placeholder="注入给 LLM 的系统级提示词" :autosize="{ minRows: 3, maxRows: 6 }" />
                </NFormItem>
              </NCollapseItem>
              <!-- 高级设置（可折叠） -->
              <NCollapseItem name="advanced" title="高级设置">
                <NFormItem label="Live2D 模型 ID" path="live2d_asset_id">
                  <NInput v-model:value="personaForm.live2d_asset_id" placeholder="关联的 Live2D 资产 ID（选填，数字）" />
                </NFormItem>
                <NFormItem label="Voice ID" path="voice_id">
                  <NInput v-model:value="personaForm.voice_id" placeholder="关联的语音角色 ID（选填）" />
                </NFormItem>
                <NFormItem label="标签 (tags)" path="tags">
                  <NInput v-model:value="tagsInput" placeholder="逗号分隔，例如：导游, 友善, 知识丰富" />
                </NFormItem>
                <NFormItem label="范围 (scope)" path="scope">
                  <NSelect v-model:value="personaForm.scope" :options="[{ label: '公开 (Public)', value: 'public' }, { label: '私有 (User)', value: 'user' }]" />
                </NFormItem>
                <NFormItem label="设为默认" path="is_default">
                  <NSwitch v-model:value="personaForm.is_default" />
                </NFormItem>
              </NCollapseItem>
            </NCollapse>
          </NForm>
          <div class="modal-actions">
            <NButton @click="showPersonaModal = false" :disabled="personaSaving">取消</NButton>
            <NButton type="primary" @click="handlePersonaSubmit" :loading="personaSaving">{{ personaSaving ? '保存中...' : '保存' }}</NButton>
          </div>
        </div>
      </NModal>

      <!-- ==================== KNOWLEDGE PREVIEW MODAL ==================== -->
      <NModal v-model:show="showKnowledgePreview" :mask-closable="true">
        <div class="preview-modal">
          <div class="modal-header">
            <h3>文档预览</h3>
            <button class="modal-close" @click="showKnowledgePreview = false">✕</button>
          </div>
          <div v-if="previewDoc" class="preview-info">
            <div class="info-row"><span class="info-label">📄 文件名</span><span class="info-value">{{ previewDoc.filename }}</span></div>
            <div class="info-row"><span class="info-label">📏 大小</span><span class="info-value">{{ previewDoc.size_display }}</span></div>
            <div class="info-row">
              <span class="info-label">📊 状态</span>
              <span class="info-value">
                <NTag :type="previewDoc.status === 'ready' ? 'success' : previewDoc.status === 'pending' ? 'warning' : previewDoc.status === 'failed' ? 'error' : 'info'" size="small">
                  {{ previewDoc.status === 'ready' ? '已索引' : previewDoc.status === 'pending' ? '等待处理' : previewDoc.status === 'failed' ? '失败' : '处理中' }}
                </NTag>
              </span>
            </div>
            <div class="info-row"><span class="info-label">📅 上传时间</span><span class="info-value">{{ previewDoc.created_at }}</span></div>
          </div>
          <div class="preview-chunks">
            <h4 class="chunks-title">Chunks 预览 <span v-if="previewChunks.length" class="chunks-count">(共 {{ previewChunks.length }} 块)</span></h4>
            <NSpin v-if="previewLoading" />
            <div v-else-if="previewChunks.length === 0" class="chunks-empty">{{ previewDoc?.status === 'ready' ? '暂无 chunk 数据' : '文档尚未向量化，请先点击 Vectorize' }}</div>
            <div v-else class="chunks-list">
              <div v-for="chunk in previewChunks.slice(0, 10)" :key="chunk.id" class="chunk-item">
                <div class="chunk-header"><span class="chunk-index">#{{ chunk.chunk_index }}</span><span class="chunk-size">[{{ chunk.content.length }} chars]</span></div>
                <p class="chunk-text">{{ truncateText(chunk.content, 150) }}</p>
              </div>
              <div v-if="previewChunks.length > 10" class="chunks-more">还有 {{ previewChunks.length - 10 }} 个 chunk 未展示</div>
            </div>
          </div>
          <div class="modal-actions"><NButton @click="showKnowledgePreview = false">关闭</NButton></div>
        </div>
      </NModal>
    </div>
  </div>
</template>

<style>
/* ===== ROOT RESPONSIVE ===== */
.admin-root { width:100vw; height:100vh; background:#0078D7; display:flex; justify-content:center; align-items:center; font-family:'Inter',system-ui,-apple-system,sans-serif; overflow:hidden }
/* Using dynamic aspect ratio scaling based on viewport width/height to avoid excessive scaling */
.layout-wrapper {
  width: 100%;
  max-width: 1920px;
  height: 100%;
  max-height: 1080px;
  position: relative;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  box-shadow: 0 0 30px rgba(0,0,0,.5);
  overflow: hidden;
}
@media (min-width: 1921px) or (min-height: 1081px) {
  .layout-wrapper {
    aspect-ratio: 16/9;
    height: auto;
    width: auto;
    min-width: 1280px;
    min-height: 720px;
  }
}
.fullscreen-bg { position:absolute; top:0; left:0; width:100%; height:100%; object-fit:cover; z-index:0; filter:brightness(.85) contrast(1.05) }

/* ===== NAVBAR ===== */
.navbar { width:100%; height:80px; display:flex; flex-direction:row; justify-content:space-between; align-items:center; padding:0 40px; background:rgba(255,255,255,.4); backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); border-bottom:1px solid rgba(255,255,255,.3); box-sizing:border-box; flex-shrink:0; z-index:10 }
.logo-zone { display:flex; align-items:center; gap:12px }
.logo-icon { width:32px; height:32px; color:#1E3A8A }
.logo-text { display:flex; flex-direction:column }
.logo-cn { font-size:18px; font-weight:600; color:#1F2937; line-height:1.2 }
.logo-en { font-size:11px; color:#4B5563; line-height:1 }
.nav-menu { display:flex; gap:8px; background:rgba(255,255,255,.5); border-radius:40px; padding:8px; backdrop-filter:blur(10px); border:1px solid rgba(255,255,255,.4); box-shadow:0 4px 12px rgba(0,0,0,.05) }
.nav-item { padding:10px 32px; border-radius:30px; background:transparent; color:#4B5563; font-size:15px; font-weight:600; border:none; cursor:pointer; transition:all .2s; font-family:inherit; outline:none }
.nav-item:hover { background:rgba(255,255,255,.4) }
.nav-item.active { background:#FFF; color:#1E3A8A; box-shadow:0 4px 8px rgba(0,0,0,.08) }
.user-glass { display:flex; align-items:center; gap:12px; background:rgba(255,255,255,.5); backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); padding:6px 16px 6px 6px; border-radius:40px; border:1px solid rgba(255,255,255,.6); box-shadow:0 4px 12px rgba(0,0,0,.05) }
.bell-btn { width:36px; height:36px; border-radius:50%; background:rgba(255,255,255,.8); display:flex; justify-content:center; align-items:center; border:none; cursor:pointer; padding:0; transition:all .2s; outline:none }
.bell-btn:hover { background:#FFF }
.text-avatar { width:36px; height:36px; border-radius:50%; background:#1E3A8A; color:#FFF; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:18px; box-shadow:0 2px 8px rgba(30,58,138,.3) }
.username { font-size:14px; font-weight:600; color:#1F2937 }

/* ===== MAIN CONTAINER ===== */
.main-container { width:100%; flex:1; display:flex; flex-direction:row; padding:24px 40px; gap:24px; box-sizing:border-box; overflow:hidden; z-index:10; position:relative }

/* ===== PEEK HANDLES ===== */
.peek { position:absolute; top:50%; width:28px; height:90px; background:rgba(255,255,255,.85); backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); display:flex; align-items:center; justify-content:center; cursor:pointer; z-index:50; opacity:0; pointer-events:none; transition:all .3s cubic-bezier(.4,0,.2,1); color:#4B5563; box-shadow:0 8px 24px rgba(0,0,0,.12); border:1px solid rgba(255,255,255,.9) }
.peek.show { opacity:1; pointer-events:auto }
.left-peek { left:0; border-radius:0 14px 14px 0; border-left:none }
.left-peek.show { transform:translateY(-50%) }
.left-peek.show:hover { transform:translateY(-50%) translateX(4px) }
.right-peek { right:0; border-radius:14px 0 0 14px; border-right:none }
.right-peek.show { transform:translateY(-50%) }
.right-peek.show:hover { transform:translateY(-50%) translateX(-4px) }

/* ===== LEFT PANEL ===== */
.left-panel { flex:1; max-width:380px; min-width:300px; height:100%; background:rgba(255,255,255,.7); backdrop-filter:blur(30px); -webkit-backdrop-filter:blur(30px); border-radius:24px; padding:24px; display:flex; flex-direction:column; gap:20px; box-shadow:0 8px 32px rgba(0,0,0,.1); border:1px solid rgba(255,255,255,.6); box-sizing:border-box; transition:all .4s cubic-bezier(.4,0,.2,1); overflow-y:auto; scrollbar-width:none; -ms-overflow-style:none; transform-origin:left center }
.left-panel::-webkit-scrollbar { display:none }
.left-panel.hidden { flex:0 0 0; min-width:0; max-width:0; padding:0; margin:0; border:none; opacity:0; overflow:hidden }
.panel-hd { display:flex; justify-content:space-between; align-items:center }
.panel-hd h3 { margin:0; font-size:18px; font-weight:700; color:#1F2937; white-space:nowrap }
.icon-btn { background:rgba(255,255,255,.5); border:1px solid rgba(255,255,255,.8); color:#4B5563; cursor:pointer; padding:8px; border-radius:50%; display:flex; align-items:center; justify-content:center; transition:all .2s }
.icon-btn:hover { background:rgba(255,255,255,.9); color:#1F2937 }

/* Persona Cards */
.persona-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; flex-shrink:0 }
.persona-card { aspect-ratio:9/16; border-radius:16px; overflow:hidden; position:relative; box-shadow:0 4px 12px rgba(0,0,0,.1); cursor:pointer; border:2px solid transparent; transition:all .2s; z-index:1; background:rgba(255,255,255,.3); min-height:0 }
.persona-card.active { border-color:#3B82F6; box-shadow:0 8px 24px rgba(59,130,246,.3); z-index:2 }
.persona-card img { width:100%; height:100%; object-fit:contain; transition:transform .3s }
.persona-card:hover img { transform:scale(1.05) }
.no-icon { width:100%; height:100%; display:flex; align-items:center; justify-content:center; color:#9CA3AF; font-size:14px; font-weight:600 }
.card-name { position:absolute; bottom:0; left:0; width:100%; background:rgba(255,255,255,.65); backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px); padding:12px 8px; text-align:center; font-size:13px; font-weight:600; color:#1F2937; border-top:1px solid rgba(255,255,255,.5); box-sizing:border-box; border-radius:0 0 14px 14px }

.setting-tabs { display:flex; background:rgba(255,255,255,.6); border-radius:12px; padding:4px }
.stab { flex:1; text-align:center; padding:8px 0; font-size:14px; color:#4B5563; cursor:pointer; border-radius:8px; transition:all .2s; white-space:nowrap }
.stab.active { background:#FFF; color:#3B82F6; font-weight:600; box-shadow:0 2px 4px rgba(0,0,0,.05) }

.setting-list { display:flex; flex-direction:column; gap:10px; flex-shrink:0 }
.sitem { display:flex; justify-content:space-between; align-items:center; padding:12px 16px; background:rgba(255,255,255,.7); border-radius:12px; font-size:14px; color:#4B5563 }
.sval { font-weight:600; color:#1F2937 }
.model-link { color:#3B82F6; cursor:pointer; text-decoration:none; padding:4px 10px; border-radius:6px; background:rgba(59,130,246,.1); transition:background .2s }
.model-link:hover { background:rgba(59,130,246,.2) }

/* Model selector dropdown */
.model-drop { background:rgba(255,255,255,.95); border-radius:12px; border:1px solid rgba(0,0,0,.08); box-shadow:0 8px 20px rgba(0,0,0,.1); padding:8px; display:flex; flex-direction:column; gap:4px }
.model-opt { padding:10px 14px; border-radius:8px; cursor:pointer; font-size:14px; color:#4B5563; transition:all .15s }
.model-opt:hover { background:#F3F4F6 }
.model-opt.sel { background:#DBEAFE; color:#1E3A8A; font-weight:600 }

/* ===== CENTER PANEL (flex:1 auto-expands to fill available space) ===== */
.center-panel { flex:2; min-width:400px; height:100%; position:relative; display:flex; justify-content:center; align-items:center; border-radius:24px; transition:all .4s cubic-bezier(.4,0,.2,1) }
.preview-box { position:absolute; inset:0; border-radius:24px; background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.15); box-shadow:0 8px 32px rgba(0,0,0,.05); display:flex; align-items:center; justify-content:center; overflow:hidden }
.preview-box canvas { position:absolute; top:0; left:0; width:100%; height:100%; object-fit:contain; z-index:1 }
.sdk-holder { position:relative; z-index:2; display:flex; flex-direction:column; align-items:center; gap:20px; padding:40px 80px; background:rgba(0,0,0,.2); backdrop-filter:blur(24px); -webkit-backdrop-filter:blur(24px); border-radius:28px; border:1px dashed rgba(255,255,255,.25) }
.ph-text { color:rgba(255,255,255,.85); font-size:20px; font-weight:500; letter-spacing:1px }

.center-actions { position:absolute; bottom:24px; display:flex; flex-wrap:wrap; justify-content:center; gap:10px; background:rgba(255,255,255,.4); backdrop-filter:blur(24px); -webkit-backdrop-filter:blur(24px); padding:8px; border-radius:30px; border:1px solid rgba(255,255,255,.5); box-shadow:0 12px 32px rgba(0,0,0,.15),inset 0 1px 1px rgba(255,255,255,.6); white-space:nowrap; max-width:90%; z-index:3 }
.act-pill { padding:12px 22px; border-radius:24px; background:transparent; border:none; font-size:14px; font-weight:600; color:#1F2937; cursor:pointer; transition:all .2s; outline:none; font-family:inherit }
.act-pill.active { background:#FFF; color:#1E3A8A; box-shadow:0 4px 12px rgba(0,0,0,.08) }
.act-pill:hover:not(.active) { background:rgba(255,255,255,.5) }
.act-pill:active { transform:scale(.96) }

/* ===== RIGHT PANEL ===== */
.right-panel { flex:2.5; max-width:620px; min-width:450px; height:100%; background:rgba(255,255,255,.7); backdrop-filter:blur(30px); -webkit-backdrop-filter:blur(30px); border-radius:24px; border:1px solid rgba(255,255,255,.6); box-shadow:0 8px 32px rgba(0,0,0,.1); display:flex; flex-direction:column; overflow:hidden; box-sizing:border-box; transition:all .4s cubic-bezier(.4,0,.2,1); transform-origin:right center }
.right-panel.hidden { flex:0 0 0; min-width:0; max-width:0; padding:0; margin:0; border:none; opacity:0; overflow:hidden }
.rp-inner { width:100%; flex:1; display:flex; flex-direction:column; gap:18px; padding:24px; overflow-y:auto; box-sizing:border-box; scrollbar-width:none; -ms-overflow-style:none }
.rp-inner::-webkit-scrollbar { display:none }
.rp-hd { display:flex; align-items:center; gap:12px }
.rp-hd h2 { margin:0; font-size:20px; font-weight:700; color:#1F2937; white-space:nowrap }

.date-row { display:flex; justify-content:space-between; align-items:center }
.db-tabs { display:flex; gap:4px; background:rgba(255,255,255,.8); padding:4px; border-radius:20px; box-shadow:0 2px 8px rgba(0,0,0,.05) }
.tbtn { background:transparent; color:#4B5563; padding:6px 18px; border-radius:16px; border:none; font-size:13px; font-weight:600; cursor:pointer; transition:all .2s; outline:none; font-family:inherit }
.tbtn:hover:not(.active) { background:rgba(255,255,255,.5) }
.tbtn.active { background:#3B82F6; color:#FFF; box-shadow:0 4px 12px rgba(59,130,246,.4) }

.date-picker-wrap { position:relative }
.dp-btn { display:flex; align-items:center; gap:8px; padding:7px 18px; background:rgba(255,255,255,.8); border:1px solid rgba(255,255,255,.9); border-radius:16px; font-size:13px; font-weight:600; color:#4B5563; cursor:pointer; box-shadow:0 2px 8px rgba(0,0,0,.05); font-family:inherit; outline:none; transition:all .2s }
.dp-btn:hover { background:#FFF }
.dp-btn.active { background:#3B82F6; color:#FFF; border-color:#3B82F6 }
.cal-drop { position:absolute; top:110%; right:0; width:280px; background:rgba(255,255,255,.97); backdrop-filter:blur(20px); border-radius:16px; padding:16px; box-shadow:0 12px 32px rgba(0,0,0,.15); border:1px solid rgba(255,255,255,.8); z-index:100 }
.cal-month { text-align:center; font-weight:700; color:#1F2937; font-size:15px; margin-bottom:12px }
.cal-grid { display:grid; grid-template-columns:repeat(7,1fr); gap:4px; text-align:center; font-size:13px }
.cal-dow { font-weight:600; color:#9CA3AF; margin-bottom:8px; font-size:12px }
.cal-empty { height:28px }
.cal-day { padding:7px 0; border-radius:8px; cursor:pointer; color:#4B5563; font-weight:500 }
.cal-day:hover { background:#F3F4F6 }
.cal-day.sel { background:#3B82F6; color:#FFF }
.cal-day.mid { background:#DBEAFE; color:#1E3A8A; border-radius:0 }
.cal-btns { display:flex; justify-content:flex-end; gap:8px; margin-top:14px }
.cal-btns button { padding:6px 16px; border-radius:8px; border:none; font-weight:600; font-size:13px; cursor:pointer }
.cal-btns button.ok { background:#3B82F6; color:#FFF }

/* Metric cards */
.metric-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px }
.mcard { background:rgba(255,255,255,.8); border-radius:16px; padding:14px; box-shadow:0 4px 12px rgba(0,0,0,.03); display:flex; flex-direction:column; transition:transform .2s ease,box-shadow .2s ease; border:1px solid rgba(255,255,255,.8); cursor:pointer }
.mcard:hover { transform:translateY(-2px); box-shadow:0 8px 24px rgba(59,130,246,.08); background:#FFF }
.mt { font-size:12px; font-weight:600; color:#6B7280 }
.mv { font-size:22px; font-weight:700; color:#1F2937; margin:6px 0; line-height:1.2 }
.mtr { font-size:11px; display:flex; align-items:center; font-weight:600; gap:4px }
.mtr.up { color:#10B981 }
.mtr.dn { color:#EF4444 }

/* Chart cards */
.charts2col { display:grid; grid-template-columns:minmax(0, 1fr) minmax(0, 1.5fr); gap:14px }
.charts3col { display:grid; grid-template-columns:1.2fr 1fr 1.3fr; gap:14px }
.cchart { min-width:0; background:rgba(255,255,255,.8); border-radius:20px; padding:18px; box-shadow:0 4px 12px rgba(0,0,0,.03); display:flex; flex-direction:column; border:1px solid rgba(255,255,255,.8); transition:transform .2s ease,box-shadow .2s ease; cursor:pointer }
.cchart:hover { transform:translateY(-2px); box-shadow:0 8px 24px rgba(59,130,246,.08); background:#FFF }
.cchart h3 { margin:0 0 14px; font-size:15px; font-weight:700; color:#1F2937 }

.top5-list { display:flex; flex-direction:column; gap:10px }
.t5row { display:flex; align-items:center; font-size:13px; padding:2px 0 }
.t5idx { width:22px; height:22px; display:flex; align-items:center; justify-content:center; border-radius:6px; font-size:12px; font-weight:700; margin-right:10px }
.r1 { background:#FEF2F2; color:#EF4444 }
.r2 { background:#FFFBEB; color:#F59E0B }
.r3 { background:#ECFDF5; color:#10B981 }
.r4,.r5 { background:#F3F4F6; color:#6B7280 }
.t5txt { flex:1; color:#374151; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-weight:600 }
.t5cnt { color:#9CA3AF; font-size:12px; font-weight:600 }

.cloud { flex:1; display:flex; flex-wrap:wrap; align-items:center; justify-content:center; align-content:center; gap:8px 14px }
.cloud-lg { gap:14px 24px; padding:20px }
.cw { font-weight:600; line-height:1.3; cursor:default; transition:transform .2s }
.cw:hover { transform:scale(1.15) }
.c1 { font-size:24px; color:#3B82F6; order:1 }
.c2 { font-size:21px; color:#F59E0B; order:2 }
.c3 { font-size:19px; color:#10B981; order:3 }
.c4 { font-size:16px; color:#8B5CF6; order:4 }
.c5 { font-size:14px; color:#6B7280; order:5 }
.c6 { font-size:12px; color:#9CA3AF; order:6 }
.c7 { font-size:11px; color:#C4C4C4; order:7 }
.cloud-lg .c1 { font-size:42px } .cloud-lg .c2 { font-size:34px } .cloud-lg .c3 { font-size:28px }
.cloud-lg .c4 { font-size:22px } .cloud-lg .c5 { font-size:18px } .cloud-lg .c6 { font-size:15px } .cloud-lg .c7 { font-size:13px }

.donut { flex:1; display:flex; align-items:center; justify-content:center; padding:8px }
.fb-list { display:flex; flex-direction:column; gap:10px }
.fbi { display:flex; flex-direction:column; gap:3px; padding-bottom:10px; border-bottom:1px solid rgba(0,0,0,.04) }
.fbi:last-child { border-bottom:none; padding-bottom:0 }
.fbt { font-size:11px; color:#9CA3AF; font-weight:600 }
.fbtxt { font-size:13px; color:#4B5563; line-height:1.5; font-weight:500 }

/* ===== EXPAND OVERLAY ===== */
.expand-overlay { position:absolute; inset:0; background:rgba(0,0,0,.35); backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px); z-index:200; display:flex; justify-content:center; align-items:center }
.expand-card { position:relative; width:75%; max-height:75%; background:rgba(255,255,255,.95); backdrop-filter:blur(40px); -webkit-backdrop-filter:blur(40px); border-radius:28px; padding:40px; box-shadow:0 24px 64px rgba(0,0,0,.25); border:1px solid rgba(255,255,255,.9); display:flex; flex-direction:column; overflow-y:auto; scrollbar-width:none; -ms-overflow-style:none }
.expand-card::-webkit-scrollbar { display:none }
.trend-tooltip { position:absolute; pointer-events:none; transform:translate(-50%,-120%); background:#1F2937; color:#FFF; padding:4px 8px; border-radius:6px; font-size:12px; font-weight:600; white-space:nowrap; z-index:10 }
.x-btn { position:absolute; top:20px; right:20px; width:44px; height:44px; border-radius:50%; background:rgba(255,255,255,.5); backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); border:1px solid rgba(255,255,255,.5); color:#4B5563; cursor:pointer; display:flex; align-items:center; justify-content:center; transition:all .2s }
.x-btn:hover { background:rgba(255,255,255,.9); color:#1F2937 }

/* Expanded Feedback specific */
.fb-expand-list { display:flex; flex-direction:column }
.fb-expand-item { display:flex; flex-direction:column; padding:20px 0; border-bottom:1px solid #F3F4F6 }
.fb-content-row { display:flex; align-items:center; gap:16px; font-size:16px }
.fb-t { color:#9CA3AF; font-weight:600; min-width:60px }
.fb-txt { flex:1; color:#374151; font-weight:500; line-height:1.6 }
.fb-reply-trigger { padding:8px 16px; border-radius:16px; background:#F3F4F6; color:#4B5563; font-size:14px; font-weight:600; border:none; cursor:pointer; transition:.2s; white-space:nowrap }
.fb-reply-trigger:hover { background:#E5E7EB }
.fb-admin-reply { margin-top:10px; margin-left:76px; padding:12px 16px; background:rgba(16,185,129,.06); border-left:3px solid #10B981; border-radius:0 12px 12px 0 }
.fb-reply-box { display:flex; flex-direction:column; gap:12px; margin-top:16px; margin-left:76px; padding:16px; background:rgba(0,0,0,.03); border-radius:16px }
.fb-textarea { width:100%; height:80px; background:#FFF; border:1px solid rgba(0,0,0,.1); border-radius:12px; padding:12px; font-family:inherit; font-size:14px; resize:none; outline:none; box-sizing:border-box }
.fb-submit { align-self:flex-end; padding:10px 24px; border-radius:12px; background:#3B82F6; color:#FFF; font-weight:600; border:none; cursor:pointer; transition:.2s }
.fb-submit:disabled { opacity:.5; cursor:not-allowed }
.fb-submit:not(:disabled):hover { background:#2563EB }

.slide-down-enter-active, .slide-down-leave-active { transition:all .3s ease; overflow:hidden }
.slide-down-enter-from, .slide-down-leave-to { opacity:0; max-height:0; margin-top:0; padding-top:0; padding-bottom:0 }
.slide-down-enter-to, .slide-down-leave-from { opacity:1; max-height:200px }

/* ===== SETTINGS / API CONFIG PAGES ===== */
.settings-container { width:100%; flex:1; display:flex; justify-content:center; align-items:center; padding:40px; box-sizing:border-box; z-index:10; overflow:hidden }
.settings-glass-card { width:100%; max-width:820px; background:rgba(255,255,255,.92); backdrop-filter:blur(40px); -webkit-backdrop-filter:blur(40px); border-radius:24px; border:1px solid rgba(255,255,255,.9); box-shadow:0 16px 48px rgba(0,0,0,.1); padding:48px; display:flex; flex-direction:column; gap:32px; max-height:90%; overflow-y:auto; scrollbar-width:none; -ms-overflow-style:none }
.settings-glass-card::-webkit-scrollbar { display:none }
.sc-hd { border-bottom:1px solid rgba(0,0,0,.08); padding-bottom:20px }
.sc-hd h2 { font-size:26px; font-weight:700; color:#1F2937; margin:0 0 6px }
.sc-hd p { font-size:14px; color:#6B7280; margin:0 }
.sc-body { display:flex; flex-direction:column; gap:14px; min-height:0; overflow-y:auto; flex:1; scrollbar-width:none; -ms-overflow-style:none }
.sc-body::-webkit-scrollbar { display:none }
.srow { display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,.5); padding:20px; border-radius:16px; border:1px solid rgba(0,0,0,.04) }
.sinfo h3 { margin:0 0 4px; font-size:15px; font-weight:600; color:#1F2937 }
.sinfo p { margin:0; font-size:12px; color:#6B7280 }
.ssel { padding:10px 14px; border-radius:12px; border:1px solid rgba(0,0,0,.1); background:#FFF; font-size:13px; color:#1F2937; font-weight:500; outline:none; cursor:pointer; min-width:150px }
.sinput { width:80px; padding:10px 12px; border-radius:12px; border:1px solid rgba(0,0,0,.1); background:#FFF; font-size:13px; color:#1F2937; outline:none; text-align:center }
.upbtn { padding:10px 24px; background:#3B82F6; color:#FFF; border:none; border-radius:12px; font-size:13px; font-weight:600; cursor:pointer; box-shadow:0 4px 12px rgba(59,130,246,.2); transition:all .2s }
.upbtn:hover { background:#2563EB; box-shadow:0 6px 16px rgba(59,130,246,.3); transform:translateY(-1px) }
.sc-actions { display:flex; justify-content:flex-end }
.pbtn { padding:14px 40px; background:#1E3A8A; color:#FFF; border:none; border-radius:16px; font-size:15px; font-weight:600; cursor:pointer; transition:all .2s }
.pbtn:hover { background:#1e40af; box-shadow:0 8px 24px rgba(30,58,138,.3) }

/* Toggle */
.tgl { width:56px; height:32px; border-radius:16px; background:rgba(0,0,0,.15); border:none; position:relative; cursor:pointer; transition:.3s; flex-shrink:0 }
.tgl.active { background:#3B82F6; box-shadow:0 0 12px rgba(59,130,246,.3) }
.tgl-knob { width:24px; height:24px; background:#FFF; border-radius:50%; position:absolute; top:4px; left:4px; transition:.3s cubic-bezier(.4,0,.2,1); box-shadow:0 2px 6px rgba(0,0,0,.2) }
.tgl.active .tgl-knob { left:28px }

/* Transitions */
.fade-enter-active,.fade-leave-active { transition:opacity .25s ease }
.fade-enter-from,.fade-leave-to { opacity:0 }

/* ===== ERROR BANNER ===== */
.error-banner { margin-top:12px; padding:10px 16px; background:rgba(239,68,68,.1); border:1px solid rgba(239,68,68,.3); border-radius:10px; color:#EF4444; font-size:13px }

/* ===== KNOWLEDGE UPLOAD ===== */
.knowledge-upload-zone { margin-bottom:20px }
.upload-dragger { border:1px dashed rgba(59,130,246,.4); border-radius:12px; padding:40px; text-align:center; background:rgba(59,130,246,.04); cursor:pointer; transition:background .3s }
.upload-dragger:hover { background:rgba(59,130,246,.08) }

/* ===== SHARED MODAL ===== */
.persona-modal { width:480px; max-height:80vh; overflow-y:auto; background:rgba(255,255,255,.97); backdrop-filter:blur(24px); -webkit-backdrop-filter:blur(24px); border-radius:20px; padding:32px; border:1px solid rgba(255,255,255,.6); box-shadow:0 16px 48px rgba(0,0,0,.15); scrollbar-width:none; -ms-overflow-style:none }
.persona-modal::-webkit-scrollbar { display:none }
.preview-modal { width:600px; max-height:80vh; overflow-y:auto; background:rgba(255,255,255,.97); backdrop-filter:blur(24px); -webkit-backdrop-filter:blur(24px); border-radius:20px; padding:32px; border:1px solid rgba(255,255,255,.6); box-shadow:0 16px 48px rgba(0,0,0,.15); scrollbar-width:none; -ms-overflow-style:none }
.preview-modal::-webkit-scrollbar { display:none }
/* NaiveUI NDataTable internal scrollbar hiding */
.n-scrollbar > .n-scrollbar-rail { display:none !important }
.modal-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:24px; padding-bottom:16px; border-bottom:1px solid rgba(0,0,0,.08) }
.modal-header h3 { margin:0; font-size:20px; font-weight:700; color:#1F2937 }
.modal-close { width:32px; height:32px; border-radius:50%; background:rgba(0,0,0,.05); border:none; color:#6B7280; font-size:16px; cursor:pointer; display:flex; align-items:center; justify-content:center; transition:all .2s }
.modal-close:hover { background:rgba(0,0,0,.1); color:#1F2937 }
.modal-actions { display:flex; justify-content:flex-end; gap:12px; margin-top:24px; padding-top:16px; border-top:1px solid rgba(0,0,0,.06) }

/* ===== PREVIEW ===== */
.preview-info { background:rgba(0,0,0,.02); border-radius:14px; padding:20px; margin-bottom:20px }
.info-row { display:flex; gap:12px; padding:8px 0; font-size:14px }
.info-label { color:#6B7280; font-weight:600; min-width:80px; flex-shrink:0 }
.info-value { color:#1F2937; font-weight:500 }
.preview-chunks { margin-top:8px }
.chunks-title { font-size:15px; font-weight:700; color:#1F2937; margin:0 0 12px }
.chunks-count { font-weight:400; color:#9CA3AF; font-size:13px }
.chunks-list { display:flex; flex-direction:column }
.chunk-item { padding:12px 0; border-bottom:1px solid rgba(0,0,0,.06) }
.chunk-header { display:flex; gap:8px; align-items:center; margin-bottom:6px }
.chunk-index { font-weight:700; color:#3B82F6; font-size:13px }
.chunk-size { font-size:11px; color:#9CA3AF }
.chunk-text { font-size:13px; color:#4B5563; line-height:1.6; margin:0; white-space:pre-wrap; word-break:break-all }
.chunks-empty { text-align:center; color:#9CA3AF; padding:24px 0; font-size:14px }
.chunks-more { text-align:center; color:#9CA3AF; padding:16px 0 4px; font-size:13px }

/* ===== ADMIN RESPONSIVE EXCLUDED AS REQUESTED ===== */
</style>
