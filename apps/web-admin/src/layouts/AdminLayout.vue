<script setup lang="ts">
import { NLayout, NLayoutHeader, NLayoutContent, NMenu, NConfigProvider, NGlobalStyle } from 'naive-ui';
import { h, ref } from 'vue';
import { RouterLink, RouterView } from 'vue-router';

// Nav Options
const menuOptions = [
  {
    label: () => h(RouterLink, { to: '/dashboard' }, { default: () => 'Dashboard' }),
    key: 'dashboard'
  },
  {
    label: () => h(RouterLink, { to: '/interaction' }, { default: () => 'Interaction' }),
    key: 'interaction'
  },
  {
    label: 'Content',
    key: 'content',
    children: [
      {
        label: () => h(RouterLink, { to: '/content/personas' }, { default: () => 'Personas' }),
        key: 'personas'
      },
      {
        label: () => h(RouterLink, { to: '/content/knowledge' }, { default: () => 'Knowledge Base' }),
        key: 'knowledge'
      },
      {
        label: () => h(RouterLink, { to: '/content/live2d' }, { default: () => 'Assets (Live2D/BG)' }),
        key: 'assets'
      }
    ]
  },
  {
    label: () => h(RouterLink, { to: '/system' }, { default: () => 'System Settings' }),
    key: 'system'
  }
];

const activeKey = ref<string>('dashboard');
</script>

<template>
  <NConfigProvider>
    <NGlobalStyle />
    <NLayout position="absolute">
      <!-- 72px Top Navigation -->
      <NLayoutHeader bordered class="admin-header">
        <div class="logo">Eira Admin</div>
        <div class="nav-menu">
          <NMenu mode="horizontal" :options="menuOptions" v-model:value="activeKey" />
        </div>
        <div class="user-info">
          Admin
        </div>
      </NLayoutHeader>

      <NLayoutContent class="admin-content" content-style="padding: 24px;">
        <RouterView />
      </NLayoutContent>
    </NLayout>
  </NConfigProvider>
</template>

<style scoped>
.admin-header {
  height: 72px;
  display: flex;
  align-items: center;
  padding: 0 32px;
  justify-content: space-between;
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  z-index: 100;
}

.logo {
  font-size: 20px;
  font-weight: bold;
  color: var(--color-accent);
}

.nav-menu {
  flex: 1;
  display: flex;
  justify-content: center;
}

.admin-content {
  top: 72px;
  background: #f4f7fb;
  min-height: calc(100vh - 72px);
}
</style>
