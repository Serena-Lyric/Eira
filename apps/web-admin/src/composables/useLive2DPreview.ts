import { ref, onMounted, onUnmounted } from 'vue'
import { LAppDelegate } from '../live2d/lappdelegate'
import * as LAppDefine from '../live2d/lappdefine'
import { createLive2DLoader } from '@shared/live2d/live2dLoader'
import type { ExtractedModel, BlobBase } from '@shared/live2d/live2dLoader'

const loader = createLive2DLoader()

/**
 * Live2D 预览控制器（管理端专用，基于官方 Cubism SDK for Web 5 Framework）。
 *
 * 与管理端的 Live2D 渲染区（Dashboard 中间栏）集成，提供模型加载、
 * 切换、拖拽平移、滚轮缩放等预览功能。
 *
 * 与 web-user 的 useLive2DController 差异：
 * - 无 Chat/Action 桥接
 * - 支持模型热切换（changeModel）
 * - 简化初始化流程
 * - 支持自定义待机动作覆盖
 */

/** 模型描述符 — 增加预览图、显示名称、动作探测元数据 */
export interface ModelDescriptor {
  id: string
  label: string
  dir: string
  fileName: string
  /** 预览图（相对路径，用于 persona card） */
  previewImage?: string
  /** 显示名称（从 vtube.json / 目录名解析） */
  displayName?: string
  /** OSS key，用于 changeModel 匹配，如 "live2d/8767b36fcc6c/mao_pro_zh.zip" */
  ossKey?: string
  /** 从 vtube.json 探测到的动作文件列表（model3.json 无 Motions 时使用） */
  discoveredMotions?: Array<{ group: string; index: number; label: string; file: string }>
}

// §4 fix: Hardcoded ADMIN_MODEL_REGISTRY removed — models now fetched from
// backend asset list via fetchAvailableModels().

const LOAD_TIMEOUT_MS = 8000

export function useLive2DPreview() {
  const containerRef = ref<HTMLElement | null>(null)
  const isLoaded = ref(false)
  const activeModelId = ref<string | null>(null)
  const loadError = ref<string | null>(null)

  // ── 模型信息列表（含预览图、显示名称） ──────────────────────────────
  // §4 fix: Fetch from backend asset list instead of hardcoded registry
  const availableModels = ref<ModelDescriptor[]>([])

  /** 当前模型的自定义待机动作覆盖（null=使用默认"Idle"组随机播放） */
  const idleMotionOverride = ref<{ group: string; index: number } | null>(null)

  /** 从已加载模型中解析可用的动作列表 */
  const availableMotions = ref<Array<{ group: string; index: number; label: string }>>([])

  /** 解析模型的显示名称、预览图、以及 vtube.json / animations 下的动作文件。
   *  model3.json 无 Motions 的模型（VTube Studio 导出）通过此途径发现动作。
   *  每个模型独立探测，避免跨模型污染。
   */
  async function resolveModelMeta() {
    // 按模型目录结构分组探测，避免误读到其他模型的动作文件
    const probeMap: Record<string, string[]> = {
      akari_vts: [
        'animations/Idle_2.motion3.json',
        'animations/Love.motion3.json',
        'animations/Shock.motion3.json',
      ],
      hiyori_vts: Array.from({ length: 10 }, (_, i) =>
        `animations/hiyori_m${String(i + 1).padStart(2, '0')}.motion3.json`,
      ),
      PinkHair_workshop_2802653785: [],
      mao_pro_zh: [],     // model3.json 有 Motions，无需探测
      hiyori_pro_zh: [],  // model3.json 有 Motions，无需探测
    }

    for (const m of availableModels.value) {
      // ── vtube.json 读取 Name + Icon + IdleAnimation ──
      const baseName = m.fileName.replace('.model3.json', '')
      const vtubeCandidates = [
        `${baseName}.vtube.json`,
        'akari.vtube.json',
        'hiyori.vtube.json',
        'yiyi_chair.vtube.json',
        'hiyori_pro_t11.vtube.json',
        'mao_pro.vtube.json',
      ]
      let vtubeJson: any = null
      for (const vf of vtubeCandidates) {
        try {
          const vResp = await fetch(`${m.dir}${vf}`)
          if (!vResp.ok) continue
          vtubeJson = await vResp.json()
          break
        } catch { /* 该候选不存在，继续 */ }
      }

      if (vtubeJson) {
        if (vtubeJson?.Name) m.displayName = vtubeJson.Name
        if (vtubeJson?.FileReferences?.Icon) {
          m.previewImage = `${m.dir}${vtubeJson.FileReferences.Icon}`
        }
      }
      if (!m.displayName) m.displayName = m.label

      // ── 动作探测：仅探测当前模型目录下的已知文件 ──
      const probes = probeMap[m.label] || []
      const discovered: ModelDescriptor['discoveredMotions'] = []
      for (const probe of probes) {
        try {
          const probeResp = await fetch(`${m.dir}${probe}`)
          if (probeResp.ok) {
            // 从路径提取组名和标签
            const fileName = probe.replace(/^.*[/]/, '').replace('.motion3.json', '')
            // 尝试按命名拆分 group（如 Idle_2 → group=Idle, idx=2）
            const match = fileName.match(/^(.+?)_(\d+)$/)
            const group = match ? match[1] : 'Animation'
            const idx = match ? parseInt(match[2], 10) : discovered.length
            discovered.push({
              group,
              index: idx,
              label: fileName,
              file: probe,
            })
          }
        } catch { /* 探测不到 */ }
      }
      if (discovered.length > 0) {
        m.discoveredMotions = discovered
      }
    }
  }

  /** §4 fix: Fetch available Live2D models from backend asset list */
  async function fetchAvailableModels() {
    try {
      const { assetApi } = await import('../services/api')
      const assets = await assetApi.list()
      const live2dModels = assets.filter((a: any) => a.kind === 'live2d_model')
      availableModels.value = live2dModels.map((a: any) => ({
        id: a.name,           // Match by display name
        label: a.name,
        dir: '',              // Will be resolved at load time via shared loader
        fileName: '',
        ossKey: a.oss_key || '',
        _ossKey: a.id,        // Asset ID for download endpoint
        _ossKeyStr: String(a.id),  // String form for matching by asset ID
      }))
    } catch {
      console.warn('[Live2D Admin] Failed to fetch models from backend')
    }
  }

  function refreshAvailableMotions() {
    const model = delegate?.getSubdelegate()?.getLive2DManager()?.getModel()
    if (!model || !(model as any)._modelSetting) {
      availableMotions.value = []
      return
    }
    const setting = (model as any)._modelSetting
    const motions: Array<{ group: string; index: number; label: string }> = []
    const groupCount = setting.getMotionGroupCount() || 0
    for (let g = 0; g < groupCount; g++) {
      const groupName = setting.getMotionGroupName(g) as string
      // 过滤空字符串组名（如 mao_pro_zh 的 "" 组）
      if (!groupName || groupName.trim() === '') {
        continue
      }
      const motionCount = setting.getMotionCount(groupName) || 0
      for (let m = 0; m < motionCount; m++) {
        motions.push({
          group: groupName,
          index: m,
          label: `${groupName}_${m}`,
        })
      }
    }

    // model3.json 没有 Motions → 使用 vtube.json 探测到的动作
    if (motions.length === 0) {
      const desc = availableModels.value.find((m) => m.id === activeModelId.value)
      if (desc?.discoveredMotions && desc.discoveredMotions.length > 0) {
        for (const dm of desc.discoveredMotions) {
          motions.push({ group: dm.group, index: dm.index, label: dm.label })
        }
      }
    }

    availableMotions.value = motions
  }

  /** 将选中的待机动作应用到当前模型 */
  async function applyIdleMotionToModel(group: string | null, index: number | null) {
    const model = delegate?.getSubdelegate()?.getLive2DManager()?.getModel()
    if (!model) return
    if (group != null && index != null) {
      idleMotionOverride.value = { group, index }
      // 注册并预加载外部动作文件（VTube Studio 导出模型）
      const desc = availableModels.value.find((m) => m.id === activeModelId.value)
      if (desc?.discoveredMotions) {
        for (const dm of desc.discoveredMotions) {
          ;(model as any).addDiscoveredMotionPath?.(dm.group, dm.index, dm.file)
        }
        // 预加载选中的动作，否则 startMotion 异步 fetch 导致首次调用必然失败
        const target = desc.discoveredMotions.find(
          (dm) => dm.group === group && dm.index === index,
        )
        if (target) {
          await (model as any).preloadMotionByPath?.(group, index, target.file)
        }
      }
      ;(model as any).setIdleMotion?.(group, index)
    } else {
      idleMotionOverride.value = null
      ;(model as any).setIdleMotion?.(null, null)
    }
  }

  let delegate: LAppDelegate | null = null
  let canvas: HTMLCanvasElement | null = null
  let wheelHandler: ((e: WheelEvent) => void) | null = null
  let pointerDownHandler: ((e: PointerEvent) => void) | null = null
  let pointerMoveHandler: ((e: PointerEvent) => void) | null = null
  let pointerUpHandler: ((e: PointerEvent) => void) | null = null

  function waitForCubismCore(): Promise<void> {
    return new Promise((resolve) => {
      if ((window as any).Live2DCubismCore) {
        resolve()
        return
      }
      const timer = setInterval(() => {
        if ((window as any).Live2DCubismCore) {
          clearInterval(timer)
          resolve()
        }
      }, 100)
      setTimeout(() => {
        clearInterval(timer)
        resolve()
      }, 10000)
    })
  }

  function waitModelReady(): Promise<boolean> {
    return new Promise((resolve) => {
      const start = Date.now()
      const timer = setInterval(() => {
        const model = delegate
          ?.getSubdelegate()
          ?.getLive2DManager()
          ?.getModel()
        if (model && model.isCompleteSetup && model.isCompleteSetup()) {
          clearInterval(timer)
          resolve(true)
        } else if (Date.now() - start > LOAD_TIMEOUT_MS) {
          clearInterval(timer)
          resolve(false)
        }
      }, 100)
    })
  }

  function getView() {
    return delegate?.getSubdelegate()?.getView()
  }

  /** 获取当前加载的模型实例。 */
  function getModel() {
    return delegate?.getSubdelegate()?.getLive2DManager()?.getModel()
  }

  // getModel は将来の拡張用に保持。
  void getModel

  /**
   * 指针(clientX, clientY)是否在交互区域内。
   *
   * 改为页面判定：仅判断指针是否在 canvas 所覆盖的中间栏卡片范围内，
   * 不再使用 readPixels 做像素级 alpha 检测。
   */
  function isPointerOverCharacter(clientX: number, clientY: number): boolean {
    if (!canvas) return false
    const rect = canvas.getBoundingClientRect()
    return (
      clientX >= rect.left &&
      clientX <= rect.right &&
      clientY >= rect.top &&
      clientY <= rect.bottom
    )
  }

  function setupInteractions() {
    const container = containerRef.value
    if (!container || !canvas) return

    const pointers = new Map<number, { x: number; y: number }>()
    let dragging = false
    let lastX = 0
    let lastY = 0
    let pinchDist = 0

    let wheelArmed = false
    let wheelIdleTimer: ReturnType<typeof setTimeout> | null = null

    canvas.style.touchAction = 'none'
    canvas.style.cursor = 'grab'

    const overlaySelector = '.settings-overlay, .expand-overlay'
    const dist2 = () => {
      const pts = Array.from(pointers.values())
      const dx = pts[0].x - pts[1].x
      const dy = pts[0].y - pts[1].y
      return Math.hypot(dx, dy)
    }

    pointerDownHandler = (e: PointerEvent) => {
      if (e.pointerType !== 'touch' && e.button !== 0) return
      if (pointers.size === 0 && !isPointerOverCharacter(e.clientX, e.clientY)) return
      e.preventDefault()
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })

      if (pointers.size === 1) {
        dragging = true
        lastX = e.clientX
        lastY = e.clientY
        canvas!.style.cursor = 'grabbing'
        try { canvas!.setPointerCapture(e.pointerId) } catch { /* ignore */ }
      } else if (pointers.size === 2) {
        dragging = false
        pinchDist = dist2()
      }
    }
    pointerMoveHandler = (e: PointerEvent) => {
      if (!pointers.has(e.pointerId) || document.querySelector(overlaySelector)) return
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })

      if (pointers.size >= 2) {
        const d = dist2()
        if (pinchDist > 0 && d > 0) {
          getView()?.zoomByCenter(d / pinchDist)
        }
        pinchDist = d
        return
      }
      if (!dragging) return
      const dx = e.clientX - lastX
      const dy = e.clientY - lastY
      lastX = e.clientX
      lastY = e.clientY
      getView()?.panBy(dx, dy)
    }
    pointerUpHandler = (e: PointerEvent) => {
      pointers.delete(e.pointerId)
      if (pointers.size < 2) pinchDist = 0
      if (pointers.size === 0 && dragging) {
        dragging = false
        if (canvas) canvas.style.cursor = 'grab'
      } else if (pointers.size === 1) {
        const [p] = Array.from(pointers.values())
        dragging = true
        lastX = p.x
        lastY = p.y
      }
    }

    canvas.addEventListener('pointerdown', pointerDownHandler)
    window.addEventListener('pointermove', pointerMoveHandler)
    window.addEventListener('pointerup', pointerUpHandler)
    window.addEventListener('pointercancel', pointerUpHandler)

    wheelHandler = (e: WheelEvent) => {
      if (document.querySelector(overlaySelector)) return
      if (!wheelArmed) {
        if (!isPointerOverCharacter(e.clientX, e.clientY)) return
        wheelArmed = true
      }
      e.preventDefault()
      const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1
      getView()?.zoomByCenter(factor)
      if (wheelIdleTimer) clearTimeout(wheelIdleTimer)
      wheelIdleTimer = setTimeout(() => { wheelArmed = false }, 500)
    }
    container.addEventListener('wheel', wheelHandler, { passive: false })
  }

  function cleanupInteractions() {
    if (wheelHandler && containerRef.value) {
      containerRef.value.removeEventListener('wheel', wheelHandler)
    }
    if (pointerMoveHandler)
      window.removeEventListener('pointermove', pointerMoveHandler)
    if (pointerUpHandler) {
      window.removeEventListener('pointerup', pointerUpHandler)
      window.removeEventListener('pointercancel', pointerUpHandler)
    }
  }

  async function loadModel(desc: ModelDescriptor): Promise<boolean> {
    const manager = delegate?.getSubdelegate()?.getLive2DManager()
    if (!manager) return false

    const assetId = (desc as any)._ossKey
    if (!assetId) {
      console.warn('[Live2D Admin] No asset ID, skipping')
      return false
    }
    console.log(`[Live2D Admin] Loading: ${desc.label} (asset #${assetId})`)

    try {
      // Download via backend streaming endpoint, extract via shared loader
      const dlUrl = `/api/admin/assets/${assetId}/file`
      const extracted: ExtractedModel = await loader.downloadAndExtract(dlUrl, String(assetId), { cache: false })

      // Create virtual base + install fetch interceptor
      const blobBase: BlobBase = loader.createBlobBase(extracted.files, extracted.model3Path)
      loader.installFetchInterceptor(blobBase.virtualBase, extracted.files)

      desc = { ...desc, dir: blobBase.virtualBase, fileName: blobBase.model3FileName }
    } catch (err: any) {
      console.error('[Live2D Admin] Download failed:', err.message)
      return false
    }

    manager.loadModel(desc.dir, desc.fileName)
    const ok = await waitModelReady()
    if (ok) {
      activeModelId.value = desc.id
      loadError.value = null
      isLoaded.value = true
      // 右上方へオフセットし、中間欄カードの中央にモデルを配置
      manager.getModel()?.centerModel(2.0, 0.08, 0.15)
      refreshAvailableMotions()
      if (idleMotionOverride.value) {
        applyIdleMotionToModel(
          idleMotionOverride.value.group,
          idleMotionOverride.value.index,
        )
      }
      console.log(`[Live2D Admin] Loaded: ${desc.label}`)
      return true
    }
    console.warn(`[Live2D Admin] Failed: ${desc.label}`)
    return false
  }

  /** 切换到指定模型。支持匹配：显示名称、asset ID、OSS key 字符串 */
  async function changeModel(modelId: string) {
    const desc = availableModels.value.find((m: any) =>
      m.id === modelId ||
      String(m._ossKey) === modelId ||
      m._ossKeyStr === modelId ||
      m.ossKey === modelId
    )
    if (!desc) {
      console.warn(`[Live2D Admin] Unknown model: ${modelId}`)
      return
    }
    isLoaded.value = false
    loadError.value = null
    activeModelId.value = null
    idleMotionOverride.value = null // 切换模型时重置待机动作覆盖
    const ok = await loadModel(desc)
    if (!ok) {
      loadError.value = `Failed to load: ${desc.label}`
    }
  }

  async function initLive2D() {
    const container = containerRef.value
    if (!container) return

    await waitForCubismCore()

    canvas = document.createElement('canvas')
    container.appendChild(canvas)

    delegate = LAppDelegate.getInstance()
    if (!delegate.initialize(canvas)) {
      loadError.value = 'WebGL 初始化失败'
      return
    }
    delegate.run()

    // §4 fix: Fetch model list from backend before resolving meta
    await fetchAvailableModels()

    // 预解析所有模型的元数据（预览图、显示名称）
    await resolveModelMeta()

    setupInteractions()

    // Load primary model from fetched list (§4 fix)
    if (availableModels.value.length > 0) {
      const primary = availableModels.value[0]
      const ok = await loadModel(primary)
      if (!ok && availableModels.value.length > 1) {
        const fallback = availableModels.value[1]
        const fbOk = await loadModel(fallback)
        if (!fbOk) {
          loadError.value = 'All Live2D models failed to load'
          console.error('[Live2D Admin] All models failed')
        }
      } else if (!ok) {
        loadError.value = 'Live2D model failed to load'
      }
    } else {
      console.warn('[Live2D Admin] No models available from backend')
    }
  }

  onMounted(() => {
    const waitContainer = setInterval(() => {
      if (containerRef.value) {
        clearInterval(waitContainer)
        initLive2D()
      }
    }, 50)
    setTimeout(() => clearInterval(waitContainer), 5000)
  })

  onUnmounted(() => {
    cleanupInteractions()
    LAppDelegate.releaseInstance()
    delegate = null
    if (canvas && canvas.parentElement) {
      canvas.parentElement.removeChild(canvas)
    }
    canvas = null
  })

  return {
    containerRef,
    isLoaded,
    activeModelId,
    loadError,
    availableModels,
    availableMotions,
    fetchAvailableModels,
    refreshAvailableMotions,
    changeModel,
    applyIdleMotionToModel,
  }
}
