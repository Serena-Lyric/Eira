import axios from "axios"
import { http } from "./http"
import type {
  LoginRequest,
  TokenPair,
  UserInfo,
  DashboardMetrics,
  TopQuestion,
  SatisfactionTrendPoint,
  WordCloudItem,
  SentimentData,
  FeedbackItem,
  Persona,
  PersonaCreate,
  KnowledgeDocument,
  DocumentDetail,
  Asset,
  AppConfig,
  PersonaConfig,
  AdminStats,
} from "./types"

// ── Auth API ──────────────────────────────────────────────────────────

export const authApi = {
  async login(payload: LoginRequest): Promise<TokenPair> {
    const { data } = await axios.post("/api/auth/login", payload)
    return data
  },

  async refresh(refreshToken: string): Promise<TokenPair> {
    const { data } = await axios.post("/api/auth/refresh", {
      refresh_token: refreshToken,
    })
    return data
  },

  async getMe(): Promise<UserInfo> {
    const { data } = await http.get("/auth/me")
    return data
  },
}

// ── Dashboard API ─────────────────────────────────────────────────────

export const dashboardApi = {
  /** Get dashboard metrics for a given time range. */
  async getMetrics(params?: {
    range?: "day" | "week" | "month" | "custom"
    start_date?: string
    end_date?: string
  }): Promise<DashboardMetrics> {
    const { data } = await http.get("/admin/dashboard/metrics", { params })
    return data
  },

  /** Get top-N frequently asked questions. */
  async getTopQuestions(
    limit = 5,
    params?: { range?: string; start_date?: string; end_date?: string },
  ): Promise<TopQuestion[]> {
    const { data } = await http.get("/admin/dashboard/top-questions", {
      params: { limit, ...params },
    })
    return data
  },

  /** Get satisfaction trend data points. */
  async getSatisfactionTrend(params?: {
    range?: string
    start_date?: string
    end_date?: string
  }): Promise<SatisfactionTrendPoint[]> {
    const { data } = await http.get("/admin/dashboard/satisfaction-trend", {
      params,
    })
    return data
  },

  /** Get word cloud data. */
  async getWordCloud(params?: {
    range?: string
    limit?: number
  }): Promise<WordCloudItem[]> {
    const { data } = await http.get("/admin/dashboard/word-cloud", {
      params,
    })
    return data
  },

  /** Get sentiment analysis data. */
  async getSentiment(params?: {
    range?: string
  }): Promise<SentimentData> {
    const { data } = await http.get("/admin/dashboard/sentiment", {
      params,
    })
    return data
  },

  /** Get latest user feedback / service suggestions. */
  async getFeedback(params?: {
    limit?: number
  }): Promise<FeedbackItem[]> {
    const { data } = await http.get("/admin/dashboard/feedback", {
      params,
    })
    return data
  },

  /** Reply to a feedback item. */
  async replyFeedback(
    feedbackId: number,
    replyText: string,
  ): Promise<void> {
    await http.post(`/admin/dashboard/feedback/${feedbackId}/reply`, {
      reply_text: replyText,
    })
  },
}

// ── Persona API ───────────────────────────────────────────────────────

export const personaApi = {
  async list(): Promise<Persona[]> {
    const { data } = await http.get<{ items: Persona[]; total: number }>("/admin/personas")
    return data.items
  },

  async get(id: number): Promise<Persona> {
    const { data } = await http.get(`/admin/personas/${id}`)
    return data
  },

  async create(payload: PersonaCreate): Promise<Persona> {
    const { data } = await http.post("/admin/personas", payload)
    return data
  },

  async update(id: number, payload: Partial<PersonaCreate>): Promise<Persona> {
    const { data } = await http.patch(`/admin/personas/${id}`, payload)
    return data
  },

  async delete(id: number): Promise<void> {
    await http.delete(`/admin/personas/${id}`)
  },

  async setDefault(id: number): Promise<Persona> {
    const { data } = await http.post(`/admin/personas/${id}/set-default`)
    return data
  },

  async import(data: Record<string, unknown>, scope = "public"): Promise<Persona> {
    const { data: result } = await http.post("/admin/personas/import", { data, scope })
    return result
  },
}

// ── Knowledge Base API ────────────────────────────────────────────────

export const knowledgeApi = {
  async list(): Promise<KnowledgeDocument[]> {
    const { data } = await http.get<{ items: KnowledgeDocument[]; total: number }>("/admin/documents")
    return data.items
  },

  async upload(formData: FormData): Promise<KnowledgeDocument> {
    const { data } = await http.post("/admin/documents/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    return data
  },

  async getStatus(id: number): Promise<KnowledgeDocument> {
    const { data } = await http.get(`/admin/documents/${id}/status`)
    return data
  },

  async reprocess(id: number): Promise<{ document_id: number; status: string }> {
    const { data } = await http.post(`/admin/documents/${id}/reprocess`)
    return data
  },

  async getDetail(id: number): Promise<DocumentDetail> {
    const { data } = await http.get(`/admin/documents/${id}`)
    return data
  },

  async delete(id: number): Promise<void> {
    await http.delete(`/admin/documents/${id}`)
  },
}

// ── Assets API (Live2D & Backgrounds) ─────────────────────────────────

export const assetApi = {
  async list(): Promise<Asset[]> {
    const { data } = await http.get("/admin/assets")
    return data.items
  },

  async uploadLive2D(formData: FormData): Promise<Asset> {
    const { data } = await http.post("/admin/assets/live2d", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    return data
  },

  async uploadBackground(formData: FormData): Promise<Asset> {
    const { data } = await http.post("/admin/assets/backgrounds", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    return data
  },

  async setDefault(id: number): Promise<Asset> {
    const { data } = await http.post(`/admin/assets/${id}/set-default`)
    return data
  },

  async delete(id: number): Promise<void> {
    await http.delete(`/admin/assets/${id}`)
  },

  /** Get a presigned download URL for an asset. */
  async getDownloadUrl(id: number): Promise<{ url: string; expires_in: number }> {
    const { data } = await http.get(`/admin/assets/${id}/download`)
    return data
  },
}

// ── App Config API ────────────────────────────────────────────────────

export const configApi = {
  async get(): Promise<AppConfig> {
    const { data } = await http.get("/admin/settings")
    return data.settings
  },

  async update(
    partial: Partial<AppConfig>,
  ): Promise<AppConfig> {
    // Backend expects { settings: { key: value } }
    const { data } = await http.patch("/admin/settings", { settings: partial })
    return data.settings
  },
}

// ── Persona Config API (Live2D & Speech) ──────────────────────────────

export const personaConfigApi = {
  async get(): Promise<PersonaConfig> {
    const { data } = await http.get("/admin/persona-config/")
    return data
  },

  async update(
    partial: Partial<PersonaConfig>,
  ): Promise<PersonaConfig> {
    const { data } = await http.patch("/admin/persona-config/", partial)
    return data
  },
}

// ── Admin Stats API ────────────────────────────────────────────────────

export const statsApi = {
  /** Get admin dashboard stats (account count + conversation count). */
  async get(): Promise<AdminStats> {
    const { data } = await http.get("/admin/stats")
    return data
  },
}
