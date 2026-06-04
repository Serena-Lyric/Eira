<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed } from 'vue';
import defaultBg from '../assets/bg-default.jpg';
import { useChatSession } from '../composables/useChatSession';
import { useLive2DController } from '../composables/useLive2DController';
import { useActionParser } from '../composables/useActionParser';

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

// ── Template-facing state (keep same variable names) ────────────

const quickQuestions = ref(['路线怎么走？', '今天有什么表演？', '推荐附近的美食']);
const inputText = ref('');
const isPressed = ref<string | null>(null);
const showSettings = ref(false);

// Settings State
const voiceEnabled = ref(true);
const cameraMode = ref<'front' | 'rear' | 'hidden'>('front');
const cameraStreamActive = ref(false);
const cameraVideoRef = ref<HTMLVideoElement | null>(null);
const showMic = ref(true);
const quickQuestionsMode = ref<'center' | 'left' | 'hidden'>('center');
const inputBarMode = ref<'center' | 'left' | 'hidden'>('center');
const chatBubbleMode = ref<'center' | 'left' | 'hidden'>('center');
const bgUrl = ref(defaultBg);
const bgBlurEnabled = ref(false);

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

// 预留摄像头切换逻辑 API
watch(cameraMode, async (mode) => {
  console.log('Camera mode changed to:', mode);
  if (mode !== 'hidden') {
    // TODO: 调用摄像头API获取对应摄像头的 stream
  } else {
    cameraStreamActive.value = false;
  }
});

// ── Bridge composable state to template variables ────────────────

// Initial greeting shown before first interaction
const initialGreeting = ref('你好啊，我是你今天的导游，需要帮忙规划路线吗？');
const hasInteracted = ref(false);

// aiResponseText: combines initial greeting, streaming response, and final messages
const aiResponseText = computed(() => {
  if (!hasInteracted.value) return initialGreeting.value;
  if (currentResponse.value) return currentResponse.value;
  const msgs = wsMessages.value;
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant') return msgs[i].content;
  }
  return '';
});

const isAiTyping = computed(() =>
  wsPhase.value === 'thinking' || wsPhase.value === 'streaming'
);

const fileInput = ref<HTMLInputElement | null>(null);
const attachmentInput = ref<HTMLInputElement | null>(null);

// ── Send handler (replaces mockBackendResponse) ──────────────────

function handleSend() {
  if (inputText.value.trim()) {
    const text = inputText.value.trim();
    const cleanText = actionParser.stripTags(text);
    hasInteracted.value = true;
    wsSendText(cleanText);
    inputText.value = '';
  }
}

function handleQuickQuestion(q: string) {
  hasInteracted.value = true;
  wsSendText(q);
}

// ── File upload handlers (unchanged) ─────────────────────────────

function triggerBgUpload() {
  fileInput.value?.click();
}

function handleBgUpload(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    const file = target.files[0];
    const reader = new FileReader();
    reader.onload = (e) => {
      if (e.target?.result) {
        bgUrl.value = e.target.result as string;
      }
    };
    reader.readAsDataURL(file);
    target.value = '';
  }
}

function triggerAttachmentUpload() {
  attachmentInput.value?.click();
}

function handleAttachmentUpload(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    console.log('API CALL: Attachment uploaded');
    target.value = '';
  }
}

// ── Lifecycle ────────────────────────────────────────────────────

let cleanupActionBridge: (() => void) | null = null;

onMounted(() => {
  // Connect WebSocket (with auth token if available)
  wsConnect();

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

onUnmounted(() => {
  wsDisconnect();
  if (cleanupActionBridge) cleanupActionBridge();
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
          <!-- API integration placeholder -->
          <div class="camera-placeholder" v-if="!cameraStreamActive">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="camera-icon"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"></path><circle cx="12" cy="13" r="3"></circle></svg>
            <span class="camera-text">{{ cameraMode === 'front' ? '前置摄像头' : '后置摄像头' }}<br/>(API预留)</span>
          </div>
          <video v-else autoplay playsinline class="pip-video" ref="cameraVideoRef"></video>
        </div>
      </transition>
    </div>

    <div class="content-stack">
      <!-- Layer 2: Bottom UI -->
      <div class="ui-layer-bottom">
        <transition name="slide-up">
          <div
            v-if="chatBubbleMode !== 'hidden'"
            class="dialogue-bubble"
            :class="`align-${chatBubbleMode}`"
          >
            <span class="dialogue-text">
              {{ aiResponseText }}<span v-if="isAiTyping" class="typing-cursor"></span>
            </span>
          </div>
        </transition>

        <transition name="fade">
          <div v-if="quickQuestionsMode !== 'hidden'" class="quick-questions" :class="`align-${quickQuestionsMode}`">
            <button
              v-for="(q, idx) in quickQuestions"
              :key="idx"
              class="quick-btn"
              @click="handleQuickQuestion(q)"
            >
              {{ q }}
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
              <button v-if="showMic" class="action-btn mic-btn">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                  <line x1="12" y1="19" x2="12" y2="23"></line>
                  <line x1="8" y1="23" x2="16" y2="23"></line>
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
              <div class="s-info"><h3>背景图替换</h3><p>自定义您的专属场景</p></div>
              <button class="btn-g" @click="triggerBgUpload">更换图片</button>
              <input type="file" ref="fileInput" @change="handleBgUpload" style="display: none" />
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

            <!-- UI Visibility -->
            <div class="s-item">
              <div class="s-info"><h3>摄像头小窗</h3><p>显示前置摄像头或者后置摄像头</p></div>
              <div class="seg">
                <button :class="{sel: cameraMode==='front'}" @click="cameraMode='front'">前置</button>
                <button :class="{sel: cameraMode==='rear'}" @click="cameraMode='rear'">后置</button>
                <button :class="{sel: cameraMode==='hidden'}" @click="cameraMode='hidden'">隐藏</button>
              </div>
            </div>
            <div class="s-item">
              <div class="s-info"><h3>语音输入</h3><p>显示麦克风按钮</p></div>
              <div class="tgl" :class="{active: showMic}" @click="showMic = !showMic">
                <div class="tgl-k"></div>
              </div>
            </div>
            <div class="s-item">
              <div class="s-info"><h3>快捷提问</h3><p>显示推荐问题</p></div>
              <div class="tgl" :class="{active: quickQuestionsMode !== 'hidden'}" @click="quickQuestionsMode = quickQuestionsMode === 'hidden' ? 'center' : 'hidden'">
                <div class="tgl-k"></div>
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
              <textarea placeholder="请详细描述您遇到的问题..."></textarea>
              <button class="btn-p">提交</button>
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
