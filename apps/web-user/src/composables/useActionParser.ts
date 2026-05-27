import { ref } from 'vue';

export function useActionParser() {
  // Map string tags to Live2D motion groups (e.g. from Hiyori's motion data)
  const motionMap: Record<string, string> = {
    '[wave]': 'TapBody',
    '[happy]': 'TapBody',
    '[nod]': 'Idle',
  };

  function parseAndTrigger(actionTag: string) {
    const motionGroup = motionMap[actionTag];
    if (motionGroup) {
      // In a real app we would fire an event here that the Live2DController listens to,
      // or export a global event bus.
      // For now, we dispatch a custom DOM event so the UI component can catch it.
      const event = new CustomEvent('live2d:motion', {
        detail: { group: motionGroup }
      });
      window.dispatchEvent(event);
    }
  }

  // Optional: Function to strip tags out of raw text stream if the backend doesn't do it cleanly
  function stripTags(text: string) {
    return text.replace(/\[.*?\]/g, '');
  }

  return {
    parseAndTrigger,
    stripTags
  };
}
