<script setup lang="tsx">
import { NDataTable, NButton, NSpace, NUpload, NTag } from 'naive-ui';
import { GlassCard } from '@eira/ui-shared';

const columns = [
  { title: 'Document Name', key: 'name' },
  { title: 'Size', key: 'size' },
  {
    title: 'Status',
    key: 'status',
    render(row: any) {
      if (row.status === 'indexed') return <NTag type="success">Indexed</NTag>;
      if (row.status === 'pending') return <NTag type="warning">Pending</NTag>;
      return <NTag type="info">Processing ({row.progress}%)</NTag>;
    }
  },
  {
    title: 'Actions',
    key: 'actions',
    render(row: any) {
      return (
        <NSpace>
          <NButton size="small" type="primary" ghost disabled={row.status === 'processing'}>Vectorize</NButton>
          <NButton size="small">Preview RAG</NButton>
          <NButton size="small" type="error" ghost>Delete</NButton>
        </NSpace>
      );
    }
  }
];

const data = [
  { key: 1, name: '景区导览手册_2026.pdf', size: '2.4 MB', status: 'indexed' },
  { key: 2, name: '票务说明.docx', size: '150 KB', status: 'processing', progress: 45 },
  { key: 3, name: '周边美食推荐.txt', size: '12 KB', status: 'pending' },
];
</script>

<template>
  <div class="page-container">
    <div class="header-actions">
      <h2>Knowledge Base & RAG</h2>
    </div>

    <NSpace vertical :size="24">
      <GlassCard>
        <NUpload
          multiple
          directory-dnd
          action="/api/v1/knowledge/upload"
          :max="5"
        >
          <div class="upload-dragger">
            <p>Click or drag files here to upload.</p>
            <p style="font-size: 13px; color: #888;">Supports PDF, DOCX, TXT, MD.</p>
          </div>
        </NUpload>
      </GlassCard>

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

.upload-dragger {
  border: 1px dashed var(--color-accent);
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  background: rgba(106, 162, 255, 0.05);
  cursor: pointer;
  transition: background 0.3s;
}

.upload-dragger:hover {
  background: rgba(106, 162, 255, 0.1);
}

.table-card {
  padding: 16px;
}
</style>
