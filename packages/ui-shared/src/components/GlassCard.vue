<script setup lang="ts">
</script>
<template>
  <div class="g-card">
    <slot />
  </div>
</template>
<style scoped>
.g-card {
  padding: 24px;
  border-radius: var(--eira-radius-lg);
  border: 1px solid var(--eira-glass-border);
  background: var(--eira-glass-bg);
  backdrop-filter: blur(var(--eira-glass-blur));
  box-shadow: var(--eira-shadow-soft);
}
</style>
