<script setup lang="tsx">
import { NDataTable, NButton, NSpace } from 'naive-ui';
import { GlassCard } from '@eira/ui-shared';

const columns = [
  { title: 'Name', key: 'name' },
  { title: 'Description', key: 'description' },
  { title: 'Default', key: 'isDefault' },
  {
    title: 'Actions',
    key: 'actions',
    render(row: any) {
      return (
        <NSpace>
          <NButton size="small">Edit</NButton>
          <NButton size="small" type="error" ghost>Delete</NButton>
        </NSpace>
      );
    }
  }
];

const data = [
  { key: 1, name: 'Eira Default', description: 'The official digital guide persona.', isDefault: 'Yes' },
  { key: 2, name: 'Historical Scholar', description: 'Expert on local history.', isDefault: 'No' }
];
</script>

<template>
  <div class="page-container">
    <div class="header-actions">
      <h2>Persona Management</h2>
      <NButton type="primary">Create New Persona</NButton>
    </div>

    <GlassCard class="table-card">
      <NDataTable :columns="columns" :data="data" :bordered="false" />
    </GlassCard>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 1200px;
  margin: 0 auto;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-actions h2 {
  margin: 0;
}

.table-card {
  padding: 16px;
}
</style>
