<script setup lang="ts">
defineProps<{ modelValue: string; placeholder?: string; type?: string }>()
defineEmits<{ "update:modelValue": [string] }>()
</script>
<template>
  <input
    class="g-input"
    :type="type || 'text'"
    :placeholder="placeholder"
    :value="modelValue"
    @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
  />
</template>
<style scoped>
.g-input {
  width: 100%;
  padding: 10px 14px;
  border-radius: var(--eira-radius-sm);
  border: 1px solid var(--eira-glass-border);
  background: var(--eira-glass-bg);
  backdrop-filter: blur(var(--eira-glass-blur));
  color: var(--eira-text-primary);
  outline: none;
  box-sizing: border-box;
}
.g-input::placeholder {
  color: var(--eira-text-muted);
}
</style>
