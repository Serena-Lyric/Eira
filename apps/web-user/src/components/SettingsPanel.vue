<!--
  @deprecated — 此组件当前未被引用。Chat.vue 已将设置面板 UI 内联实现。
  保留此文件供未来组件化重构时参考。
-->
<script setup lang="ts">
import { GlassModal, GlassButton } from '@eira/ui-shared';

defineProps<{ open: boolean }>();
defineEmits<{ close: [] }>();
</script>

<template>
  <GlassModal :open="open" @close="$emit('close')">
    <div class="settings-content">
      <h3>Settings</h3>

      <div class="setting-group">
        <label>Voice TTS</label>
        <input type="checkbox" checked />
      </div>

      <div class="setting-group">
        <label>Camera Window</label>
        <input type="checkbox" checked />
      </div>

      <div class="actions">
        <GlassButton variant="primary" @click="$emit('close')">Done</GlassButton>
      </div>
    </div>
  </GlassModal>
</template>

<style scoped>
.settings-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

h3 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.setting-group {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}
</style>
