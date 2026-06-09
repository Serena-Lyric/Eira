import { ref, type Ref } from 'vue';

// ── Glass UI stubs (replaced by local implementations in each app) ──

import { defineComponent } from 'vue';

export const GlassCard = defineComponent({ render() { return null; } });
export const GlassButton = defineComponent({ render() { return null; } });
export const GlassModal = defineComponent({ render() { return null; } });
export const GlassInput = defineComponent({ render() { return null; } });

// ── useWebSocket composable ──────────────────────────────────────

export interface WebSocketHandle {
  isConnected: Ref<boolean>;
  connect: () => void;
  disconnect: () => void;
  send: (data: string | ArrayBuffer) => void;
  addListener: (cb: (event: MessageEvent) => void) => () => void;
}

export function useWebSocket(url: string): WebSocketHandle {
  const isConnected = ref(false);
  let ws: WebSocket | null = null;
  const listeners: Array<(event: MessageEvent) => void> = [];
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let intentionalClose = false;

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    intentionalClose = false;

    try {
      ws = new WebSocket(url);
    } catch (e) {
      console.error('[useWebSocket] Failed to create WebSocket:', e);
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      isConnected.value = true;
    };

    ws.onmessage = (event: MessageEvent) => {
      for (const cb of listeners) {
        try {
          cb(event);
        } catch (e) {
          console.error('[useWebSocket] Listener error:', e);
        }
      }
    };

    ws.onclose = (event) => {
      isConnected.value = false;
      ws = null;
      if (!intentionalClose) {
        console.log('[useWebSocket] Connection closed, reconnecting in 3s...');
        scheduleReconnect();
      }
    };

    ws.onerror = (event) => {
      console.error('[useWebSocket] Connection error:', event);
    };
  }

  function disconnect() {
    intentionalClose = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (ws) {
      ws.close();
      ws = null;
    }
    isConnected.value = false;
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, 3000);
  }

  function send(data: string | ArrayBuffer) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(data);
    } else {
      console.warn('[useWebSocket] Cannot send — not connected');
    }
  }

  function addListener(cb: (event: MessageEvent) => void): () => void {
    listeners.push(cb);
    return () => {
      const idx = listeners.indexOf(cb);
      if (idx !== -1) listeners.splice(idx, 1);
    };
  }

  return {
    isConnected,
    connect,
    disconnect,
    send,
    addListener,
  };
}
