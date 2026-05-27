<script setup lang="ts">
defineProps<{ modelValue: string; placeholder?: string; type?: string }>()
defineEmits<{ "update:modelValue": [string] }>()
</script>

<template>
  <input
    class="glass-input"
    :type="type || 'text'"
    :placeholder="placeholder"
    :value="modelValue"
    @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
  />
</template>

<style scoped>
.glass-input {
  width: 100%;
  padding: 12px 16px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--glass-border);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  color: var(--color-text-primary);
  outline: none;
  box-sizing: border-box;
  font-family: inherit;
  font-size: 15px;
  pointer-events: auto;
  transition: box-shadow var(--ease-soft) 0.3s;
}
.glass-input:focus {
  box-shadow: var(--shadow-soft);
  border-color: rgba(255, 255, 255, 0.5);
}
.glass-input::placeholder {
  color: rgba(120, 120, 120, 0.7);
}
[data-theme="dark"] .glass-input::placeholder {
  color: rgba(200, 200, 200, 0.5);
}
</style>
