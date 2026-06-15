// ── Auth ──────────────────────────────────────────────────────────────

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  display_name?: string
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

// ── Conversation ──────────────────────────────────────────────────────

export interface SessionCreate {
  persona_id?: string | null
  title?: string
}

export interface SessionOut {
  id: number
  user_id: number
  persona_id: string | null
  title: string
  created_at: string
  ended_at: string | null
}

export interface ConversationList {
  sessions: SessionOut[]
  total: number
}

export interface ChatMessageOut {
  id: number
  session_id: number
  role: "user" | "assistant"
  content: string
  created_at: string
}

// ── WebSocket Frames ──────────────────────────────────────────────────

export interface WsStateFrame {
  type: "state"
  phase: "thinking" | "streaming" | "done" | "error"
}

export interface WsTokenFrame {
  type: "token"
  text: string
}

export interface WsActionFrame {
  type: "action"
  tag: string
}

export interface WsDoneFrame {
  type: "done"
  message_id: number | null
  latency_ms: number
  tokens: { completion: number }
}

export interface WsErrorFrame {
  type: "error"
  code: string
  detail: string
}

export type WsServerFrame =
  | WsStateFrame
  | WsTokenFrame
  | WsActionFrame
  | WsDoneFrame
  | WsErrorFrame

// ── Client → Server ───────────────────────────────────────────────────

export interface WsUserTextIn {
  type: "user_text"
  session_id: string
  text: string
  ts: number
}

export interface WsInterruptIn {
  type: "interrupt"
}

// ── Feedback ──────────────────────────────────────────────────────────

export interface FeedbackResponse {
  success: boolean
  message: string
  feedback_id: number | null
  created_at: string | null
}

// ── TTS (Text-to-Speech) ──────────────────────────────────────────────

export interface TtsRequest {
  text: string
  voice?: string
  speed?: number
}

// ── ASR Config ────────────────────────────────────────────────────────

export interface AsrConfig {
  provider: string
  app_id: string | null
  api_key: string | null
  api_secret: string | null
  websocket_url: string | null
  enabled: boolean
}

// ── Quick Questions ───────────────────────────────────────────────────

export interface QuickQuestionItem {
  display_text: string  // 前端展示的问题内容
  send_text: string     // 触发时向后端发送的请求文本
}

// ── User Upload Responses ─────────────────────────────────────────────

export interface BackgroundUploadResponse {
  success: boolean
  message: string
  url: string | null
}

export interface ModelUploadResponse {
  success: boolean
  message: string
  model_id: string | null
}
