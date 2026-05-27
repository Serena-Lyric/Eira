<script setup lang="ts">
import { ref } from 'vue';

const props = defineProps<{
  text: string;
  isThinking: boolean;
}>();
</script>

<template>
  <div class="speech-bubble" v-if="text || isThinking">
    <div class="content" v-if="!isThinking">
      {{ text }}
    </div>
    <div class="thinking-dots" v-else>
      <span>.</span><span>.</span><span>.</span>
    </div>
  </div>
</template>

<style scoped>
.speech-bubble {
  max-width: 80%;
  padding: 16px 24px;
  border-radius: var(--radius-card);
  background: rgba(255, 255, 255, 0.45);
  border: 1px solid var(--glass-border);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  box-shadow: var(--shadow-soft);
  color: var(--color-text-primary);
  font-size: 16px;
  line-height: 1.5;
  text-align: center;
  transition: opacity 0.3s;
}

[data-theme="dark"] .speech-bubble {
  background: rgba(20, 20, 25, 0.45);
}

.thinking-dots {
  display: flex;
  gap: 4px;
  justify-content: center;
  font-size: 24px;
  line-height: 1;
}

.thinking-dots span {
  animation: bounce 1.4s infinite ease-in-out both;
}

.thinking-dots span:nth-child(1) { animation-delay: -0.32s; }
.thinking-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
</style>
