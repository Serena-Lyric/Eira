import { ref } from 'vue';

export function useActionParser() {
  /**
   * Map action tags → Live2D motion groups.
   *
   * Available motion groups (model-dependent):
   *   hiyori_pro_zh: Idle, Flick, FlickDown, FlickUp, Tap, Tap@Body, Flick@Body
   *   mao_pro_zh:    Idle, "" (default group with mtn_02-04, special_01-02)
   *
   * The Live2D controller will try the primary group, then fall back
   * through Tap@Body → Tap → Idle if the group isn't available.
   */
  const motionMap: Record<string, string> = {
    '[wave]': 'Flick',
    '[happy]': 'Tap',
    '[nod]': 'FlickDown',
    '[greet]': 'FlickUp',
    '[tap]': 'Tap@Body',
    '[idle]': 'Idle',
    '[surprised]': 'FlickUp',
    '[sad]': 'FlickDown',
    '[think]': 'Tap@Body',
    '[angry]': 'Flick',
    '[shy]': 'Flick@Body',
    '[wink]': 'Tap',
    '[confused]': 'FlickDown',
  };

  /**
   * Parse an action tag or motion group name and trigger the Live2D motion.
   *
   * Accepts both forms:
   *   - Raw tags: 'wave', 'nod', 'happy', '[wave]', '[nod]', '[happy]'
   *   - Motion group names: 'Tap@Body', 'Idle', 'Flick' (passed through)
   */
  function parseAndTrigger(actionTag: string) {
    let motionGroup: string | null = null;

    // Normalize: strip brackets if present
    const normalized = actionTag.replace(/[\[\]]/g, '');

    // Known motion groups (used directly)
    const knownGroups = new Set([
      'Idle', 'Flick', 'FlickDown', 'FlickUp', 'Tap', 'Tap@Body', 'Flick@Body',
    ]);

    if (knownGroups.has(actionTag)) {
      motionGroup = actionTag;
    } else if (knownGroups.has(normalized)) {
      motionGroup = normalized;
    } else {
      // Try tag lookup: 'wave' → '[wave]' → 'Flick'
      const withBrackets = `[${normalized}]`;
      motionGroup = motionMap[withBrackets] || motionMap[actionTag] || null;
    }

    if (motionGroup) {
      const event = new CustomEvent('live2d:motion', {
        detail: { group: motionGroup }
      });
      window.dispatchEvent(event);
    }
  }

  /**
   * Strip action tags from display text.
   * Removes all bracket-delimited tags: [wave], [nod], etc.
   */
  function stripTags(text: string): string {
    return text.replace(/\[.*?\]/g, '').trim();
  }

  return {
    parseAndTrigger,
    stripTags,
  };
}
