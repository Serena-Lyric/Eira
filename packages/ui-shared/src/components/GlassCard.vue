<script setup lang="ts">
</script>

<template>
  <div class="glass-card">
    <slot />
  </div>
</template>

<style scoped>
.glass-card {
  padding: 24px;
  border-radius: var(--radius-card);
  border: 1px solid var(--glass-border);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  box-shadow: var(--shadow-soft);
  color: var(--color-text-primary);
  transition: all var(--ease-soft) 0.3s;
}
</style>
