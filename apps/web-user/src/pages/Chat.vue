<script setup lang="ts">
import { ref } from 'vue';
import { GlassButton } from '@eira/ui-shared';
import Live2DCanvas from '../components/Live2DCanvas.vue';
import TopSettingsButton from '../components/TopSettingsButton.vue';
import CameraMiniWindow from '../components/CameraMiniWindow.vue';
import ChatInputArea from '../components/ChatInputArea.vue';
import CharacterSpeechBubble from '../components/CharacterSpeechBubble.vue';
import QuickQuestionPanel from '../components/QuickQuestionPanel.vue';
import SettingsPanel from '../components/SettingsPanel.vue';
import { useLive2DController } from '../composables/useLive2DController';
import { useChatSession } from '../composables/useChatSession';

const { containerRef, isLoaded } = useLive2DController('hiyori');
const { currentText, isThinking, sendText } = useChatSession();

const isSettingsOpen = ref(false);
const quickQuestions = ref(['Where are we now?', 'Tell me a story', 'Take a photo']);

function handleSend(text: string) {
  if (text.trim()) {
    sendText(text);
  }
}
</script>

<template>
  <div class="chat-layout">
    <!-- Layer 0: Background -->
    <div class="layer-bg"></div>

    <!-- Layer 1: Live2D Canvas (Z-Index 1) -->
    <div class="layer-canvas">
      <Live2DCanvas :container-ref="containerRef" />
    </div>

    <!-- Layer 2: UI Overlay (Z-Index 2) -->
    <div class="layer-ui">
      <!-- Top Area -->
      <TopSettingsButton class="ui-element pos-top-left" @click="isSettingsOpen = true" />
      <CameraMiniWindow class="ui-element pos-top-right" />

      <!-- Middle Area -->
      <CharacterSpeechBubble
        v-if="currentText || isThinking"
        class="ui-element pos-middle-center"
        :text="currentText"
        :is-thinking="isThinking"
      />
      <QuickQuestionPanel
        class="ui-element pos-middle-left"
        :questions="quickQuestions"
        @select="handleSend"
      />

      <!-- Bottom Area -->
      <ChatInputArea class="ui-element pos-bottom" @send="handleSend" />
    </div>

    <SettingsPanel :open="isSettingsOpen" @close="isSettingsOpen = false" />
  </div>
</template>

<style scoped>
.chat-layout {
  position: relative;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: #111;
}

.layer-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  /* Default background. Can be replaced with image/video */
  background: radial-gradient(circle at center, #2a3143 0%, #0d121c 100%);
}

.layer-canvas {
  position: absolute;
  inset: 0;
  z-index: 1;
}

.layer-ui {
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none; /* Let clicks pass through to canvas by default */
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: 1fr;
}

/* Base class for UI elements to re-enable clicks */
.ui-element {
  pointer-events: auto;
  position: absolute;
}

/* Positioning */
.pos-top-left {
  top: 24px;
  left: 24px;
}

.pos-top-right {
  top: 24px;
  right: 24px;
}

.pos-middle-center {
  bottom: 45%;
  left: 50%;
  transform: translateX(-50%);
}

.pos-middle-left {
  bottom: 120px;
  left: 5%;
  max-width: 250px;
}

.pos-bottom {
  bottom: 24px;
  left: 5%;
  right: 5%;
  width: 90%;
  margin: 0 auto;
}
</style>
