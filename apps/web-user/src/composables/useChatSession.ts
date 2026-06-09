import { ref, computed } from 'vue';
import { useWebSocket } from '@eira/ui-shared';
import type { WebSocketHandle } from '@eira/ui-shared';
import { useActionParser } from './useActionParser';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  ts: number;
}

export function useChatSession() {
  // Build WS URL from current location or env var
  const buildWsUrl = () => {
    if (typeof import.meta.env !== 'undefined' && import.meta.env.VITE_WS_URL) {
      return import.meta.env.VITE_WS_URL;
    }
    // Auto-derive from current page URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const port = '8000'; // backend port
    return `${protocol}//${host}:${port}/ws/chat`;
  };

  const messages = ref<ChatMessage[]>([]);
  const currentResponse = ref('');
  const phase = ref<'idle' | 'thinking' | 'streaming' | 'done' | 'error'>('idle');
  const sessionId = ref<string>('');
  const isConnected = ref(false);
  const actionParser = useActionParser();

  let ws: WebSocketHandle | null = null;
  let removeListener: (() => void) | null = null;

  function getAccessToken(): string {
    // Read from auth store localStorage (key: eira:at)
    return localStorage.getItem('eira:at') || '';
  }

  function connect() {
    const token = getAccessToken();
    if (!token) {
      console.warn('[useChatSession] No access token — redirecting to login');
      window.location.href = '/login';
      return;
    }

    const wsUrl = `${buildWsUrl()}?token=${encodeURIComponent(token)}`;
    ws = useWebSocket(wsUrl);
    ws.connect();

    // Poll for connection (clean up after connected or timeout)
    let attempts = 0;
    const maxAttempts = 50; // 10 seconds at 200ms intervals
    const checkInterval = setInterval(() => {
      attempts++;
      if (ws && ws.isConnected.value) {
        isConnected.value = true;
        clearInterval(checkInterval);
      } else if (attempts >= maxAttempts) {
        clearInterval(checkInterval);
        console.warn('[useChatSession] WebSocket connection timeout');
      }
    }, 200);

    removeListener = ws.addListener((event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case 'state':
            if (data.phase === 'thinking') {
              phase.value = 'thinking';
              currentResponse.value = '';
            } else if (data.phase === 'streaming') {
              phase.value = 'streaming';
            } else if (data.phase === 'done') {
              phase.value = 'done';
              // Finalize the assistant message
              if (currentResponse.value) {
                messages.value.push({
                  role: 'assistant',
                  content: currentResponse.value,
                  ts: Date.now(),
                });
                // Clear after a delay for UI transition
                setTimeout(() => {
                  currentResponse.value = '';
                  phase.value = 'idle';
                }, 500);
              }
            } else if (data.phase === 'error') {
              phase.value = 'error';
            }
            break;

          case 'token':
            if (data.text) {
              currentResponse.value += data.text;
            }
            break;

          case 'action':
            if (data.tag) {
              actionParser.parseAndTrigger(data.tag);
            }
            break;

          case 'done':
            console.log('[useChatSession] Turn complete:', data);
            break;

          case 'quick_questions':
            // 后端推送快捷问题列表
            if (data.questions && Array.isArray(data.questions)) {
              window.dispatchEvent(
                new CustomEvent('eira:quick-questions', { detail: data.questions })
              );
            }
            break;

          case 'error':
            console.error('[useChatSession] Server error:', data.code, data.detail);
            phase.value = 'error';
            break;
        }
      } catch (e) {
        console.error('[useChatSession] Failed to parse WS message:', e);
      }
    });
  }

  function createSession() {
    sessionId.value = `sess-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    return sessionId.value;
  }

  function sendText(text: string) {
    if (!ws || !ws.isConnected.value) {
      console.warn('[useChatSession] WS not connected — reconnecting...');
      connect();
      // Queue the message for after connection
      const waitAndSend = setInterval(() => {
        if (ws && ws.isConnected.value) {
          clearInterval(waitAndSend);
          doSend(text);
        }
      }, 100);
      return;
    }

    doSend(text);
  }

  function doSend(text: string) {
    if (!sessionId.value) {
      createSession();
    }

    // Add user message immediately
    messages.value.push({
      role: 'user',
      content: text,
      ts: Date.now(),
    });

    phase.value = 'thinking';
    currentResponse.value = '';

    ws!.send(JSON.stringify({
      type: 'user_text',
      session_id: sessionId.value,
      text: text,
      ts: Date.now(),
    }));
  }

  function disconnect() {
    if (removeListener) {
      removeListener();
      removeListener = null;
    }
    if (ws) {
      ws.disconnect();
      ws = null;
    }
    isConnected.value = false;
  }

  return {
    messages,
    currentResponse,
    phase,
    sessionId,
    isConnected,
    connect,
    createSession,
    sendText,
    disconnect,
  };
}
