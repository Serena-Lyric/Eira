import { ref } from 'vue';
import { useWebSocket } from '@eira/ui-shared';
import { useActionParser } from './useActionParser';

export function useChatSession() {
  const wsUrl = typeof import.meta.env !== 'undefined' && import.meta.env.VITE_WS_URL
    ? import.meta.env.VITE_WS_URL
    : 'ws://localhost:8000/ws/chat';

  const ws = useWebSocket(wsUrl);
  const currentText = ref('');
  const isThinking = ref(false);
  const actionParser = useActionParser();

  // Initialize WS listeners
  ws.addListener((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'agent.thinking':
          isThinking.value = true;
          currentText.value = '';
          break;

        case 'agent.text.delta':
          isThinking.value = false;
          currentText.value += data.payload.text;
          break;

        case 'agent.action':
          actionParser.parseAndTrigger(data.payload.action);
          break;

        case 'agent.text.done':
          // Optionally hide bubble after a few seconds
          setTimeout(() => {
            currentText.value = '';
          }, 10000);
          break;
      }
    } catch (e) {
      console.error('Failed to parse WS message:', e);
    }
  });

  // Connect on setup
  ws.connect();

  function sendText(text: string) {
    if (!ws.isConnected.value) return;

    ws.send(JSON.stringify({
      type: 'user.text',
      payload: { text }
    }));
  }

  function sendAudioChunk(chunk: ArrayBuffer) {
    if (!ws.isConnected.value) return;

    ws.send(chunk); // Send raw binary for audio
  }

  return {
    currentText,
    isThinking,
    sendText,
    sendAudioChunk
  };
}
