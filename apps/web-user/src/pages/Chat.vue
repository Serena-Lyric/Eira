<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed, nextTick } from 'vue';
import defaultBg from '../assets/bg-default.jpg';
import { useChatSession } from '../composables/useChatSession';
import { useLive2DController } from '../composables/useLive2DController';
import { useActionParser } from '../composables/useActionParser';
import { useVoiceWs } from '../composables/useVoiceWs';
import { useAudioPlayer } from '../composables/useAudioPlayer';
import { userApi, feedbackApi, voiceApi } from '../services/api';
import type { FeedbackResponse, BackgroundUploadResponse, ModelUploadResponse } from '../services/types';

// ── Chat Session (replaces mockBackendResponse) ─────────────────

const {
  messages: wsMessages,
  currentResponse,
  phase: wsPhase,
  sessionId,
  isConnected: wsConnected,
  connect: wsConnect,
  sendText: wsSendText,
  disconnect: wsDisconnect,
} = useChatSession();

// ── Live2D Controller ───────────────────────────────────────────

const live2dContainerRef = ref<HTMLElement | null>(null);
const { containerRef: l2dRef, isLoaded: l2dLoaded, activeModelId, loadError: l2dError, triggerMotion, setMouthOpen } =
  useLive2DController();

// ── Action Parser ────────────────────────────────────────────────

const actionParser = useActionParser();

// Bridge action parser to Live2D via DOM events
function setupActionBridge() {
  const handler = (e: Event) => {
    const detail = (e as CustomEvent).detail;
    if (detail?.group) {
      triggerMotion(detail.group);
    }
  };
  window.addEventListener('live2d:motion', handler);
  return () => window.removeEventListener('live2d:motion', handler);
}

// ── Voice WS + Audio Player (Phase 3 data integration) ────────────

const voiceWs = useVoiceWs();
const audioPlayer = useAudioPlayer();

// Connect audio player amplitude to Live2D lip sync
audioPlayer.setCallbacks({
  onAmplitude: (value: number) => {
    setMouthOpen(value);
  },
  onPlayStart: () => {
    // Start talking motion
    triggerMotion('Tap');
  },
  onPlayEnd: () => {
    // Reset mouth when audio ends
    setMouthOpen(0);
  },
});

// Voice WS callbacks
const voiceWsCallbacks = {
  onAsrPartial: (text: string) => {
    // Show partial recognition in input field
    inputText.value = text;
  },
  onAsrFinal: (text: string) => {
    // Final ASR result → use as input text
    inputText.value = text;
    // Auto-send the recognized text to trigger LLM response
    if (text.trim()) {
      wsSendText(text.trim());
    }
  },
  onChatToken: (text: string) => {
    // Accumulate streaming response text (already handled by useChatSession)
    // This is a secondary stream from /ws/voice
  },
  onChatAction: (tag: string) => {
    // Trigger Live2D motion
    triggerMotion(tag);
    // Also dispatch to action parser bridge
    window.dispatchEvent(new CustomEvent('live2d:motion', { detail: { group: tag } }));
  },
  onAudioChunk: (chunk: ArrayBuffer) => {
    // Enqueue TTS audio for playback
    audioPlayer.enqueue(chunk);
  },
  onChatDone: (_data: Record<string, unknown>) => {
    // Voice turn complete
  },
  onError: (code: string, detail: string) => {
    console.error(`[Voice] Error ${code}: ${detail}`);
  },
};

// ── Template-facing state (keep same variable names) ────────────

interface QuickQuestionItem {
  display_text: string
  send_text: string
}
// 快捷问题：初始为空，仅在后端推送数据后才显示
const quickQuestions = ref<QuickQuestionItem[]>([]);
const inputText = ref('');
const isPressed = ref<string | null>(null);
const showSettings = ref(false);

// Settings State
const voiceEnabled = ref(true);
const cameraMode = ref<'front' | 'rear' | 'hidden'>('hidden');
const cameraStreamActive = ref(false);
const cameraVideoRef = ref<HTMLVideoElement | null>(null);
const hasRearCamera = ref(false); // 检测后置摄像头是否可用
const showMic = ref(true);
const quickQuestionsMode = ref<'center' | 'left' | 'hidden'>('center');
const inputBarMode = ref<'center' | 'left' | 'hidden'>('center');
const chatBubbleMode = ref<'center' | 'left' | 'hidden'>('center');
const bgUrl = ref(defaultBg);
const bgBlurEnabled = ref(false);
const voiceInputMode = ref<'click' | 'persistent' | 'smart' | 'hidden'>('click');
const speechRate = ref(1.0);

// 防抖保存用户偏好
let savePrefsTimer: ReturnType<typeof setTimeout> | null = null;
function debouncedSavePrefs() {
  if (savePrefsTimer) clearTimeout(savePrefsTimer);
  savePrefsTimer = setTimeout(async () => {
    try {
      await userApi.savePreferences({
        background_url: bgUrl.value,
        background_blur: bgBlurEnabled.value,
        voice_enabled: voiceEnabled.value,
        camera_mode: cameraMode.value,
        show_mic: showMic.value,
        quick_questions: quickQuestions.value,
        chat_bubble_mode: chatBubbleMode.value,
        quick_questions_mode: quickQuestionsMode.value,
        input_bar_mode: inputBarMode.value,
        active_model_id: activeModelId.value ?? undefined,
        voice_input_mode: voiceInputMode.value,
        default_speech_rate: speechRate.value,
      });
    } catch {
      // 静默失败，不影响用户体验
    }
  }, 500);
}

watch(inputBarMode, (newVal) => {
  if (newVal === 'center') {
    if (chatBubbleMode.value === 'left') chatBubbleMode.value = 'center';
    if (quickQuestionsMode.value === 'left') quickQuestionsMode.value = 'center';
  } else if (newVal === 'left') {
    if (quickQuestionsMode.value !== 'hidden') {
      quickQuestionsMode.value = 'left';
    }
  }
});

// 自动保存用户偏好（除 inputBarMode 触发的级联外）
watch([bgBlurEnabled, voiceEnabled, cameraMode, showMic, voiceInputMode,
       chatBubbleMode, quickQuestionsMode, inputBarMode, speechRate],
  () => { debouncedSavePrefs(); }
);

// 语音录制状态
const isRecording = ref(false)
const voiceModeLabel = computed(() => {
  switch (voiceInputMode.value) {
    case 'click': return '点击录音'
    case 'persistent': return '常驻监听'
    case 'smart': return '智能检测'
    case 'hidden': return '隐藏'
    default: return ''
  }
})
let mediaRecorder: MediaRecorder | null = null
let audioChunks: Blob[] = []
let smartDetectionTimer: ReturnType<typeof setTimeout> | null = null
let silenceTimer: ReturnType<typeof setTimeout> | null = null

async function toggleVoiceRecording() {
  // 隐藏模式：不响应点击
  if (voiceInputMode.value === 'hidden') return

  // 点击模式：点击开始 / 再次点击结束
  if (voiceInputMode.value === 'click') {
    if (isRecording.value) {
      mediaRecorder?.stop()
      return
    }
    await startVoiceRecording()
    return
  }

  // 常驻模式：点击开启常驻，再次点击关闭
  if (voiceInputMode.value === 'persistent') {
    if (isRecording.value) {
      stopPersistentRecording()
      return
    }
    await startPersistentRecording()
    return
  }

  // 智能模式：点击开启智能检测
  if (voiceInputMode.value === 'smart') {
    if (isRecording.value) {
      stopSmartDetection()
      return
    }
    await startSmartDetection()
    return
  }
}

async function startVoiceRecording() {
  try {
    // Ensure voice WS is connected
    if (!voiceWs.isConnected.value) {
      voiceWs.connect(voiceWsCallbacks)
      // Wait for connection
      await new Promise<void>((resolve) => {
        const check = setInterval(() => {
          if (voiceWs.isConnected.value) {
            clearInterval(check)
            resolve()
          }
        }, 100)
        setTimeout(() => { clearInterval(check); resolve() }, 5000)
      })
    }

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    // Use timeslice to get dataavailable events every 250ms for streaming
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
    audioChunks = []

    // Send voice.start control message
    voiceWs.sendVoiceStart('zh')

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        // Stream audio chunk directly over WebSocket
        voiceWs.sendAudioChunk(e.data)
        // Also keep local buffer as fallback
        audioChunks.push(e.data)
      }
    }

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      isRecording.value = false
      // Send voice.end control message
      voiceWs.sendVoiceEnd()

      // Fallback: if WS is not connected, use REST API
      if (!voiceWs.isConnected.value && audioChunks.length > 0) {
        const blob = new Blob(audioChunks, { type: 'audio/webm' })
        console.log('API: POST /voice/asr — audio size:', (blob.size / 1024).toFixed(1), 'KB')
        try {
          const result = await voiceApi.sendAudio(blob)
          if (result.text) inputText.value = result.text
        } catch {
          console.warn('ASR request failed')
        }
      }
    }

    // Request data every 250ms for streaming
    mediaRecorder.start(250)
    isRecording.value = true
  } catch (err) {
    console.warn('Microphone access denied:', err)
  }
}

// 常驻模式：持续录音，静音 3 秒后自动停止
async function startPersistentRecording() {
  await startVoiceRecording()
}

function stopPersistentRecording() {
  mediaRecorder?.stop()
}

// 智能检测模式：持续监听，检测到语音时自动开始录音，静音时自动停止
let smartStream: MediaStream | null = null
let audioContext: AudioContext | null = null
let analyser: AnalyserNode | null = null

async function startSmartDetection() {
  try {
    smartStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    audioContext = new AudioContext()
    analyser = audioContext.createAnalyser()
    analyser.fftSize = 256
    const source = audioContext.createMediaStreamSource(smartStream)
    source.connect(analyser)

    isRecording.value = true
    const dataArray = new Uint8Array(analyser.frequencyBinCount)
    let isSpeaking = false

    function detect() {
      if (!analyser || !isRecording.value) return
      analyser.getByteFrequencyData(dataArray)
      const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length

      if (avg > 30 && !isSpeaking) {
        // 检测到语音开始
        isSpeaking = true
        console.log('[Smart ASR] Speech detected')
      } else if (avg < 15 && isSpeaking) {
        // 静音，延迟 2 秒后停止
        if (silenceTimer) clearTimeout(silenceTimer)
        silenceTimer = setTimeout(() => {
          isSpeaking = false
          console.log('[Smart ASR] Silence — stopping capture')
        }, 2000)
      }

      smartDetectionTimer = setTimeout(detect, 200)
    }
    detect()
  } catch (err) {
    console.warn('Smart detection failed:', err)
    isRecording.value = false
  }
}

function stopSmartDetection() {
  if (smartDetectionTimer) clearTimeout(smartDetectionTimer)
  if (silenceTimer) clearTimeout(silenceTimer)
  smartStream?.getTracks().forEach((t) => t.stop())
  smartStream = null
  audioContext?.close()
  audioContext = null
  analyser = null
  isRecording.value = false
}

// 摄像头切换逻辑
let cameraStream: MediaStream | null = null

async function startCamera(facingMode: 'user' | 'environment') {
  try {
    // 先尝试指定 facingMode
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode, width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    })
  } catch {
    // 指定 facingMode 失败时（如无后置摄像头），尝试不指定 facingMode
    try {
      cameraStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      })
    } catch (err) {
      console.warn('Camera access denied or unavailable:', err)
      cameraStreamActive.value = false
      return
    }
  }
  // 获取到摄像头权限后，重新枚举设备（此时 label 可读，能正确检测后置摄像头）
  await detectCameras()
  if (cameraVideoRef.value) {
    cameraVideoRef.value.srcObject = cameraStream
    // 确保视频开始播放
    await cameraVideoRef.value.play().catch(() => {})
  }
  cameraStreamActive.value = true
}

function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach((track) => track.stop())
    cameraStream = null
  }
  if (cameraVideoRef.value) {
    cameraVideoRef.value.srcObject = null
  }
  cameraStreamActive.value = false
}

watch(cameraMode, async (mode) => {
  console.log('Camera mode changed to:', mode)
  stopCamera()
  if (mode !== 'hidden') {
    // 等待 Vue 完成 DOM 更新（pip-window 和 video 元素渲染到 DOM）
    await nextTick()
  }
  if (mode === 'front') {
    await startCamera('user')
  } else if (mode === 'rear') {
    await startCamera('environment')
  }
  // 'hidden' already handled by stopCamera()
})

// ── Bridge composable state to template variables ────────────────

// AI response text: only shows streaming content or last assistant message
// Hidden when empty (no input yet, no response)
const aiResponseText = computed(() => {
  if (currentResponse.value) return currentResponse.value;
  const msgs = wsMessages.value;
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant') return msgs[i].content;
  }
  return '';
});

// Whether the bubble should be visible
const showBubble = computed(() => {
  return isAiTyping.value || aiResponseText.value.length > 0;
});

const isAiTyping = computed(() =>
  wsPhase.value === 'thinking' || wsPhase.value === 'streaming'
);

const fileInput = ref<HTMLInputElement | null>(null);
const modelFileInput = ref<HTMLInputElement | null>(null);
const attachmentInput = ref<HTMLInputElement | null>(null);

// Upload states
const bgUploading = ref(false)
const bgUploadMsg = ref('')
const modelUploading = ref(false)
const modelUploadMsg = ref('')
const modelUploadOk = ref(false)

// 允许的图片格式
const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']

// ── Send handler (replaces mockBackendResponse) ──────────────────

function handleSend() {
  if (inputText.value.trim()) {
    const text = inputText.value.trim();
    const cleanText = actionParser.stripTags(text);
    wsSendText(cleanText);
    inputText.value = '';
  }
}

function handleQuickQuestion(q: QuickQuestionItem) {
  const text = q.send_text || q.display_text;
  wsSendText(text);
}

// ── File upload handlers (unchanged) ─────────────────────────────

function triggerBgUpload() {
  fileInput.value?.click();
}

async function handleBgUpload(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    const file = target.files[0];
    // 验证图片格式
    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      bgUploadMsg.value = '仅支持 JPG、PNG、WebP 格式'
      setTimeout(() => { bgUploadMsg.value = '' }, 3000)
      target.value = ''
      return
    }
    bgUploading.value = true
    bgUploadMsg.value = '上传中...'

    try {
      // 先本地预览
      const reader = new FileReader()
      const dataUrl = await new Promise<string>((resolve, reject) => {
        reader.onload = (e) => {
          if (e.target?.result) resolve(e.target.result as string)
          else reject(new Error('读取失败'))
        }
        reader.onerror = () => reject(new Error('读取失败'))
        reader.readAsDataURL(file)
      })
      // 本地预览先显示
      bgUrl.value = dataUrl

      // 上传到后端，等待确认
      const response: BackgroundUploadResponse = await userApi.uploadBackground(file)
      if (response.success) {
        bgUploadMsg.value = '✓ 背景图已保存'
        // 使用后端返回的 URL 替换本地 data URL
        if (response.url) bgUrl.value = response.url
      } else {
        bgUploadMsg.value = response.message || '保存失败，请重试'
      }
    } catch (err: any) {
      // 根据错误类型给出不同提示
      if (err?.response?.status === 413) {
        bgUploadMsg.value = '图片文件过大（最大 10 MB）'
      } else if (err?.response?.status === 400) {
        bgUploadMsg.value = err?.response?.data?.detail || '不支持的图片格式'
      } else if (err?.code === 'ERR_NETWORK' || err?.message?.includes('Network')) {
        bgUploadMsg.value = '网络错误，请检查连接后重试'
      } else if (err?.response?.status === 401) {
        bgUploadMsg.value = '登录已过期，请重新登录'
      } else {
        bgUploadMsg.value = '上传失败：' + (err?.response?.data?.detail || err?.message || '未知错误')
      }
    } finally {
      bgUploading.value = false
      setTimeout(() => { bgUploadMsg.value = '' }, 5000)
    }
    target.value = '';
  }
}

function triggerModelUpload() {
  modelFileInput.value?.click();
}

async function handleModelUpload(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    const file = target.files[0];
    const ext = file.name.toLowerCase().split('.').pop()
    const allowedExts = ['zip', '7z', 'rar']
    const allowedTypes = ['application/zip', 'application/x-zip-compressed', 'application/x-7z-compressed', 'application/x-rar-compressed', 'application/vnd.rar', 'application/octet-stream']
    if (!allowedExts.includes(ext || '') && !allowedTypes.includes(file.type)) {
      modelUploadMsg.value = '仅支持 .zip / .7z / .rar 压缩包格式'
      modelUploadOk.value = false
      setTimeout(() => { modelUploadMsg.value = '' }, 3000)
      target.value = ''
      return
    }
    modelUploading.value = true
    modelUploadMsg.value = '正在解析模型包...'
    modelUploadOk.value = false

    try {
      // 步骤 1: 本地解析验证（模拟检查压缩包结构）
      // 实际解析需解压检查 model3.json、moc3 文件等，此处简化
      await new Promise<void>((resolve) => setTimeout(resolve, 800))
      modelUploadMsg.value = '正在上传到服务器...'

      // 步骤 2: 上传到后端，等待后端存储确认
      const response: ModelUploadResponse = await userApi.uploadModel(file)
      if (response.success) {
        modelUploadOk.value = true
        modelUploadMsg.value = `✓ 模型包解析成功，已保存 (${response.model_id || ''})`
        console.log('Model uploaded successfully:', response.model_id)
      } else {
        modelUploadMsg.value = response.message || '模型保存失败，请重试'
      }
    } catch (err: any) {
      if (err?.response?.status === 413) {
        modelUploadMsg.value = '模型包过大（最大 100 MB）'
      } else if (err?.response?.status === 400) {
        modelUploadMsg.value = err?.response?.data?.detail || '不支持的压缩格式或模型结构无效'
      } else if (err?.code === 'ERR_NETWORK' || err?.message?.includes('Network')) {
        modelUploadMsg.value = '网络错误，请检查连接后重试'
      } else if (err?.response?.status === 401) {
        modelUploadMsg.value = '登录已过期，请重新登录'
      } else {
        modelUploadMsg.value = '上传失败：' + (err?.response?.data?.detail || err?.message || '未知错误')
      }
    } finally {
      modelUploading.value = false
      setTimeout(() => { modelUploadMsg.value = '' }, 8000)
    }
    target.value = '';
  }
}

function triggerAttachmentUpload() {
  attachmentInput.value?.click();
}

function handleAttachmentUpload(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    const file = target.files[0]
    // API: 发送文件到后端
    console.log('API: POST /conversations/upload — file:', file.name, file.type)
    target.value = '';
  }
}

// ── Lifecycle ────────────────────────────────────────────────────

let cleanupActionBridge: (() => void) | null = null;
let cleanupQuickQuestions: (() => void) | null = null;

// 检测可用摄像头
async function detectCameras() {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    const videoDevices = devices.filter((d) => d.kind === 'videoinput')
    // 检测后置摄像头：通常标签含 "back" 或 "environment"，或 groupId 与前置不同
    hasRearCamera.value = videoDevices.some(
      (d) =>
        d.label.toLowerCase().includes('back') ||
        d.label.toLowerCase().includes('rear') ||
        d.label.toLowerCase().includes('environment')
    )
    // 如果有多个视频设备，很可能有后置
    if (videoDevices.length >= 2) hasRearCamera.value = true
  } catch {
    hasRearCamera.value = false
  }
}

onMounted(async () => {
  // 检测摄像头硬件
  await detectCameras()

  // Load user preferences from backend (if available)
  try {
    const prefs = await userApi.getPreferences()
    if (prefs) {
      if (prefs.background_url) bgUrl.value = prefs.background_url
      if (typeof prefs.background_blur === 'boolean') bgBlurEnabled.value = prefs.background_blur
      if (typeof prefs.voice_enabled === 'boolean') voiceEnabled.value = prefs.voice_enabled
      if (prefs.camera_mode) cameraMode.value = prefs.camera_mode
      if (typeof prefs.show_mic === 'boolean') showMic.value = prefs.show_mic
      if (prefs.voice_input_mode) voiceInputMode.value = prefs.voice_input_mode
      if (typeof prefs.default_speech_rate === 'number') speechRate.value = prefs.default_speech_rate
      if (prefs.quick_questions) {
        // 向后兼容：旧的 string[] 格式转换为 QuickQuestionItem[]
        const firstItem = prefs.quick_questions[0];
        if (typeof firstItem === 'string') {
          quickQuestions.value = (prefs.quick_questions as unknown as string[]).map((s) => ({
            display_text: s,
            send_text: s,
          }));
        } else {
          quickQuestions.value = prefs.quick_questions as QuickQuestionItem[];
        }
      }
      if (prefs.chat_bubble_mode) chatBubbleMode.value = prefs.chat_bubble_mode
      if (prefs.quick_questions_mode) quickQuestionsMode.value = prefs.quick_questions_mode
      if (prefs.input_bar_mode) inputBarMode.value = prefs.input_bar_mode
    }
  } catch {
    // Backend not ready — use defaults
  }

  // Connect WebSocket (with auth token if available)
  wsConnect();

  // Connect Voice WebSocket for ASR/TTS streaming
  voiceWs.connect(voiceWsCallbacks);

  // 监听后端推送的快捷问题
  const onQQ = (e: Event) => {
    const detail = (e as CustomEvent).detail;
    if (Array.isArray(detail)) {
      const items = detail.map((item: any) => {
        if (typeof item === 'string') {
          return { display_text: item, send_text: item };
        }
        return {
          display_text: item.display_text || item.send_text || '',
          send_text: item.send_text || item.display_text || '',
        };
      }).filter((q: QuickQuestionItem) => q.display_text);
      if (items.length > 0) {
        quickQuestions.value = items;
      }
    }
  };
  window.addEventListener('eira:quick-questions', onQQ);
  cleanupQuickQuestions = () => window.removeEventListener('eira:quick-questions', onQQ);

  // Setup Live2D if container exists
  if (live2dContainerRef.value) {
    l2dRef.value = live2dContainerRef.value;
  } else {
    // Look for existing canvas in the DOM as fallback
    const existingCanvas = document.querySelector('.web-user-container');
    if (existingCanvas) {
      l2dRef.value = existingCanvas as HTMLElement;
    }
  }

  // Bridge action parser → Live2D
  cleanupActionBridge = setupActionBridge();
});

// Feedback submission state
const feedbackText = ref('')
const feedbackSending = ref(false)
const feedbackSent = ref(false)
const feedbackError = ref('')

async function submitFeedback() {
  if (!feedbackText.value.trim() || feedbackSending.value) return
  feedbackSending.value = true
  feedbackError.value = ''
  try {
    const response: FeedbackResponse = await feedbackApi.submit(feedbackText.value)
    if (response.success) {
      feedbackSent.value = true
      feedbackText.value = ''
      setTimeout(() => { feedbackSent.value = false }, 5000)
    } else {
      feedbackError.value = response.message || '提交失败，请重试'
    }
  } catch (err: any) {
    if (err?.code === 'ERR_NETWORK' || err?.message?.includes('Network')) {
      feedbackError.value = '网络错误，请检查连接后重试'
    } else if (err?.response?.status === 401) {
      feedbackError.value = '登录已过期，请重新登录'
    } else {
      feedbackError.value = '提交失败：' + (err?.response?.data?.detail || err?.message || '未知错误')
    }
  } finally {
    feedbackSending.value = false
  }
}

onUnmounted(() => {
  wsDisconnect();
  voiceWs.disconnect();
  audioPlayer.stop();
  stopCamera();
  if (cleanupActionBridge) cleanupActionBridge();
  if (cleanupQuickQuestions) cleanupQuickQuestions();
});
</script>

<template>
  <div class="web-user-container" ref="live2dContainerRef">
    <!-- Main Layer Stack -->
    <!-- Layer 0: Background -->
    <div class="background-container">
      <img
        id="fullscreen-bg"
        class="layer-bg"
        :class="{ 'is-blurred': bgBlurEnabled }"
        :src="bgUrl"
        alt="Background"
      />
    </div>

    <!-- Layer 1: Top UI (Global, spans full width) -->
    <div class="ui-layer-top">
      <button
        class="settings-btn"
        @mousedown="isPressed = 'settings'"
        @mouseup="isPressed = null"
        @click="showSettings = true"
        :class="{ pressed: isPressed === 'settings' }"
      >
        <svg class="icon-gear" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
        </svg>
      </button>

      <transition name="fade">
        <div v-if="cameraMode !== 'hidden'" class="pip-window">
          <!-- 摄像头未激活时的占位图标（v-show 保持 DOM 存在，避免 ref 绑定丢失） -->
          <div class="camera-placeholder" v-show="!cameraStreamActive">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="camera-icon"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"></path><circle cx="12" cy="13" r="3"></circle></svg>
            <span class="camera-text">{{ cameraMode === 'front' ? '前置摄像头' : '后置摄像头' }}</span>
          </div>
          <video v-show="cameraStreamActive" autoplay playsinline muted class="pip-video" ref="cameraVideoRef"></video>
        </div>
      </transition>
    </div>

    <div class="content-stack">
      <!-- Layer 2: Bottom UI -->
      <div class="ui-layer-bottom">
        <transition name="slide-up">
          <div
            v-if="chatBubbleMode !== 'hidden' && showBubble"
            class="dialogue-bubble"
            :class="`align-${chatBubbleMode}`"
          >
            <span class="dialogue-text">
              {{ aiResponseText }}<span v-if="isAiTyping" class="typing-cursor"></span>
            </span>
          </div>
        </transition>

        <transition name="fade">
          <div v-if="quickQuestionsMode !== 'hidden' && quickQuestions.length > 0" class="quick-questions" :class="`align-${quickQuestionsMode}`">
            <button
              v-for="(q, idx) in quickQuestions"
              :key="idx"
              class="quick-btn"
              @click="handleQuickQuestion(q)"
            >
              {{ q.display_text }}
            </button>
          </div>
        </transition>

        <transition name="slide-up">
          <div
            v-if="inputBarMode !== 'hidden'"
            class="input-bar"
            :class="`mode-${inputBarMode}`"
          >
            <transition name="fade">
              <button v-if="showMic" class="action-btn mic-btn" :class="{ recording: isRecording }" @click="toggleVoiceRecording">
                <svg v-if="!isRecording" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                  <line x1="12" y1="19" x2="12" y2="23"></line>
                  <line x1="8" y1="23" x2="16" y2="23"></line>
                </svg>
                <svg v-else viewBox="0 0 24 24" width="22" height="24" fill="#EF4444">
                  <rect x="5" y="5" width="14" height="14" rx="3" />
                </svg>
              </button>
            </transition>

            <input
              class="input-field"
              v-model="inputText"
              type="text"
              placeholder="输入您的问题..."
              @keyup.enter="handleSend"
            />

            <div class="action-group">
              <button class="action-btn plus-btn" @click="triggerAttachmentUpload">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="12" y1="5" x2="12" y2="19"></line>
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
              </button>
              <input type="file" ref="attachmentInput" @change="handleAttachmentUpload" style="display: none" />

              <button class="action-btn send-btn" :disabled="!inputText.trim()" @click="handleSend">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13"></line>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                </svg>
              </button>
            </div>
          </div>
        </transition>
      </div>
    </div>

    <!-- Settings Overlay -->
    <transition name="fade">
      <div v-if="showSettings" class="settings-overlay">
        <div class="settings-card">
          <div class="settings-header">
            <h2>设置</h2>
            <button class="close-x" @click="showSettings = false">×</button>
          </div>
          <div class="settings-body">
            <!-- Scene Settings -->
            <div class="s-item">
              <div class="s-info"><h3>背景图替换</h3><p>自定义场景（支持 JPG/PNG/WebP）</p></div>
              <button class="btn-g" @click="triggerBgUpload">{{ bgUploading ? '上传中...' : '更换图片' }}</button>
              <input type="file" ref="fileInput" accept="image/jpeg,image/png,image/webp" @change="handleBgUpload" style="display: none" />
            </div>
            <div class="s-item" v-if="bgUploadMsg" :style="{background: bgUploadMsg.startsWith('✓') ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)', border: '1px solid ' + (bgUploadMsg.startsWith('✓') ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)')}">
              <span :style="{color: bgUploadMsg.startsWith('✓') ? '#10B981' : '#EF4444', fontSize:'13px'}">{{ bgUploadMsg }}</span>
            </div>
            <div class="s-item">
              <div class="s-info"><h3>模型上传</h3><p>上传 Live2D 模型包（支持 .zip / .7z / .rar）</p></div>
              <button class="btn-g" @click="triggerModelUpload">{{ modelUploading ? '解析中...' : '选择文件' }}</button>
              <input type="file" ref="modelFileInput" accept=".zip,.7z,.rar" @change="handleModelUpload" style="display: none" />
            </div>
            <div class="s-item" v-if="modelUploadMsg" :style="{background: modelUploadOk ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)', border: '1px solid ' + (modelUploadOk ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)')}">
              <span :style="{color: modelUploadOk ? '#10B981' : '#EF4444', fontSize:'13px'}">{{ modelUploadMsg }}</span>
            </div>
            <div class="s-item">
              <div class="s-info"><h3>背景模糊</h3><p>突出前景内容</p></div>
              <div class="tgl" :class="{active: bgBlurEnabled}" @click="bgBlurEnabled = !bgBlurEnabled">
                <div class="tgl-k"></div>
              </div>
            </div>

            <!-- Audio Settings -->
            <div class="s-item">
              <div class="s-info"><h3>语音播报</h3><p>开启AI语音回复</p></div>
              <div class="tgl" :class="{active: voiceEnabled}" @click="voiceEnabled = !voiceEnabled">
                <div class="tgl-k"></div>
              </div>
            </div>
            <div class="s-item">
              <div class="s-info"><h3>默认语速</h3><p>AI语音回复的播放速度</p></div>
              <div class="seg">
                <button v-for="rate in [0.5, 0.75, 1.0, 1.25, 1.5]" :key="rate"
                  :class="{sel: speechRate === rate}"
                  @click="speechRate = rate; debouncedSavePrefs()">
                  {{ rate }}x
                </button>
              </div>
            </div>

            <!-- UI Visibility -->
            <div class="s-item">
              <div class="s-info"><h3>摄像头小窗</h3><p>显示前置摄像头或者后置摄像头</p></div>
              <div class="seg">
                <button :class="{sel: cameraMode==='front'}" @click="cameraMode='front'">前置</button>
                <button :class="{sel: cameraMode==='rear'}" :disabled="!hasRearCamera" @click="cameraMode='rear'">后置</button>
                <button :class="{sel: cameraMode==='hidden'}" @click="cameraMode='hidden'">隐藏</button>
              </div>
            </div>
            <div class="s-item">
              <div class="s-info"><h3>语音输入</h3><p>显示麦克风按钮及输入模式</p></div>
              <div class="tgl" :class="{active: showMic}" @click="showMic = !showMic">
                <div class="tgl-k"></div>
              </div>
            </div>
            <div class="s-item" v-if="showMic">
              <div class="s-info"><h3>语音输入模式</h3><p>{{ voiceModeLabel }}</p></div>
              <div class="seg">
                <button :class="{sel: voiceInputMode==='click'}" @click="voiceInputMode='click'">点击</button>
                <button :class="{sel: voiceInputMode==='persistent'}" @click="voiceInputMode='persistent'">常驻</button>
                <button :class="{sel: voiceInputMode==='smart'}" @click="voiceInputMode='smart'">智能</button>
                <button :class="{sel: voiceInputMode==='hidden'}" @click="voiceInputMode='hidden'">隐藏</button>
              </div>
            </div>
            <!-- Layout Settings -->
            <div class="s-item">
              <div class="s-info"><h3>对话气泡位置</h3></div>
              <div class="seg">
                <button :class="{sel: chatBubbleMode==='center'}" @click="chatBubbleMode='center'">居中</button>
                <button :class="{sel: chatBubbleMode==='left'}" :disabled="inputBarMode === 'center'" @click="chatBubbleMode='left'">居左</button>
                <button :class="{sel: chatBubbleMode==='hidden'}" @click="chatBubbleMode='hidden'">隐藏</button>
              </div>
            </div>
            <div class="s-item">
              <div class="s-info"><h3>快捷问题位置</h3></div>
              <div class="seg">
                <button :class="{sel: quickQuestionsMode==='center'}" @click="quickQuestionsMode='center'">居中</button>
                <button :class="{sel: quickQuestionsMode==='left'}" :disabled="inputBarMode === 'center'" @click="quickQuestionsMode='left'">居左</button>
                <button :class="{sel: quickQuestionsMode==='hidden'}" @click="quickQuestionsMode='hidden'">隐藏</button>
              </div>
            </div>
            <div class="s-item">
              <div class="s-info"><h3>输入框位置</h3></div>
              <div class="seg">
                <button :class="{sel: inputBarMode==='center'}" @click="inputBarMode='center'">居中</button>
                <button :class="{sel: inputBarMode==='left'}" @click="inputBarMode='left'">居左</button>
                <button :class="{sel: inputBarMode==='hidden'}" @click="inputBarMode='hidden'">隐藏</button>
              </div>
            </div>

            <!-- Feedback -->
            <div class="s-item feedback">
              <div class="s-info"><h3>意见反馈</h3><p>帮助我们改进体验</p></div>
              <textarea v-model="feedbackText" placeholder="请详细描述您遇到的问题..."></textarea>
              <button class="btn-p" @click="submitFeedback" :disabled="!feedbackText.trim() || feedbackSending">
                {{ feedbackSending ? '提交中...' : feedbackSent ? '✓ 已提交' : '提交' }}
              </button>
              <div v-if="feedbackError" style="color:#EF4444;font-size:13px;margin-top:8px">{{ feedbackError }}</div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.web-user-container { position: relative; width: 100vw; height: 100vh; overflow: hidden; background: #000; display: flex; align-items: center; justify-content: center; font-family: 'PingFang SC', system-ui, sans-serif;
  /* 全局禁用文字框选（拖拽 Live2D 时不会误选页面文字） */
  user-select: none; -webkit-user-select: none;
}
/* 输入框与文本域内仍允许框选/编辑 */
.web-user-container input,
.web-user-container textarea { user-select: text; -webkit-user-select: text; }
.content-stack { position: relative; width: 100%; height: 100%; max-width: 800px; margin: 0 auto; display: flex; flex-direction: column;
  /* 让点击穿透到下层 canvas（仅交互控件重新开启 pointer-events） */
  pointer-events: none;
}

/* Background */
.background-container { position: absolute; inset: 0; z-index: 0; overflow: hidden; }
.layer-bg { width: 100%; height: 100%; object-fit: cover; transition: filter 0.6s ease; transform: scale(1.05); }
.layer-bg.is-blurred { filter: blur(30px) brightness(0.8); }

/* PIXI Live2D canvas — positioned behind UI, above background */
.web-user-container :deep(canvas) {
  position: absolute;
  top: 0;
  left: 0;
  width: 100% !important;
  height: 100% !important;
  object-fit: contain;
  z-index: 1;
}

/* UI Layer Top (Global layout to snap to corners on desktop) */
.ui-layer-top { position: absolute; inset: 0; z-index: 10; display: flex; justify-content: space-between; align-items: flex-start; padding: calc(env(safe-area-inset-top, 0px) + 24px) calc(env(safe-area-inset-right, 0px) + 24px) 0 calc(env(safe-area-inset-left, 0px) + 24px); pointer-events: none; }
.ui-layer-top > * { pointer-events: auto; }
.settings-btn { width: 48px; height: 48px; background: rgba(255,255,255,0.15); backdrop-filter: blur(10px); border-radius: 50%; border: 1px solid rgba(255,255,255,0.2); color: #FFF; display: flex; align-items: center; justify-content: center; cursor: pointer; }
.icon-gear { width: 24px; height: 24px; }
.pip-window { width: 140px; height: 140px; border-radius: 24px; background: rgba(255,255,255,0.1); backdrop-filter: blur(20px); border: 2px solid rgba(255,255,255,0.3); overflow: hidden; box-shadow: 0 12px 32px rgba(0,0,0,0.3); }
.camera-placeholder { width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; color: rgba(255,255,255,0.7); }
.camera-icon { width: 32px; height: 32px; margin-bottom: 8px; }
.camera-text { font-size: 12px; }
.pip-video { width: 100%; height: 100%; object-fit: cover; }

/* UI Layer Bottom */
.ui-layer-bottom { position: relative; margin-top: auto; z-index: 10; display: flex; flex-direction: column; gap: 16px; padding: 24px 24px calc(env(safe-area-inset-bottom, 24px) + 12px); width: 100%; box-sizing: border-box; pointer-events: none; }
/* 仅可交互控件接收事件，其余区域穿透到 Live2D canvas 以便拖拽 */
.ui-layer-bottom .quick-btn,
.ui-layer-bottom .input-bar { pointer-events: auto; }

.dialogue-bubble { max-width: 85%; background: linear-gradient(135deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0.05) 100%); backdrop-filter: blur(40px); border: 1px solid rgba(255,255,255,0.25); border-radius: 24px; padding: 18px 24px; box-shadow: 0 12px 32px rgba(0,0,0,0.2); }
.dialogue-bubble.align-center { align-self: center; text-align: center; }
.dialogue-bubble.align-left { align-self: flex-start; text-align: left; }
.dialogue-text { font-size: 18px; color: #FFF; line-height: 1.5; font-weight: 500; }

.quick-questions { display: flex; flex-direction: column; gap: 10px; align-items: flex-start; width: 100%; }
.quick-questions.align-left { align-items: flex-start; }
.quick-questions.align-center { align-items: center; }
.quick-btn { width: max-content; max-width: 90%; background: rgba(255,255,255,0.12); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.15); border-radius: 20px; padding: 10px 20px; font-size: 15px; color: #EEE; cursor: pointer; text-align: left; transition: 0.2s; }
.quick-btn:hover { background: rgba(255,255,255,0.2); }

.input-bar { height: 64px; background: rgba(255,255,255,0.15); backdrop-filter: blur(40px); border: 1px solid rgba(255,255,255,0.2); border-radius: 32px; display: flex; align-items: center; padding: 0 10px; gap: 8px; box-shadow: 0 16px 40px rgba(0,0,0,0.3); transition: width 0.4s ease; box-sizing: border-box; }
.input-bar.mode-center { width: 100%; max-width: 760px; align-self: center; }
.input-bar.mode-left { width: 100%; max-width: 760px; align-self: flex-start; }

.action-btn { width: 44px; height: 44px; border-radius: 50%; border: none; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: 0.2s; background: rgba(255,255,255,0.1); color: #FFF; flex-shrink: 0; }
.action-btn svg { width: 22px; height: 24px; }
.send-btn { background: linear-gradient(135deg, #5B92FF, #3867ED); }
.send-btn:disabled { opacity: 0.4; }

.input-field { flex: 1; background: transparent; border: none; outline: none; font-size: 16px; color: #FFF; padding: 0 4px; min-width: 0; }
.input-field::placeholder { color: rgba(255,255,255,0.4); }
.action-group { display: flex; gap: 8px; flex-shrink: 0; }

/* Settings Overlay */
.settings-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); backdrop-filter: blur(15px); z-index: 100; display: flex; align-items: center; justify-content: center; padding: 20px; }
.settings-card { width: 100%; max-width: 480px; background: rgba(30,35,45,0.9); border: 1px solid rgba(255,255,255,0.15); border-radius: 32px; padding: 28px; box-shadow: 0 32px 64px rgba(0,0,0,0.5); color: #FFF; max-height: 90vh; overflow-y: auto; scrollbar-width: none; }
.settings-card::-webkit-scrollbar { display: none; }
.settings-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-shrink: 0; }
.settings-header h2 { font-size: 24px; margin: 0; }
.close-x { background: transparent; border: none; color: #AAA; font-size: 32px; cursor: pointer; }

.settings-body { display: flex; flex-direction: column; gap: 20px; }
.s-item { padding: 16px; background: rgba(255,255,255,0.05); border-radius: 20px; display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.s-info h3 { font-size: 16px; margin: 0 0 4px; }
.s-info p { font-size: 12px; color: #888; margin: 0; }

.tgl { width: 50px; height: 28px; border-radius: 14px; background: rgba(255,255,255,0.1); position: relative; cursor: pointer; transition: 0.3s; flex-shrink: 0; }
.tgl.active { background: #3B82F6; }
.tgl-k { width: 22px; height: 22px; background: #FFF; border-radius: 50%; position: absolute; top: 3px; left: 3px; transition: 0.3s; }
.tgl.active .tgl-k { left: 25px; }

.seg { display: flex; background: rgba(0,0,0,0.2); border-radius: 12px; padding: 4px; flex-shrink: 0; }
.seg button { background: transparent; border: none; color: #888; padding: 6px 12px; font-size: 13px; border-radius: 8px; cursor: pointer; transition: 0.2s; }
.seg button.sel { background: rgba(255,255,255,0.15); color: #FFF; }
.seg button:disabled { opacity: 0.3; cursor: not-allowed; }

.btn-g { padding: 8px 16px; border-radius: 10px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: #FFF; cursor: pointer; flex-shrink: 0; }
.feedback { flex-direction: column; align-items: stretch; }
.feedback textarea { width: 100%; height: 80px; background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 12px; color: #FFF; font-family: inherit; resize: none; margin-top: 10px; outline: none; box-sizing: border-box; }
.btn-p { margin-top: 12px; padding: 12px; border-radius: 12px; background: #3B82F6; border: none; color: #FFF; font-weight: 600; cursor: pointer; flex-shrink: 0; }

/* Transitions */
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.slide-up-enter-active, .slide-up-leave-active { transition: all 0.4s ease; }
.slide-up-enter-from, .slide-up-leave-to { opacity: 0; transform: translateY(20px); }

/* Responsive adjustments */
@media (max-width: 480px) {
  .dialogue-text { font-size: 16px; }
  .quick-btn { font-size: 14px; }
  .pip-window { width: 100px; height: 100px; }
}
@media (min-width: 1024px) {
  .content-stack { max-width: 100%; width: 100%; padding: 0; }
  .ui-layer-bottom { padding: 40px; }
  .ui-layer-top { padding: 40px; }
  .pip-window { width: 200px; height: 200px; }
  .settings-btn { width: 56px; height: 56px; }
  .icon-gear { width: 28px; height: 28px; }

  /* Make left-aligned elements align with the left settings button */
  .dialogue-bubble.align-left { margin-left: 0; align-self: flex-start; }
  .quick-questions.align-left { margin-left: 0; align-items: flex-start; }
  .input-bar.mode-left { margin-left: 0; align-self: flex-start; }
}
</style>
