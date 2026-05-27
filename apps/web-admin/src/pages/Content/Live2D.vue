<script setup lang="tsx">
import { NDataTable, NButton, NSpace, NUpload } from 'naive-ui';
import { GlassCard } from '@eira/ui-shared';

const columns = [
  { title: 'Asset Name', key: 'name' },
  { title: 'Type', key: 'type' },
  { title: 'Default', key: 'isDefault' },
  {
    title: 'Actions',
    key: 'actions',
    render(row: any) {
      return (
        <NSpace>
          <NButton size="small" type="primary" ghost>Set Default</NButton>
          <NButton size="small" type="error" ghost>Delete</NButton>
        </NSpace>
      );
    }
  }
];

const data = [
  { key: 1, name: 'Hiyori v1', type: 'Live2D Model', isDefault: 'Yes' },
  { key: 2, name: 'Natori', type: 'Live2D Model', isDefault: 'No' },
  { key: 3, name: 'Night Street', type: 'Background (Image)', isDefault: 'Yes' }
];
</script>

<template>
  <div class="page-container">
    <div class="header-actions">
      <h2>Assets (Live2D Models & Backgrounds)</h2>
    </div>

    <NSpace vertical :size="24">
      <NSpace>
        <GlassCard style="flex: 1;">
          <h3>Upload Live2D Model (.zip)</h3>
          <NUpload action="/api/v1/assets/live2d">
            <NButton>Select ZIP</NButton>
          </NUpload>
        </GlassCard>

        <GlassCard style="flex: 1;">
          <h3>Upload Background (Image/Video)</h3>
          <NUpload action="/api/v1/assets/background">
            <NButton>Select File</NButton>
          </NUpload>
        </GlassCard>
      </NSpace>

      <GlassCard class="table-card">
        <NDataTable :columns="columns" :data="data" :bordered="false" />
      </GlassCard>
    </NSpace>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 1200px;
  margin: 0 auto;
}

.header-actions {
  margin-bottom: 24px;
}

h3 {
  margin-top: 0;
  margin-bottom: 16px;
  font-size: 16px;
}

.table-card {
  padding: 16px;
}
</style>
