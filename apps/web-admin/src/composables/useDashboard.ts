import { ref, computed } from 'vue'
import { dashboardApi, statsApi } from '../services/api'
import type {
  DashboardMetrics,
  TopQuestion,
  SatisfactionTrendPoint,
  WordCloudItem,
  SentimentData,
  FeedbackItem,
} from '../services/types'

export type TimeRange = 'day' | 'week' | 'month' | 'custom'

/**
 * Dashboard data composable.
 *
 * Wraps the dashboard API with reactive state, loading indicators, and
 * a time-range filter. Falls back to structured mock data when the backend
 * endpoints are not yet available (HTTP 404 / connection refused).
 */
export function useDashboard() {
  const currentRange = ref<TimeRange>('day')
  const customStart = ref<string | undefined>()
  const customEnd = ref<string | undefined>()

  const metrics = ref<DashboardMetrics>({
    total_visitors: 0,
    total_conversations: 0,
    avg_response_latency_ms: 0,
    satisfaction_pct: 0,
    visitors_change_pct: 0,
    conversations_change_pct: 0,
    latency_change_ms: 0,
    satisfaction_change_pct: 0,
  })
  const topQuestions = ref<TopQuestion[]>([])
  const satisfactionTrend = ref<SatisfactionTrendPoint[]>([])
  const satisfactionTrendMonth = ref<SatisfactionTrendPoint[]>([])
  const wordCloud = ref<WordCloudItem[]>([])
  const sentiment = ref<SentimentData>({
    positive_pct: 0,
    neutral_pct: 0,
    negative_pct: 0,
  })
  const feedback = ref<FeedbackItem[]>([])

  const loading = ref(false)
  const error = ref<string | null>(null)

  function buildParams() {
    const params: Record<string, string> = { range: currentRange.value }
    if (currentRange.value === 'custom') {
      if (customStart.value) params.start_date = customStart.value
      if (customEnd.value) params.end_date = customEnd.value
    }
    return params
  }

  async function fetchAll() {
    loading.value = true
    error.value = null
    const params = buildParams()

    try {
      const [m, tq, st, stMonth, wc, se, fb, realStats] = await Promise.all([
        dashboardApi.getMetrics(params).catch(() => null),
        dashboardApi.getTopQuestions(5, params).catch(() => null),
        dashboardApi.getSatisfactionTrend({ range: 'week' }).catch(() => null),
        dashboardApi.getSatisfactionTrend({ range: 'month' }).catch(() => null),
        dashboardApi.getWordCloud(params).catch(() => null),
        dashboardApi.getSentiment(params).catch(() => null),
        dashboardApi.getFeedback({ limit: 10 }).catch(() => null),
        statsApi.get().catch(() => null),
      ])

      // Metrics: fallback to mock if backend returns all-zeros (stub)
      if (m && !isEmptyMetrics(m)) {
        metrics.value = m
      } else {
        metrics.value = getMockMetrics(currentRange.value)
      }

      // Always overlay real stats on top (even if metrics came from mock)
      if (realStats) {
        metrics.value = {
          ...metrics.value,
          total_visitors: realStats.total_accounts,
          total_conversations: realStats.total_conversations,
        }
      }

      // Top Questions: fallback to mock if backend returns empty array
      if (tq && tq.length > 0) topQuestions.value = tq
      else topQuestions.value = getMockTopQuestions()

      // Satisfaction Trend: week for card, month for expanded detail
      satisfactionTrend.value = st || []
      satisfactionTrendMonth.value = stMonth || []

      // Word Cloud: fallback to mock if backend returns empty array
      if (wc && wc.length > 0) wordCloud.value = wc
      else wordCloud.value = getMockWordCloud()

      // Sentiment: fallback to mock if backend returns all-zeros (stub)
      if (se && (se.positive_pct > 0 || se.neutral_pct > 0 || se.negative_pct > 0)) {
        sentiment.value = se
      } else {
        sentiment.value = getMockSentiment()
      }

      // Feedback: use real data from DB (P1-6 fixed), show empty if no data
      if (fb && fb.length > 0) feedback.value = fb
      else feedback.value = []

    } catch (e: any) {
      error.value = e?.message || 'Failed to load dashboard data'
    } finally {
      loading.value = false
    }
  }

  function setRange(range: TimeRange, start?: string, end?: string) {
    currentRange.value = range
    customStart.value = start
    customEnd.value = end
    fetchAll()
  }

  async function replyToFeedback(feedbackId: number, replyText: string) {
    await dashboardApi.replyFeedback(feedbackId, replyText)
    // Refresh feedback list after reply
    const fb = await dashboardApi.getFeedback({ limit: 10 }).catch(() => null)
    if (fb) feedback.value = fb
  }

  return {
    // State
    currentRange,
    customStart,
    customEnd,
    metrics,
    topQuestions,
    satisfactionTrend,
    satisfactionTrendMonth,
    wordCloud,
    sentiment,
    feedback,
    loading,
    error,
    // Actions
    fetchAll,
    setRange,
    replyToFeedback,
  }
}

// ── Helpers ────────────────────────────────────────────────────────────

/** Detect stub responses: backend returns all-zeros when no real analytics exist. */
function isEmptyMetrics(m: DashboardMetrics): boolean {
  return (
    m.total_visitors === 0 &&
    m.total_conversations === 0 &&
    m.avg_response_latency_ms === 0 &&
    m.satisfaction_pct === 0
  )
}

// ── Mock data providers (used when backend endpoints return 404 / empty) ─

function getMockMetrics(range: TimeRange): DashboardMetrics {
  if (range === 'day') {
    return {
      total_visitors: 1258,
      total_conversations: 8432,
      avg_response_latency_ms: 1200,
      satisfaction_pct: 98.5,
      visitors_change_pct: 12.5,
      conversations_change_pct: 5.2,
      latency_change_ms: 100,
      satisfaction_change_pct: 1.0,
    }
  }
  if (range === 'week') {
    return {
      total_visitors: 8420,
      total_conversations: 52100,
      avg_response_latency_ms: 1150,
      satisfaction_pct: 97.8,
      visitors_change_pct: 8.3,
      conversations_change_pct: 3.1,
      latency_change_ms: -50,
      satisfaction_change_pct: 0.5,
    }
  }
  return {
    total_visitors: 32100,
    total_conversations: 198400,
    avg_response_latency_ms: 1180,
    satisfaction_pct: 97.2,
    visitors_change_pct: 15.0,
    conversations_change_pct: 10.5,
    latency_change_ms: -80,
    satisfaction_change_pct: -0.3,
  }
}

function getMockTopQuestions(): TopQuestion[] {
  return [
    { rank: 1, text: '洗手间在哪里？', count: 342, percentage: 32 },
    { rank: 2, text: '今天有什么表演？', count: 289, percentage: 27 },
    { rank: 3, text: '餐厅推荐', count: 215, percentage: 20 },
    { rank: 4, text: '怎么去北门？', count: 198, percentage: 18 },
    { rank: 5, text: '门票包含哪些项目？', count: 156, percentage: 14 },
  ]
}

function getMockSatisfactionTrend(): SatisfactionTrendPoint[] {
  return [
    { date: '2026-05-25', score: 98 },
    { date: '2026-05-26', score: 96 },
    { date: '2026-05-27', score: 99 },
    { date: '2026-05-28', score: 97 },
    { date: '2026-05-29', score: 99 },
  ]
}

function getMockWordCloud(): WordCloudItem[] {
  return [
    { text: '路线', weight: 0.9, color: '#3B82F6' },
    { text: '美食', weight: 0.85, color: '#F59E0B' },
    { text: '表演时间', weight: 0.8, color: '#10B981' },
    { text: '门票', weight: 0.7, color: '#8B5CF6' },
    { text: '天气', weight: 0.65, color: '#6B7280' },
    { text: '洗手间', weight: 0.6, color: '#EF4444' },
    { text: '停车', weight: 0.55, color: '#EC4899' },
    { text: '地铁', weight: 0.5, color: '#6366F1' },
    { text: '优惠', weight: 0.45, color: '#14B8A6' },
  ]
}

function getMockSentiment(): SentimentData {
  return {
    positive_pct: 75,
    neutral_pct: 12,
    negative_pct: 13,
  }
}

