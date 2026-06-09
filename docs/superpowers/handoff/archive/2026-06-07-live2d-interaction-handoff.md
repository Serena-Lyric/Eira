# Eira Live2D 交互修复交接 (2026-06-07)

> 本次会话专项：彻底修复 web-user / web-admin 两端 Live2D 的**中心缩放、悬停门控、平移、默认居中**问题。
> 上游基线：[2026-06-06-current-state-handoff.md](./2026-06-06-current-state-handoff.md)。
> 关键改动均为**几何/矩阵层面根因修复**，非表面调参。配套记忆：`memory/frontend-optimization-2026-06-06.md`「Live2D 缩放/平移彻底修复」。

---

## 一、本次解决的问题（用户报告）

| # | 现象 | 端 |
|---|------|----|
| 1 | 缩放未以模型中心进行，缩放时中心垂直/水平偏移 | admin（user 同源） |
| 2 | 缩放过程中光标脱离模型、手势未放开就「脱离控制」中断 | 两端 |
| 3 | 模型停在左下角，只能看到角色右半边帽子 | admin |
| 4 | 无法左右平移（但缩放后又能动），缩放后模型飞出屏幕 | user |
| 5 | 指针未落在模型上也能触发拖拽/缩放（更早一轮已修，本轮保留） | 两端 |

---

## 二、根因与修复

### A. 缩放中心偏移（问题 1）
- **根因**：`lappview.ts:zoomByCenter(factor)` 用 viewMatrix 平移项 `vm[12],vm[13]` 作 `adjustScale` 锚点。该点等于「模型屏幕中心」**仅当模型中心位于 view-logical 原点 (0,0)**。admin 之前用 `centerModel(1.8, -0.1)` 把中心放到 `(0,-0.1)`，锚点偏了 `vm[5]×(-0.1)` → 缩放垂直漂移。
- **修复**：admin `useLive2DPreview.ts` 的 `loadModel` 改回 `centerModel()`（原点、width=2.0）。

### B. admin 模型错位在左下角（问题 3）
- **根因**：`lapplive2dmanager.ts:onUpdate` 竖屏分支**每帧**强制 `getModelMatrix().setWidth(2.0)`，把 `centerModel(1.8,…)` 设的 1.8 宽度 clobber 掉，但平移量仍按 1.8 计算 → 错位。
- **修复**：统一 width=2.0（与 onUpdate 强制值一致），随 A 一并解决。

### C. user 无法左右平移、缩放后出屏（问题 4）
- **根因**：平移 clamp（`adjustTranslate`）用对称固定边界 `±3`。横向可动域 = `scale×maxRight − ratio`，宽屏 ratio≈1.8~2.6 时 scale=1 横向余量≈0（死），放大后才有空间——与症状完全吻合。
- **修复**：两端 `lappview.ts:initialize` 将 `setMaxScreenRect` 改为 **ratio 追踪**：
  ```
  panMargin = 2.0
  setMaxScreenRect(-(ratio+panMargin), ratio+panMargin, -(1+panMargin), 1+panMargin)
  ```
  横竖等量余裕。`lappdefine.ts` 的 `ViewLogicalMax*` 常量废弃保留（已加注释）。

### D. 手势中途「脱离控制」（问题 2）
- **根因**：wheel arm 的空闲解除阈值 220ms 太短，trackpad/滚轮 notch 停顿会超过它，中途 `wheelArmed=false` → 下一 tick 重新命中判定，光标已离开缩小后的模型 → 中断。
- **修复**：两端阈值 220ms → **500ms**。

### E. 坏状态持久化（问题 4 的持久化面）
- **根因**：user `restoreView` 从 localStorage 恢复旧矩阵，可能是历史「出屏/偏移」坏值，每次加载复活。
- **修复**：恢复前做合法性校验——`scale∈[min×0.9, max×1.1]`、`|tx|,|ty|≤5`，越界则 `removeItem` 并回退默认居中。

### F. 门控机制（问题 5，本轮保留并强化）
- 像素级 alpha 命中：`lappglmanager.ts` 两端 webgl2 context 加 `preserveDrawingBuffer:true`；`isPointerOverCharacter` 读指针处 drawing buffer 像素（CSS→buffer 坐标，Y 反转），`alpha>16` 命中。
- **手势级锁定**：手势开始（pointerdown / 首个 wheel tick / pinch 首指）命中判定一次即锁定，手势进行中不再检测；松开（pointerup / 滚轮停 500ms）后下次重新检测。

---

## 三、改动文件清单

| 文件 | 改动 |
|------|------|
| `apps/web-user/src/live2d/lappview.ts` | 新增 `zoomByCenter()`；`initialize` 平移边界改 ratio 追踪 |
| `apps/web-admin/src/live2d/lappview.ts` | 同上 |
| `apps/web-user/src/live2d/lappglmanager.ts` | webgl2 context 加 `preserveDrawingBuffer:true` |
| `apps/web-admin/src/live2d/lappglmanager.ts` | 同上 |
| `apps/web-user/src/live2d/lappmodel.ts` | `centerModel(width=2.0, offsetY=0.0)` 参数化 |
| `apps/web-admin/src/live2d/lappmodel.ts` | 同上 |
| `apps/web-user/src/live2d/lappdefine.ts` | `ViewLogicalMax*` 标注废弃保留 |
| `apps/web-admin/src/live2d/lappdefine.ts` | 同上 |
| `apps/web-user/src/composables/useLive2DController.ts` | 像素命中 + 手势锁定 + pinch + restoreView 校验 |
| `apps/web-admin/src/composables/useLive2DPreview.ts` | 像素命中 + 手势锁定 + pinch + `centerModel()` 复位 |

> `lappdefine.ts` 的 `ViewLogicalMax*` 已不被引用，但作为导出常量保留以防外部依赖。

---

## 四、交互行为现状（两端一致）

| 操作 | 桌面 | 移动 |
|------|------|------|
| 平移 | 左键按住角色拖拽 | 单指按住角色拖拽 |
| 缩放 | 滚轮（需先悬停角色 arm） | 双指 pinch |
| 缩放锚点 | 模型中心（不漂移、不出屏） | 同 |
| 门控 | 命中角色不透明像素才触发，手势内锁定 | 同 |
| 状态持久化 | user 端存 localStorage（`eira:live2d:<modelId>`，含合法性校验）；admin 不持久化 | — |

---

## 五、可调参数（如需微调手感）

| 参数 | 位置 | 当前值 | 调大效果 |
|------|------|--------|----------|
| `panMargin` | 两端 `lappview.ts:initialize` | `2.0` | 平移余裕更大 |
| wheel 释放阈值 | 两端 composable `wheelIdleTimer` | `500` ms | 连续滚动更「粘」，间隔久也不重判 |
| alpha 命中阈值 | 两端 composable `isPointerOverCharacter` | `px[3] > 16` | 命中更严（边缘飘发更难触发） |
| 缩放步进 | 两端 composable `wheelHandler` | `1.1` / `1/1.1` | 每格缩放更猛 |

---

## 六、验证门禁

```bash
pnpm --filter @eira/web-user exec vue-tsc --noEmit    # 0 errors ✅
pnpm --filter @eira/web-admin exec vue-tsc --noEmit   # 0 errors ✅
```

> 本次仅改前端 Live2D 交互层，未触后端。两端类型检查均通过。

### 人工回归建议
1. **user 端先清 localStorage**（或换模型触发新 key），确认历史出屏矩阵不再复活。
2. 桌面：悬停角色滚轮缩放 → 中心不漂移、不出屏；缩小后左右拖拽仍可动。
3. 移动/触屏：双指 pinch 中心缩放；单指拖拽。
4. admin：模型默认居中于中间栏（非左下角）；缩放锚点稳定。
5. 缩放过程中光标滑出模型但不停滚轮 → 不中断（500ms 内）。

---

## 七、遗留 / 注意

- `preserveDrawingBuffer:true` 使 `readPixels` 读上一帧画面，命中判定有 1 帧延迟，对静态判定无影响；理论上有轻微合成开销，实测可忽略。
- 命中判定每次 wheel arm / pointerdown 各读 1 像素，开销极小。
- admin 端目前不持久化视图矩阵（刷新回默认居中），如需持久化可参照 user 端 `saveView`/`restoreView`（含校验）移植。
- `ViewLogicalMax*` 常量已无引用，未来可安全删除。
