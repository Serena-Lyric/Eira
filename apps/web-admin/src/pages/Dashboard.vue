<script setup lang="ts">
import { NGrid, NGridItem, NCard, NStatistic } from 'naive-ui';
import { GlassCard, GlassButton } from '@eira/ui-shared';
// Placeholder for VueEcharts imports later
</script>

<template>
  <div class="dashboard">
    <!-- 3-Column Layout: Left 26%, Middle 38%, Right 36% -->
    <NGrid :x-gap="24" :cols="100">

      <!-- Left Column (26%) -->
      <NGridItem :span="26">
        <GlassCard class="column-card">
          <h2 class="title">Active Persona</h2>
          <div class="persona-info">
            <div class="avatar-placeholder">Hiyori</div>
            <h3>Eira Default</h3>
            <p>Your AI Guide</p>
          </div>

          <div class="config-tabs">
            <GlassButton variant="primary" style="width: 100%; margin-bottom: 12px;">Edit Appearance</GlassButton>
            <GlassButton variant="ghost" style="width: 100%;">Voice Settings</GlassButton>
          </div>
        </GlassCard>
      </NGridItem>

      <!-- Middle Column (38%) -->
      <NGridItem :span="38">
        <GlassCard class="column-card live2d-preview-card">
          <div class="preview-area">
            <!-- Render Live2D preview here -->
            <p style="color: #888;">Live2D Preview Area</p>
          </div>
          <div class="action-bar">
            <GlassButton variant="pill">Wave</GlassButton>
            <GlassButton variant="pill">Smile</GlassButton>
            <GlassButton variant="pill">Test Voice</GlassButton>
          </div>
        </GlassCard>
      </NGridItem>

      <!-- Right Column (36%) -->
      <NGridItem :span="36">
        <div class="analytics-stack">
          <!-- Metrics Row -->
          <NGrid :x-gap="12" :cols="2">
            <NGridItem>
              <GlassCard>
                <NStatistic label="Total Interactions" value="1,248" />
              </GlassCard>
            </NGridItem>
            <NGridItem>
              <GlassCard>
                <NStatistic label="Satisfaction Rate" value="98%" />
              </GlassCard>
            </NGridItem>
          </NGrid>

          <!-- Chart Area -->
          <GlassCard style="flex: 1;">
            <h3 style="margin-top: 0;">Interaction Trends</h3>
            <div class="chart-placeholder">
              [ ECharts Line Chart Placeholder ]
            </div>
          </GlassCard>

          <GlassCard style="height: 200px;">
            <h3 style="margin-top: 0;">Top Questions (Word Cloud)</h3>
            <div class="chart-placeholder">
              [ ECharts WordCloud Placeholder ]
            </div>
          </GlassCard>
        </div>
      </NGridItem>

    </NGrid>
  </div>
</template>

<style scoped>
.dashboard {
  height: 100%;
}

.column-card {
  height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
}

.title {
  margin-top: 0;
  font-size: 18px;
  font-weight: 600;
}

.persona-info {
  text-align: center;
  padding: 40px 0;
}

.avatar-placeholder {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: #e2e8f0;
  margin: 0 auto 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  color: #64748b;
}

.live2d-preview-card {
  position: relative;
  overflow: hidden;
}

.preview-area {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
  border-radius: 12px;
}

.action-bar {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 12px;
  padding: 12px 24px;
  background: rgba(255,255,255,0.8);
  border-radius: 99px;
  backdrop-filter: blur(12px);
  box-shadow: var(--shadow-soft);
}

.analytics-stack {
  display: flex;
  flex-direction: column;
  gap: 24px;
  height: calc(100vh - 120px);
}

.chart-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: calc(100% - 40px);
  background: #f1f5f9;
  border-radius: 8px;
  color: #94a3b8;
}
</style>
