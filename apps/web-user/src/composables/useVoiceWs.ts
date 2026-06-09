/**
 * Voice WebSocket client — connects to /ws/voice for real-time ASR + TTS.
 *
 * Protocol:
 *   Client → Server:
 *     Binary frames: audio data (WebM/Opus chunks from MediaRecorder)
 *     {"type": "voice.start", "lang": "zh"}
 *     {"type": "voice.end"}
 *     {"type": "voice.barge_in"}
 *
 *   Server → Client:
 *     {"type": "asr.partial", "text": "..."}
 *     {"type": "asr.final", "text": "最终文本"}
 *     {"type": "chat.token", "text": "..."}
 *     {"type": "chat.action", "tag": "wave"}
 *     {"type": "chat.done", "latency_ms": ..., ...}
 *     {"type": "error", "code": "...", "detail": "..."}
 *     Binary frames: TTS audio opus chunks
 */
import { ref, type Ref } from 'vue'

export interface VoiceWsCallbacks {
  onAsrPartial?: (text: string) => void
  onAsrFinal?: (text: string) => void
  onChatToken?: (text: string) => void
  onChatAction?: (tag: string) => void
  onChatDone?: (data: Record<string, unknown>) => void
  onAudioChunk?: (chunk: ArrayBuffer) => void
  onError?: (code: string, detail: string) => void
}

export function useVoiceWs() {
  const isConnected: Ref<boolean> = ref(false)
  const isRecording: Ref<boolean> = ref(false)

  let ws: WebSocket | null = null
  let callbacks: VoiceWsCallbacks = {}
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempts = 0
  const maxReconnectAttempts = 5
  const reconnectBaseDelay = 1000 // 1s base

  function getAccessToken(): string {
    return localStorage.getItem('eira:at') || ''
  }

  function buildUrl(): string {
    if (typeof import.meta.env !== 'undefined' && import.meta.env.VITE_WS_URL) {
      return import.meta.env.VITE_WS_URL.replace('/ws/chat', '/ws/voice')
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.hostname
    const port = '8000'
    return `${protocol}//${host}:${port}/ws/voice`
  }

  function connect(cbs: VoiceWsCallbacks = {}) {
    callbacks = cbs
    const token = getAccessToken()
    if (!token) {
      console.warn('[useVoiceWs] No access token, cannot connect')
      return
    }

    const url = `${buildUrl()}?token=${encodeURIComponent(token)}`
    ws = new WebSocket(url)
    ws.binaryType = 'arraybuffer'

    ws.onopen = () => {
      isConnected.value = true
      reconnectAttempts = 0
      console.log('[useVoiceWs] Connected')
    }

    ws.onmessage = (event: MessageEvent) => {
      // Handle binary (TTS audio) frames
      if (event.data instanceof ArrayBuffer) {
        callbacks.onAudioChunk?.(event.data)
        return
      }

      // Handle text (JSON) messages
      try {
        const data = JSON.parse(event.data as string)
        switch (data.type) {
          case 'asr.partial':
            callbacks.onAsrPartial?.(data.text)
            break
          case 'asr.final':
            callbacks.onAsrFinal?.(data.text)
            break
          case 'token':
            callbacks.onChatToken?.(data.text)
            break
          case 'action':
            callbacks.onChatAction?.(data.tag)
            break
          case 'chat.done':
            callbacks.onChatDone?.(data)
            break
          case 'error':
            callbacks.onError?.(data.code, data.detail)
            break
          default:
            console.log('[useVoiceWs] Unknown message type:', data.type)
        }
      } catch {
        console.warn('[useVoiceWs] Failed to parse message')
      }
    }

    ws.onclose = (event) => {
      isConnected.value = false
      isRecording.value = false
      console.log('[useVoiceWs] Disconnected:', event.code, event.reason)

      // Auto-reconnect with exponential backoff
      if (reconnectAttempts < maxReconnectAttempts) {
        const delay = reconnectBaseDelay * Math.pow(2, reconnectAttempts)
        reconnectAttempts++
        console.log(`[useVoiceWs] Reconnecting in ${delay}ms (attempt ${reconnectAttempts})`)
        reconnectTimer = setTimeout(() => connect(callbacks), delay)
      }
    }

    ws.onerror = (event) => {
      console.error('[useVoiceWs] Error:', event)
    }
  }

  function sendVoiceStart(lang = 'zh') {
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    ws.send(JSON.stringify({ type: 'voice.start', lang }))
    isRecording.value = true
  }

  function sendVoiceEnd() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    ws.send(JSON.stringify({ type: 'voice.end' }))
    isRecording.value = false
  }

  function sendBargeIn() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    ws.send(JSON.stringify({ type: 'voice.barge_in' }))
  }

  function sendAudioChunk(chunk: ArrayBuffer | Blob) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    if (chunk instanceof Blob) {
      chunk.arrayBuffer().then((buf) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(buf)
        }
      })
    } else {
      ws.send(chunk)
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    reconnectAttempts = maxReconnectAttempts // Prevent reconnect
    if (ws) {
      ws.close(1000, 'client-disconnect')
      ws = null
    }
    isConnected.value = false
    isRecording.value = false
  }

  return {
    isConnected,
    isRecording,
    connect,
    disconnect,
    sendVoiceStart,
    sendVoiceEnd,
    sendBargeIn,
    sendAudioChunk,
  }
}
