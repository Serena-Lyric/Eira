<script setup lang="ts">
defineProps<{ variant?: "primary" | "ghost"; disabled?: boolean }>()
defineEmits<{ click: [Event] }>()
</script>
<template>
  <button
    class="g-btn"
    :class="variant"
    :disabled="disabled"
    @click="$emit('click', $event)"
  >
    <slot />
  </button>
</template>
<style scoped>
.g-btn {
  padding: 10px 18px;
  border-radius: var(--eira-radius-md);
  border: 1px solid var(--eira-glass-border);
  background: var(--eira-glass-bg);
  backdrop-filter: blur(var(--eira-glass-blur));
  color: var(--eira-text-primary);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.2s ease;
}
.g-btn:hover {
  transform: translateY(-1px);
  box-shadow: var(--eira-shadow-soft);
}
.g-btn.primary {
  background: var(--eira-accent);
  color: #fff;
  border-color: transparent;
}
.g-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
