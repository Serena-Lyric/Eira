<!--
  @deprecated — 此组件当前未被引用。Chat.vue 已将快捷问题 UI 内联实现。
  保留此文件供未来组件化重构时参考。
-->
<script setup lang="ts">
import { GlassButton } from '@eira/ui-shared';

defineProps<{ questions: string[] }>();
defineEmits<{ select: [string] }>();
</script>

<template>
  <div class="quick-questions">
    <GlassButton
      v-for="(q, index) in questions"
      :key="index"
      variant="pill"
      class="qq-btn"
      @click="$emit('select', q)"
    >
      {{ q }}
    </GlassButton>
  </div>
</template>

<style scoped>
.quick-questions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.qq-btn {
  justify-content: flex-start;
  text-align: left;
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.25);
  font-size: 14px;
}

[data-theme="dark"] .qq-btn {
  background: rgba(40, 45, 60, 0.45);
}
</style>
