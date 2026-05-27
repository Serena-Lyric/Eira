<script setup lang="ts">
defineProps<{ open: boolean }>()
defineEmits<{ close: [] }>()
</script>
<template>
  <div v-if="open" class="g-modal-overlay" @click.self="$emit('close')">
    <div class="g-modal">
      <slot />
    </div>
  </div>
</template>
<style scoped>
.g-modal-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(4px);
  z-index: 1000;
}
.g-modal {
  padding: 28px;
  border-radius: var(--eira-radius-lg);
  border: 1px solid var(--eira-glass-border);
  background: var(--eira-glass-bg);
  backdrop-filter: blur(var(--eira-glass-blur));
  box-shadow: var(--eira-shadow-soft);
  min-width: 320px;
}
</style>
