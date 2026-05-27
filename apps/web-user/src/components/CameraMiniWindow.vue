<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';

const videoRef = ref<HTMLVideoElement | null>(null);
let stream: MediaStream | null = null;

onMounted(async () => {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    if (videoRef.value) {
      videoRef.value.srcObject = stream;
    }
  } catch (err) {
    console.error("Camera access denied or unavailable", err);
  }
});

onUnmounted(() => {
  if (stream) {
    stream.getTracks().forEach(track => track.stop());
  }
});
</script>

<template>
  <div class="camera-pip">
    <video ref="videoRef" autoplay playsinline muted></video>
  </div>
</template>

<style scoped>
.camera-pip {
  width: 120px;
  height: 160px;
  border-radius: var(--radius-card);
  overflow: hidden;
  border: 1px solid var(--glass-border);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  box-shadow: var(--shadow-soft);
}

.camera-pip video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transform: scaleX(-1); /* Mirror effect */
}
</style>
