import { ref, onMounted, onUnmounted, shallowRef } from 'vue';
import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display';

// In Vue 3, avoid making PIXI instances reactive
(window as any).PIXI = PIXI;

export function useLive2DController(modelId: string = 'default') {
  const containerRef = ref<HTMLElement | null>(null);
  const app = shallowRef<PIXI.Application | null>(null);
  const model = shallowRef<Live2DModel | null>(null);
  const isLoaded = ref(false);

  async function initPixi() {
    if (!containerRef.value) return;

    app.value = new PIXI.Application({
      resizeTo: containerRef.value,
      backgroundAlpha: 0,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
    });

    containerRef.value.appendChild(app.value.view as any);

    try {
      // Fetch model3.json. We use local path for Phase 1 as agreed
      // In production, this would be an OSS URL fetched from API
      const modelUrl = `/live2d/${modelId}/Hiyori.model3.json`;

      model.value = await Live2DModel.from(modelUrl);
      app.value.stage.addChild(model.value);

      setupModelTransform();
      setupInteractions();

      isLoaded.value = true;
    } catch (e) {
      console.error("Failed to load Live2D model:", e);
    }
  }

  function setupModelTransform() {
    if (!model.value || !app.value) return;

    // Default centering (Bottom anchored)
    const scale = app.value.screen.height / (model.value.internalModel.height * 1.5);
    model.value.scale.set(scale);

    model.value.x = app.value.screen.width / 2;
    model.value.y = app.value.screen.height;
    model.value.anchor.set(0.5, 1);

    // Restore from localStorage if exists
    const savedState = localStorage.getItem(`eira:live2d:${modelId}`);
    if (savedState) {
      try {
        const parsed = JSON.parse(savedState);
        model.value.x = parsed.x;
        model.value.y = parsed.y;
        model.value.scale.set(parsed.scale);
      } catch (e) {
        // ignore invalid state
      }
    }
  }

  function setupInteractions() {
    if (!model.value) return;

    model.value.eventMode = 'static';
    model.value.cursor = 'grab';

    let isDragging = false;
    let pointerStartX = 0;
    let pointerStartY = 0;
    let modelStartX = 0;
    let modelStartY = 0;

    model.value.on('pointerdown', (e: any) => {
      isDragging = true;
      model.value!.cursor = 'grabbing';
      pointerStartX = e.global.x;
      pointerStartY = e.global.y;
      modelStartX = model.value!.x;
      modelStartY = model.value!.y;
    });

    model.value.on('pointermove', (e: any) => {
      if (!isDragging) return;
      const dx = e.global.x - pointerStartX;
      const dy = e.global.y - pointerStartY;

      model.value!.x = modelStartX + dx;
      model.value!.y = modelStartY + dy;
    });

    model.value.on('pointerup', saveState);
    model.value.on('pointerupoutside', saveState);

    function saveState() {
      isDragging = false;
      model.value!.cursor = 'grab';
      localStorage.setItem(`eira:live2d:${modelId}`, JSON.stringify({
        x: model.value!.x,
        y: model.value!.y,
        scale: model.value!.scale.x
      }));
    }

    // Zoom via wheel
    if (containerRef.value) {
      containerRef.value.addEventListener('wheel', (e) => {
        if (!model.value) return;

        const delta = -Math.sign(e.deltaY) * 0.05;
        let newScale = model.value.scale.x * (1 + delta);

        // Clamp 0.3x - 3x
        newScale = Math.max(0.3, Math.min(3, newScale));
        model.value.scale.set(newScale);
        saveState();
      }, { passive: true });
    }
  }

  function triggerMotion(groupName: string, index?: number) {
    if (model.value) {
      model.value.motion(groupName, index);
    }
  }

  function setMouthOpen(value: number) {
    // Advanced access using any to bypass strict typing for pixi-live2d-display core model structure
    const internalModel = model.value?.internalModel as any;
    if (internalModel?.coreModel?.setParameterValueById) {
      internalModel.coreModel.setParameterValueById("ParamMouthOpenY", Math.min(1, value * 1.4));
    }
  }

  onMounted(() => {
    // Wait for Cubism core script to be available globally before init
    const checkCubism = setInterval(() => {
      if ((window as any).Live2DCubismCore) {
        clearInterval(checkCubism);
        initPixi();
      }
    }, 100);
  });

  onUnmounted(() => {
    if (app.value) {
      app.value.destroy(true, { children: true, texture: true, baseTexture: true });
    }
  });

  return {
    containerRef,
    isLoaded,
    triggerMotion,
    setMouthOpen
  };
}
