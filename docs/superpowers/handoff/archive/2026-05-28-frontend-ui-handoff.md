# 前端后续接力指南 (Handoff & Next Steps)

## 当前完成状态 (Phase 1 Frontend Layout)

至此，User端与Admin端两套 UI 均已依据视觉稿与《2026-05-26 架构设计》高保真实现。

### User端 (`apps/web-user/src/pages/Chat.vue`)
*   完成所有交互按键、设置面板、上传入口的预留。
*   完成了深色陪伴感夜景氛围、组件自适应收缩、玻璃拟态重构。
*   默认背景已经集成。

### Admin端 (`apps/web-admin/src/pages/Dashboard.vue` 及 Layout)
*   移除了 Layout 中多余的左侧/顶部导航条，保证中心上方唯一导航入口生效。
*   文案已调整：“人物形象管理”及对应的英文翻译，符合当前系统的主题定位。
*   **左侧侧边栏深度优化**：不再仅仅是压扁，而是实现了完整的移出视口并仅在边缘露出一小截把手的“彻底隐藏 (Edge Peek)”模式。模型选择也换成了两个带圆角矩形的卡片水平并列，带名字毛玻璃遮罩。
*   **右侧数据面板交互与功能升级**：
    *   同样实现了“彻底隐藏 (Edge Peek)”的把手收缩模式，支持将中央大屏放大到极致。
    *   顶部引入了自定义日期范围下拉组件（Mock 渲染的网格型玻璃日历）。
    *   满意度图表升级为精准对应数据点与光影渐变的折线连点 SVG 区域图。
*   **中央区域布局升级**：中央的 Live2D 展示区被明显缩窄（仅比动作栏略宽），使得两边的侧边栏能占用更大区域并展示更多控制选项。
*   **系统设置页**：通过顶部导航直接切换至强效玻璃白卡包裹的全局系统设置页。

---

## 下一步工作项 (Next Steps)

### 1. 完善跨平台端响应适配
*   **User端横屏适配**：需要在后续使用 `window.innerWidth > window.innerHeight` 增加一套 CSS `@media` 查询规则，重排版布局以适应手机横屏与平板。
*   目前 Admin 端使用了基于 Scale 的强制等比缩放方案 (`transform: scale()`) 来保真 1920x1080。在后续真实接管大屏数据时，需讨论是否改用 Grid 或 Flex 响应式弹性换行方案。

### 2. Live2D SDK 对接
*   中间的 `.avatar-preview-container` 和 `.sdk-placeholder` 需要替换为 `<canvas>`。
*   需引入 `@pixi/live2d-display` 等依赖包。
*   通过组件或 Composable 连接底部的药丸按钮（动作预览、表情调试等），触发模型的 Motion。

### 3. 图表与后端联调
*   废弃 Dashboard 右侧卡片中的假 SVG 画布及自定义日历，通过 `vue-echarts` 以及第三方日期选择器 (如 naive-ui 的 date-picker) 集成真实图表与操作。
*   连通右上角的 JWT 校验流程与用户头像展示。
*   开始研发 `chat-pipeline-text` 和 `voice-streaming` 等后端业务模块。