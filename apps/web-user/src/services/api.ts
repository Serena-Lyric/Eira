import axios from "axios"
import { http } from "./http"
import type {
  LoginRequest,
  RegisterRequest,
  TokenPair,
  UserInfo,
  SessionCreate,
  SessionOut,
  ConversationList,
  ChatMessageOut,
  FeedbackResponse,
  TtsRequest,
  AsrConfig,
  BackgroundUploadResponse,
  ModelUploadResponse,
  QuickQuestionItem,
} from "./types"

// ── Auth API ──────────────────────────────────────────────────────────

export const authApi = {
  /** Login with email/password, returns token pair. */
  async login(payload: LoginRequest): Promise<TokenPair> {
    const { data } = await axios.post("/api/auth/login", payload)
    return data
  },

  /** Register a new user account. */
  async register(payload: RegisterRequest): Promise<UserInfo> {
    const { data } = await axios.post("/api/auth/register", payload)
    return data
  },

  /** Refresh the access/refresh token pair. */
  async refresh(refreshToken: string): Promise<TokenPair> {
    const { data } = await axios.post("/api/auth/refresh", {
      refresh_token: refreshToken,
    })
    return data
  },

  /** Get the currently authenticated user's profile. */
  async getMe(): Promise<UserInfo> {
    const { data } = await http.get("/auth/me")
    return data
  },
}

// ── User Data API ─────────────────────────────────────────────────────

export interface UserPreferences {
  background_url?: string
  background_blur: boolean
  voice_enabled: boolean
  camera_mode: 'front' | 'rear' | 'hidden'
  show_mic: boolean
  quick_questions: QuickQuestionItem[]
  chat_bubble_mode: 'center' | 'left' | 'hidden'
  quick_questions_mode: 'center' | 'left' | 'hidden'
  input_bar_mode: 'center' | 'left' | 'hidden'
  active_model_id?: string
  model_source: 'default' | 'custom'
  voice_input_mode: 'click' | 'persistent' | 'smart' | 'hidden'
  default_speech_rate: number
}

export const userApi = {
  /** Get user preferences from backend. */
  async getPreferences(): Promise<UserPreferences | null> {
    try {
      const { data } = await http.get("/user/preferences")
      return data
    } catch {
      // Backend may not have this endpoint yet
      return null
    }
  },

  /** Save user preferences to backend. */
  async savePreferences(prefs: Partial<UserPreferences>): Promise<void> {
    await http.patch("/user/preferences", prefs)
  },

  /** Upload user background image. Returns backend response with success status. */
  async uploadBackground(file: File): Promise<BackgroundUploadResponse> {
    const fd = new FormData()
    fd.append('background', file)
    const { data } = await http.post<BackgroundUploadResponse>("/user/background", fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  /** Upload Live2D model zip for user. Returns backend response with success status. */
  async uploadModel(file: File): Promise<ModelUploadResponse> {
    const fd = new FormData()
    fd.append('model_zip', file)
    const { data } = await http.post<ModelUploadResponse>("/user/model", fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  /** Get a presigned download URL for a Live2D model by OSS key (§4 fix). */
  async getModelDownloadUrl(ossKey: string): Promise<{ url: string }> {
    const { data } = await http.get("/user/model/download-url", {
      params: { oss_key: ossKey },
    })
    return data
  },
}

// ── Voice API ─────────────────────────────────────────────────────────

export const voiceApi = {
  /** Send audio blob for ASR processing. */
  async sendAudio(audioBlob: Blob): Promise<{ text: string }> {
    const fd = new FormData()
    fd.append('audio', audioBlob, 'recording.webm')
    const { data } = await http.post("/voice/asr", fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  /** Request TTS audio for given text. Returns audio as Blob. */
  async textToSpeech(req: TtsRequest): Promise<Blob> {
    const { data } = await http.post("/voice/tts", req, {
      responseType: 'blob',
    })
    return data
  },

  /** Get ASR service configuration (provider, api keys, etc.). */
  async getAsrConfig(): Promise<AsrConfig> {
    const { data } = await http.get("/voice/asr/config")
    return data
  },
}

// ── Document API ──────────────────────────────────────────────────────

export interface DocumentUploadOut {
  document_id: number
  filename: string
  status: string
  message: string
}

export interface DocumentProgress {
  document_id: number
  status: string
  stage: string | null
  progress: number
  error: string | null
}

export interface DocumentOut {
  id: number
  filename: string
  status: string
  file_size: number
  created_at: string
}

export interface DocumentListOut {
  items: DocumentOut[]
  total: number
}

export const documentApi = {
  /** Upload a document for knowledge base processing. */
  async upload(file: File): Promise<DocumentUploadOut> {
    const fd = new FormData()
    fd.append('file', file)
    const { data } = await http.post<DocumentUploadOut>('/documents/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  /** List uploaded documents for current user. */
  async list(params?: { status?: string; page?: number; page_size?: number }): Promise<DocumentListOut> {
    const { data } = await http.get<DocumentListOut>('/documents', { params })
    return data
  },

  /** Get document details by ID. */
  async get(documentId: number): Promise<DocumentOut> {
    const { data } = await http.get<DocumentOut>(`/documents/${documentId}`)
    return data
  },

  /** Get document processing progress. */
  async getProgress(documentId: number): Promise<DocumentProgress> {
    const { data } = await http.get<DocumentProgress>(`/documents/${documentId}/progress`)
    return data
  },

  /** Delete a document by ID. */
  async delete(documentId: number): Promise<{ success: boolean; message: string }> {
    const { data } = await http.delete(`/documents/${documentId}`)
    return data
  },
}

// ── Feedback API ──────────────────────────────────────────────────────

export const feedbackApi = {
  /** Submit user feedback. Returns success status and message from backend. */
  async submit(text: string): Promise<FeedbackResponse> {
    const { data } = await http.post<FeedbackResponse>("/feedback", { text })
    return data
  },
}

// ── Conversation API ──────────────────────────────────────────────────

export const conversationApi = {
  /** Create a new chat session. */
  async create(payload: SessionCreate = {}): Promise<SessionOut> {
    const { data } = await http.post("/conversations", payload)
    return data
  },

  /** List sessions for the current user. */
  async list(limit = 20, offset = 0): Promise<ConversationList> {
    const { data } = await http.get("/conversations", {
      params: { limit, offset },
    })
    return data
  },

  /** Get messages for a specific session. */
  async getMessages(
    sessionId: number,
    limit = 200,
    offset = 0,
  ): Promise<ChatMessageOut[]> {
    const { data } = await http.get(
      `/conversations/${sessionId}/messages`,
      { params: { limit, offset } },
    )
    return data
  },
}
