import { ref, onMounted, onUnmounted } from 'vue';
import { LAppDelegate } from '../live2d/lappdelegate';
import * as LAppDefine from '../live2d/lappdefine';
import { useLive2DModelLoader } from './useLive2DModelLoader';

/**
 * Live2D 控制器（基于官方 Cubism SDK for Web 5 Framework 自管 WebGL 渲染）。
 *
 * §4 fix: 不再使用硬编码 MODEL_REGISTRY。模型从 OSS 下载 → JSZip 解压 →
 * IndexedDB 缓存 → 通过 fetch 拦截器提供 Blob URL 给 Cubism SDK。
 *
 * 对外接口保持不变：containerRef / isLoaded / activeModelId / loadError /
 * triggerMotion / setMouthOpen，Chat.vue 无需改动。
 */

const LOAD_TIMEOUT_MS = 8000;
const STORAGE_PREFIX = 'eira:live2d:';

export function useLive2DController() {
  const containerRef = ref<HTMLElement | null>(null);
  const isLoaded = ref(false);
  // activeModelId：当前模型的 virtualBase（eira-model://...），仅用于本地视图矩阵缓存键，
  // 绝不可持久化到 DB 的 active_model_id（见 P1 根因：会污染成虚拟前缀导致下次加载 502）。
  const activeModelId = ref<string | null>(null);
  // activeModelOssKey：当前模型的真实 OSS key（live2d/.../xxx.zip），用于持久化到 active_model_id。
  const activeModelOssKey = ref<string | null>(null);
  const loadError = ref<string | null>(null);

  // §4 fix: Model loader replaces hardcoded MODEL_REGISTRY
  const modelLoader = useLive2DModelLoader();

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

  /** 获取当前加载的模型实例。 */
  function getModel() {
    return delegate?.getSubdelegate()?.getLive2DManager()?.getModel();
  }

  // getModel は将来の拡張用に保持（音声/動作ブリッジから参照されうる）。
  void getModel;

  /**
   * 指针(clientX, clientY)是否在交互区域内。
   *
   * 改为页面判定：仅判断指针是否在 canvas 所覆盖的窗口范围内，
   * 不再使用 readPixels 做像素级 alpha 检测。
   */
  function isPointerOverCharacter(clientX: number, clientY: number): boolean {
    if (!canvas) return false;
    const rect = canvas.getBoundingClientRect();
    return (
      clientX >= rect.left &&
      clientX <= rect.right &&
      clientY >= rect.top &&
      clientY <= rect.bottom
    );
  }

  function setupInteractions() {
    const container = containerRef.value;
    if (!container || !canvas) return;

    // アクティブなポインタを追跡（マルチタッチ pinch 用）
    const pointers = new Map<number, { x: number; y: number }>();
    let dragging = false;
    let lastX = 0;
    let lastY = 0;
    let pinchDist = 0; // 直前の2指間距離

    // ホイールズーム用「セッション」状態。
    // 角色上で初めてホイールを回した時に arm し、以降は連続スクロール中
    // 命中判定をスキップして滑らかにズーム。スクロールが止まったら（=放開）
    // タイマーで解除し、次回は再び命中判定からやり直す。
    let wheelArmed = false;
    let wheelIdleTimer: ReturnType<typeof setTimeout> | null = null;

    canvas.style.touchAction = 'none';
    canvas.style.cursor = 'grab';

    const dist2 = () => {
      const pts = Array.from(pointers.values());
      const dx = pts[0].x - pts[1].x;
      const dy = pts[0].y - pts[1].y;
      return Math.hypot(dx, dy);
    };

    // 门控：仅在「手势开始」时命中判定一次；手势进行中不再重复检测，
    // 直到松开（指针抬起 / 滚轮停止）才重新检测下一次手势。
    pointerDownHandler = (e: PointerEvent) => {
      if (e.pointerType !== 'touch' && e.button !== 0) return;
      // 2 指目以降は pinch 継続のため命中判定をスキップ（1 指目で既に角色上に居る）。
      if (pointers.size === 0 && !isPointerOverCharacter(e.clientX, e.clientY)) return;
      e.preventDefault();
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

      if (pointers.size === 1) {
        dragging = true;
        lastX = e.clientX;
        lastY = e.clientY;
        canvas!.style.cursor = 'grabbing';
        try { canvas!.setPointerCapture(e.pointerId); } catch { /* ignore */ }
      } else if (pointers.size === 2) {
        // 2指目が触れたら pan を中断し pinch ズームへ
        dragging = false;
        pinchDist = dist2();
      }
    };
    pointerMoveHandler = (e: PointerEvent) => {
      if (!pointers.has(e.pointerId) || document.querySelector('.settings-overlay')) return;
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

      if (pointers.size >= 2) {
        // 双指 pinch：距離比でモデル中心ズーム（手势中は命中判定しない）
        const d = dist2();
        if (pinchDist > 0 && d > 0) {
          getView()?.zoomByCenter(d / pinchDist);
        }
        pinchDist = d;
        return;
      }
      if (!dragging) return;
      const dx = e.clientX - lastX;
      const dy = e.clientY - lastY;
      lastX = e.clientX;
      lastY = e.clientY;
      getView()?.panBy(dx, dy);
    };
    pointerUpHandler = (e: PointerEvent) => {
      pointers.delete(e.pointerId);
      if (pointers.size < 2) pinchDist = 0;
      if (pointers.size === 0 && dragging) {
        dragging = false; // 松开 → 下次手势重新检测
        if (canvas) canvas.style.cursor = 'grab';
        saveView();
      } else if (pointers.size === 1) {
        // pinch 終了後、残った1指で pan を再開
        const [p] = Array.from(pointers.values());
        dragging = true;
        lastX = p.x;
        lastY = p.y;
        saveView();
      }
    };

    canvas.addEventListener('pointerdown', pointerDownHandler);
    window.addEventListener('pointermove', pointerMoveHandler);
    window.addEventListener('pointerup', pointerUpHandler);
    window.addEventListener('pointercancel', pointerUpHandler);

    // 滚轮缩放：首次需命中角色才 arm；之后连续滚动持续以模型中心缩放，
    // 不再每 tick 重复检测（避免模型缩小后光标落到透明像素导致缩放中断）。
    // 滚轮停止约 220ms（视为「放开」）后解除 arm，下次重新检测。
    wheelHandler = (e: WheelEvent) => {
      if (document.querySelector('.settings-overlay')) return;
      if (!wheelArmed) {
        if (!isPointerOverCharacter(e.clientX, e.clientY)) return;
        wheelArmed = true;
      }
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
      getView()?.zoomByCenter(factor);
      saveView();
      if (wheelIdleTimer) clearTimeout(wheelIdleTimer);
      wheelIdleTimer = setTimeout(() => { wheelArmed = false; }, 500);
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
      if (!Array.isArray(arr) || arr.length !== 16) return;
      // 合法性校验：旧版本可能保存了「中心偏移 / 出屏」的坏矩阵，会让模型一直复活到屏幕外。
      // 缩放(arr[0]) 必须在允许范围内，平移(arr[12],arr[13]) 不能离原点过远，否则丢弃用默认居中。
      const scale = arr[0];
      const tx = arr[12];
      const ty = arr[13];
      // tx/ty 上限を screenRect の想定最大 (±ratio≈±2.7 以下) に合わせる。
      // 旧値 ±5.0 では縮小時に画面外へ飛ぶマトリクスを許容してしまうため。
      const valid =
        Number.isFinite(scale) && scale >= LAppDefine.ViewMinScale * 0.9 && scale <= LAppDefine.ViewMaxScale * 1.1 &&
        Number.isFinite(tx) && Math.abs(tx) <= 3.0 &&
        Number.isFinite(ty) && Math.abs(ty) <= 3.0;
      if (!valid) {
        localStorage.removeItem(`${STORAGE_PREFIX}${modelId}`);
        return;
      }
      view.getViewMatrix().setMatrix(new Float32Array(arr));
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

    // §4 fix: Load model via OSS → JSZip → IndexedDB → fetch interceptor
    const ok = await modelLoader.loadModel();
    if (ok && modelLoader.state.value.baseUrl && modelLoader.state.value.model3FileName) {
      const { baseUrl, model3FileName } = modelLoader.state.value;
      console.log(`[Live2D] Loading from: ${baseUrl}${model3FileName}`);
      manager.loadModel(baseUrl!, model3FileName!);
      const ready = await waitModelReady();
      if (ready) {
        activeModelId.value = baseUrl;
        // 持久化用真实 OSS key，不是 virtualBase（见 P1 根因）
        activeModelOssKey.value = modelLoader.state.value.ossKey;
        loadError.value = null;
        isLoaded.value = true;
        manager.getModel()?.centerModel();
        restoreView(baseUrl);
        setupInteractions();
        console.log('[Live2D] Successfully loaded via model loader');
        return;
      }
    }

    loadError.value = modelLoader.state.value.error || '所有 Live2D 模型加载失败';
    console.error('[Live2D] Model load failed:', loadError.value);
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
    modelLoader.cleanup()  // 卸载 fetch 拦截器，防止泄漏
    if (wheelHandler && containerRef.value) {
      containerRef.value.removeEventListener('wheel', wheelHandler);
    }
    if (pointerMoveHandler) window.removeEventListener('pointermove', pointerMoveHandler);
    if (pointerUpHandler) {
      window.removeEventListener('pointerup', pointerUpHandler);
      window.removeEventListener('pointercancel', pointerUpHandler);
    }
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
    activeModelOssKey,
    loadError,
    triggerMotion,
    setMouthOpen,
  };
}
