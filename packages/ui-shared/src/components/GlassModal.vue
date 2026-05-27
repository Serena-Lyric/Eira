<script setup lang="ts">
defineProps<{ open: boolean }>()
defineEmits<{ close: [] }>()
</script>

<template>
  <div v-if="open" class="glass-modal-overlay" @click.self="$emit('close')">
    <div class="glass-modal">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.glass-modal-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  z-index: 1000;
  pointer-events: auto;
}
.glass-modal {
  padding: 28px;
  border-radius: var(--radius-card);
  border: 1px solid var(--glass-border);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  box-shadow: var(--shadow-soft);
  min-width: 320px;
  color: var(--color-text-primary);
  animation: modal-enter var(--ease-soft) 0.3s;
}

@keyframes modal-enter {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(10px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
</style>
