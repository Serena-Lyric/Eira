// ── Auth (reused from web-user pattern) ───────────────────────────────

export interface LoginRequest {
  email: string
  password: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface UserInfo {
  id: number
  email: string
  display_name: string
  role: string
}

// ── Dashboard ─────────────────────────────────────────────────────────

export interface DashboardMetrics {
  total_visitors: number
  total_conversations: number
  avg_response_latency_ms: number
  satisfaction_pct: number
  visitors_change_pct: number
  conversations_change_pct: number
  latency_change_ms: number
  satisfaction_change_pct: number
}

export interface TopQuestion {
  rank: number
  text: string
  count: number
  percentage: number
}

export interface SatisfactionTrendPoint {
  date: string
  score: number
}

export interface WordCloudItem {
  text: string
  weight: number
  color: string
}

export interface SentimentData {
  positive_pct: number
  neutral_pct: number
  negative_pct: number
}

export interface FeedbackItem {
  id: number
  timestamp: string
  content: string
  replied: boolean
  reply_text?: string
}

// ── Persona ───────────────────────────────────────────────────────────

export interface Persona {
  id: number
  scope: string
  user_id: number | null
  name: string
  description: string | null
  personality: string | null
  scenario: string | null
  first_mes: string | null
  mes_example: string | null
  system_prompt: string | null
  avatar_asset_id: number | null
  live2d_asset_id: number | null
  voice_id: string | null
  tags: string[]
  is_default: boolean
  disabled: boolean
  created_at: string | null
  updated_at: string | null
}

export interface PersonaCreate {
  name: string
  scope?: string
  description?: string
  personality?: string
  scenario?: string
  first_mes?: string
  mes_example?: string
  system_prompt?: string
  avatar_asset_id?: number | null
  live2d_asset_id?: number | null
  voice_id?: string | null
  tags?: string[]
  is_default?: boolean
}

// ── Knowledge Base ────────────────────────────────────────────────────

export interface KnowledgeDocument {
  id: number
  filename: string
  mime_type: string | null
  file_size: number
  status: "ready" | "pending" | "processing" | "failed"
  chunk_count: number
  error: string | null
  uploader_id: number
  created_at: string | null
  updated_at: string | null
  // Computed on frontend
  size_display?: string
  progress?: number
}

export interface ChunkInfo {
  id: number
  chunk_index: number
  content: string
  metadata_json?: string | null
}

export interface DocumentDetail extends KnowledgeDocument {
  chunks: ChunkInfo[]
}

// ── Assets (Live2D & Backgrounds) ─────────────────────────────────────

export interface Asset {
  id: number
  kind: string
  name: string
  mime_type: string | null
  file_size: number | null
  user_id: number
  created_at: string | null
  /** Backend doesn't yet support defaults; always false for now. */
  is_default?: boolean
}

// ── App Config ────────────────────────────────────────────────────────

export interface AppConfig {
  llm_provider: string
  llm_model: string
  tts_provider: string
  asr_provider: string
  embedding_provider: string
  embedding_model: string
  search_provider: string
  daily_search_quota: number
  api_key_status: Record<string, "configured" | "missing">
  global_background_url?: string
  voice_persistence: boolean
  user_doc_quota: number
}

// ── Persona Config (Live2D & Speech) ──────────────────────────────────

export interface MotionOption {
  group: string       // 动作组名 (e.g. "Idle", "TapBody")
  index: number        // 组内索引
  label: string        // 展示标签 (e.g. "Idle_0", "挥手示意")
  file?: string        // 动作文件名
}

// ── Stats ─────────────────────────────────────────────────────────────

export interface AdminStats {
  total_accounts: number
  total_conversations: number
}

export interface PersonaConfig {
  active_model_id: string | null
  available_models: string[]

  idle_motion_group: string | null
  idle_motion_index: number | null
  available_idle_motions: MotionOption[]

  offline_idle_motion_group: string | null
  offline_idle_motion_index: number | null
  available_offline_motions: MotionOption[]

  default_speech_rate: number
  default_background_oss_key: string | null
  default_background_url: string | null
}
