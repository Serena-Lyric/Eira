<script setup lang="ts">
defineProps<{ variant?: "primary" | "ghost" | "pill"; disabled?: boolean }>()
defineEmits<{ click: [Event] }>()
</script>

<template>
  <button
    class="glass-btn"
    :class="variant"
    :disabled="disabled"
    @click="$emit('click', $event)"
  >
    <slot />
  </button>
</template>

<style scoped>
.glass-btn {
  padding: 10px 18px;
  border-radius: var(--radius-card);
  border: 1px solid var(--glass-border);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  color: var(--color-text-primary);
  cursor: pointer;
  pointer-events: auto;
  transition: transform 0.15s ease, box-shadow 0.2s ease;
  font-family: inherit;
  font-size: 14px;
  outline: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.glass-btn:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-soft);
}
.glass-btn:active {
  transform: translateY(1px);
}
.glass-btn.primary {
  background: var(--color-accent);
  color: #fff;
  border-color: transparent;
}
.glass-btn.pill {
  border-radius: var(--radius-pill);
}
.glass-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}
</style>
