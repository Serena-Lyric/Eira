import { ref, onUnmounted } from 'vue';

export function useWebSocket(url: string, protocols?: string | string[]) {
  const ws = ref<WebSocket | null>(null);
  const isConnected = ref(false);
  const reconnectAttempts = ref(0);
  const maxReconnectAttempts = 5;
  const listeners = new Set<(ev: MessageEvent) => void>();

  function connect() {
    if (ws.value?.readyState === WebSocket.OPEN) return;

    // Append access token if available
    const token = localStorage.getItem('eira_access_token');
    const wsUrl = new URL(url);
    if (token) {
      wsUrl.searchParams.append('token', token);
    }

    ws.value = new WebSocket(wsUrl.toString(), protocols);

    ws.value.onopen = () => {
      isConnected.value = true;
      reconnectAttempts.value = 0;
    };

    ws.value.onmessage = (event) => {
      listeners.forEach(fn => fn(event));
    };

    ws.value.onclose = () => {
      isConnected.value = false;
      if (reconnectAttempts.value < maxReconnectAttempts) {
        const timeout = Math.min(1000 * Math.pow(2, reconnectAttempts.value), 10000);
        setTimeout(() => {
          reconnectAttempts.value++;
          connect();
        }, timeout);
      }
    };

    ws.value.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  function send(data: string | ArrayBuffer | Blob) {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(data);
    } else {
      console.warn('WebSocket is not connected. Message dropped.');
    }
  }

  function addListener(fn: (ev: MessageEvent) => void) {
    listeners.add(fn);
  }

  function removeListener(fn: (ev: MessageEvent) => void) {
    listeners.delete(fn);
  }

  onUnmounted(() => {
    if (ws.value) {
      ws.value.close();
    }
    listeners.clear();
  });

  return {
    ws,
    isConnected,
    connect,
    send,
    addListener,
    removeListener
  };
}
