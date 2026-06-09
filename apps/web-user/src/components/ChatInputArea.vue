<!--
  @deprecated — 此组件当前未被引用。Chat.vue 已将输入栏 UI 内联实现。
  保留此文件供未来组件化重构时参考。
-->
<script setup lang="ts">
import { ref } from 'vue';

const emit = defineEmits<{ send: [string] }>();
const inputText = ref('');

function handleSubmit() {
  if (inputText.value.trim()) {
    emit('send', inputText.value);
    inputText.value = '';
  }
}
</script>

<template>
  <div class="chat-input-area">
    <div class="input-container glass-container">
      <button class="icon-btn left-btn mic-btn">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
          <line x1="12" y1="19" x2="12" y2="22"></line>
        </svg>
      </button>

      <input
        type="text"
        v-model="inputText"
        placeholder="Type a message..."
        @keyup.enter="handleSubmit"
      />

      <div class="right-actions">
        <button class="icon-btn plus-btn">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
        </button>
        <button class="icon-btn send-btn" @click="handleSubmit" :disabled="!inputText.trim()">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-input-area {
  width: 100%;
}

.glass-container {
  display: flex;
  align-items: center;
  border-radius: var(--radius-pill);
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  box-shadow: var(--shadow-soft);
  padding: 8px 12px;
}

[data-theme="dark"] .glass-container {
  background: rgba(30, 35, 45, 0.6);
}

input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--color-text-primary);
  font-size: 16px;
  padding: 8px 12px;
}

input::placeholder {
  color: rgba(150, 150, 150, 0.7);
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
  outline: none;
}

.mic-btn {
  background: transparent;
  color: var(--color-text-primary);
  opacity: 0.8;
}

.mic-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  opacity: 1;
}

.right-actions {
  display: flex;
  gap: 8px;
  margin-left: 8px;
}

.plus-btn {
  background: rgba(255, 255, 255, 0.2);
  color: var(--color-text-primary);
  border: 1px solid var(--glass-border);
}

.send-btn {
  background: var(--color-accent);
  color: white;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.icon-btn:not(:disabled):active {
  transform: scale(0.95);
}
</style>
