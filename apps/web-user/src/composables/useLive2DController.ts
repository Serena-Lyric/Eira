import { ref, onMounted, onUnmounted } from 'vue';
import { LAppDelegate } from '../live2d/lappdelegate';
import * as LAppDefine from '../live2d/lappdefine';

/**
 * Live2D 控制器（基于官方 Cubism SDK for Web 5 Framework 自管 WebGL 渲染）。
 *
 * 历史背景：曾用 pixi-live2d-display，但其与 Cubism 5 Core 不兼容
 *（库读 drawables.renderOrders，而 Core 5 把 renderOrders 移到了 model 顶层）
 * 导致渲染崩溃，故改用官方 Framework。
 *
 * 对外接口保持不变：containerRef / isLoaded / activeModelId / loadError /
 * triggerMotion / setMouthOpen，Chat.vue 无需改动。
 */

/** 模型描述符——按优先级排序（主模型在前，失败回退）。 */
interface ModelDescriptor {
  id: string;
  label: string;
  /** model3.json 所在目录（末尾带斜杠，相对站点根） */
  dir: string;
  /** model3.json 文件名 */
  fileName: string;
}

const MODEL_REGISTRY: ModelDescriptor[] = [
  {
    id: 'mao_pro_zh',
    label: 'Mao (Primary)',
    dir: '/live2d/mao_pro_zh/runtime/',
    fileName: 'mao_pro.model3.json',
  },
  {
    id: 'hiyori_pro_zh',
    label: 'Hiyori (Fallback)',
    dir: '/live2d/hiyori_pro_zh/runtime/',
    fileName: 'hiyori_pro_t11.model3.json',
  },
];

const LOAD_TIMEOUT_MS = 8000;
const STORAGE_PREFIX = 'eira:live2d:';

export function useLive2DController() {
  const containerRef = ref<HTMLElement | null>(null);
  const isLoaded = ref(false);
  const activeModelId = ref<string | null>(null);
  const loadError = ref<string | null>(null);

  let delegate: LAppDelegate | null = null;
  let canvas: HTMLCanvasElement | null = null;
  let wheelHandler: ((e: WheelEvent) => void) | null = null;
  let pointerDownHandler: ((e: PointerEvent) => void) | null = null;
  let pointerMoveHandler: ((e: PointerEvent) => void) | null = null;
  let pointerUpHandler: ((e: PointerEvent) => void) | null = null;

  /** 等待 Cubism Core 全局就绪。 */
  function waitForCubismCore(): Promise<void> {
    return new Promise((resolve) => {
      if ((window as any).Live2DCubismCore) {
        resolve();
        return;
      }
      const timer = setInterval(() => {
        if ((window as any).Live2DCubismCore) {
          clearInterval(timer);
          resolve();
        }
      }, 100);
      // 兜底：10s 后无论如何继续（Core 可能以其他方式可用）
      setTimeout(() => {
        clearInterval(timer);
        resolve();
      }, 10000);
    });
  }

  /** 等待某模型加载完成；超时返回 false。 */
  function waitModelReady(): Promise<boolean> {
    return new Promise((resolve) => {
      const start = Date.now();
      const timer = setInterval(() => {
        const model = delegate?.getSubdelegate()?.getLive2DManager()?.getModel();
        if (model && model.isCompleteSetup && model.isCompleteSetup()) {
          clearInterval(timer);
          resolve(true);
        } else if (Date.now() - start > LOAD_TIMEOUT_MS) {
          clearInterval(timer);
          resolve(false);
        }
      }, 100);
    });
  }

  function getView() {
    return delegate?.getSubdelegate()?.getView();
  }

  function setupInteractions() {
    const container = containerRef.value;
    if (!container || !canvas) return;

    // 拖拽平移（鼠标左键按住拖动模型，松开固定；作用于 Framework 的 ViewMatrix）。
    let dragging = false;
    let lastX = 0;
    let lastY = 0;

    canvas.style.touchAction = 'none'; // 触摸设备不滚动页面
    canvas.style.cursor = 'grab';

    pointerDownHandler = (e: PointerEvent) => {
      // 仅响应鼠标左键（button 0）；触摸/笔的 pointerdown button 也为 0
      if (e.button !== 0) return;
      e.preventDefault();
      dragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
      canvas!.style.cursor = 'grabbing';
      try {
        canvas!.setPointerCapture(e.pointerId); // 拖出 canvas 仍持续接收
      } catch {
        /* ignore */
      }
    };
    pointerMoveHandler = (e: PointerEvent) => {
      if (!dragging) return;
      const dx = e.clientX - lastX;
      const dy = e.clientY - lastY;
      lastX = e.clientX;
      lastY = e.clientY;
      // 屏幕 Y 向下为正，ViewMatrix Y 向上为正，故 dy 取反
      getView()?.panBy(dx, -dy);
    };
    pointerUpHandler = () => {
      if (dragging) {
        dragging = false;
        if (canvas) canvas.style.cursor = 'grab';
        saveView(); // 松开固定并持久化位置
      }
    };

    canvas.addEventListener('pointerdown', pointerDownHandler);
    window.addEventListener('pointermove', pointerMoveHandler);
    window.addEventListener('pointerup', pointerUpHandler);

    // 滚轮缩放：passive:false + preventDefault，阻止浏览器页面缩放
    wheelHandler = (e: WheelEvent) => {
      e.preventDefault();
      const rect = canvas!.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
      getView()?.zoomAt(cx, cy, factor);
      saveView();
    };
    container.addEventListener('wheel', wheelHandler, { passive: false });
  }

  /** 保存当前 ViewMatrix（缩放/平移）到 localStorage。 */
  function saveView() {
    const view = getView();
    if (!view) return;
    const id = activeModelId.value || 'default';
    const arr = Array.from(view.getViewMatrix().getArray());
    localStorage.setItem(`${STORAGE_PREFIX}${id}`, JSON.stringify(arr));
  }

  /** 从 localStorage 恢复 ViewMatrix。 */
  function restoreView(modelId: string) {
    const view = getView();
    if (!view) return;
    const saved = localStorage.getItem(`${STORAGE_PREFIX}${modelId}`);
    if (!saved) return;
    try {
      const arr = JSON.parse(saved);
      if (Array.isArray(arr) && arr.length === 16) {
        view.getViewMatrix().setMatrix(new Float32Array(arr));
      }
    } catch {
      /* ignore invalid state */
    }
  }

  async function initLive2D() {
    const container = containerRef.value;
    if (!container) return;

    await waitForCubismCore();

    // 创建 canvas 注入容器（样式由 Chat.vue 的 :deep(canvas) 控制）
    canvas = document.createElement('canvas');
    container.appendChild(canvas);

    delegate = LAppDelegate.getInstance();
    if (!delegate.initialize(canvas)) {
      loadError.value = 'WebGL 初始化失败';
      return;
    }
    delegate.run();

    const manager = delegate.getSubdelegate().getLive2DManager();

    // 依次尝试模型，成功即止
    for (const desc of MODEL_REGISTRY) {
      console.log(`[Live2D] Attempting to load: ${desc.label} from ${desc.dir}${desc.fileName}`);
      manager.loadModel(desc.dir, desc.fileName);
      const ok = await waitModelReady();
      if (ok) {
        activeModelId.value = desc.id;
        loadError.value = null;
        isLoaded.value = true;
        // 居中模型（Mao 等无 Layout 字段的模型需要），再恢复用户的缩放/平移
        manager.getModel()?.centerModel();
        restoreView(desc.id);
        setupInteractions();
        console.log(`[Live2D] Successfully loaded: ${desc.label}`);
        return;
      }
      console.warn(`[Live2D] Failed/timeout loading ${desc.label}, trying next...`);
    }

    loadError.value = 'All Live2D models failed to load';
    console.error('[Live2D] All models failed to load');
  }

  /**
   * 触发动作。回退顺序：请求组 → 空组 → Idle。
   */
  function triggerMotion(groupName: string, index?: number) {
    const model = delegate?.getSubdelegate()?.getLive2DManager()?.getModel();
    if (!model) {
      console.warn('[Live2D] Cannot trigger motion — model not loaded');
      return;
    }
    const setting = (model as any)._modelSetting;
    const candidates = [groupName, '', LAppDefine.MotionGroupIdle];
    for (const group of candidates) {
      try {
        if (setting && setting.getMotionCount(group) > 0) {
          if (index != null) {
            model.startMotion(group, index, LAppDefine.PriorityNormal);
          } else {
            model.startRandomMotion(group, LAppDefine.PriorityNormal);
          }
          return;
        }
      } catch {
        /* try next */
      }
    }
    console.warn(`[Live2D] Motion group "${groupName}" not available`);
  }

  /** 设置口型开合（0~1），由 LAppModel.update 末尾注入。 */
  function setMouthOpen(value: number) {
    const model = delegate?.getSubdelegate()?.getLive2DManager()?.getModel();
    if (model && model.setExternalMouthOpen) {
      model.setExternalMouthOpen(value);
    }
  }

  onMounted(() => {
    // 容器可能在下一 tick 才绑定，轮询等待
    const waitContainer = setInterval(() => {
      if (containerRef.value) {
        clearInterval(waitContainer);
        initLive2D();
      }
    }, 50);
    setTimeout(() => clearInterval(waitContainer), 5000);
  });

  onUnmounted(() => {
    if (wheelHandler && containerRef.value) {
      containerRef.value.removeEventListener('wheel', wheelHandler);
    }
    if (pointerMoveHandler) window.removeEventListener('pointermove', pointerMoveHandler);
    if (pointerUpHandler) window.removeEventListener('pointerup', pointerUpHandler);
    LAppDelegate.releaseInstance();
    delegate = null;
    if (canvas && canvas.parentElement) {
      canvas.parentElement.removeChild(canvas);
    }
    canvas = null;
  });

  return {
    containerRef,
    isLoaded,
    activeModelId,
    loadError,
    triggerMotion,
    setMouthOpen,
  };
}
