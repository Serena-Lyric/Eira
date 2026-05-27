<script setup lang="ts">
import { ref, onMounted } from 'vue';

const props = defineProps<{
  containerRef: HTMLElement | null;
}>();
</script>

<template>
  <div class="canvas-container" ref="containerRef"></div>
</template>

<style scoped>
.canvas-container {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.canvas-container :deep(canvas) {
  display: block;
  width: 100% !important;
  height: 100% !important;
  object-fit: contain;
}
</style>
