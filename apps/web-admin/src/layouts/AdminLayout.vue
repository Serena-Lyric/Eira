<script setup lang="ts">
import { NConfigProvider, NGlobalStyle } from 'naive-ui';
import { RouterView } from 'vue-router';
</script>

<template>
  <NConfigProvider>
    <NGlobalStyle />
    <RouterView />
  </NConfigProvider>
</template>

<style>
body {
  margin: 0;
  padding: 0;
  overflow: hidden;
}
</style>
