<script setup lang="ts">
import { NConfigProvider, NGlobalStyle, NMessageProvider } from 'naive-ui';
import { RouterView } from 'vue-router';
</script>

<template>
  <NConfigProvider>
    <NGlobalStyle />
    <NMessageProvider>
      <RouterView />
    </NMessageProvider>
  </NConfigProvider>
</template>

<style>
body {
  margin: 0;
  padding: 0;
  overflow: hidden;
}
</style>
