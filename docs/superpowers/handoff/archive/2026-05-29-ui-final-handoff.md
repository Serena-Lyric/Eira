# 前端响应式与功能完善 · 最终交接 (2026-05-29)

> **状态更新：2026-06-02** — 以下为原始交接内容与当前实际代码状态的综合对比。
> 
> **🔒 UI 定档声明：所有前端 UI 界面已于 2026-06-02 正式定档，后续不再修改。** AdminLayout、Dashboard、Chat.vue 及所有组件的当前形态即为最终 UI。后续工作仅聚焦于数据层对接（API 接入、WebSocket 连接、认证流程），不涉及任何视觉或布局变更。

---

## 一、原始完成内容 (2026-05-29)

### 1. 响应式布局优化 (Responsive)

#### 用户端 (User) - 核心适配完成 ✅
- **多终端支持**：
    - **移动端**：移除了固定画布和 scale 模式。页面现在 100% 充满手机屏幕，背景图及 UI 元素（气泡、按钮、输入框）会根据视口宽度动态调整大小。
    - **桌面端**：为了保持沉浸式"导游"感，桌面浏览器中主内容区域限制在 `450px` - `800px` 之间并水平居中，模拟手机显示比例，左右带有微弱边框。
    - **窗口缩放**：任意拉伸浏览器窗口时，底部输入框、快捷问题等会实时重排，不再出现水平滚动条或内容溢出。
- **安全区适配**：顶栏自动躲避刘海屏 (`safe-area-inset-top`)，底栏自动上浮躲避 Home 条。

#### 管理端 (Admin) - 固定比例保真 ✅
- **策略调整**：根据要求，Admin 端移除了流式响应式逻辑，回归到 **1920x1080 固定高保真比例** 配合 `transform: scale()` 的模式。这保证了在任何分辨率的电脑屏幕上，管理看板的元素尺寸、间距、圆角都与设计稿完全一致。

### 2. 管理端 (Admin) 功能与视觉细节修复 ✅

- **布局自动扩展**：
    - **修复**：修正了左右栏收起后中间 Live2D 区的偏移问题。
    - **逻辑**：左栏收缩时，中间区无缝向左平移填充空间；右栏收缩时，中间区无缝向右平移填充空间。
    - **动画**：修复了右栏收入动画方向错误的问题（现在向右侧滑动滑出屏幕）。
- **视觉修复**：
    - **圆角一致性**：左栏"神里绫华"底部磨砂玻璃增加了左右下角的 `14px` 圆角；右侧"官方导游"图片的溢出边缘已修复。
    - **字体样式**：移除了 Live2D 模型名称点击时的蓝色下划线及默认链接样式。
- **交互完善**：
    - **词云增强**：卡片内词云按权重（关注度）分布；展开后采用**中心放射状点阵布局**，最核心、字号最大的词位于正圆心，次要词向外扩散。
    - **服务建议回复系统**：点击大卡片展开后，每一条建议右侧都有"回复"按钮。点击后会在下方平滑展开（`slide-down` 动画）一个磨砂回复输入框。
- **API 配置页**：
    - 完成了导航切换到 API 配置页面的设计。
    - 迁移了原有的 LLM/TTS 设置，并新增了 ASR、Embedding、Web Search 等后台驱动参数的配置入口。

### 3. 用户端 (User) 功能新增 ✅

- **设置面板增强**：
    - **意见反馈**：在偏好设置的最下方，新增了"意见反馈"文本域与发送按钮，允许用户提交建议。
    - **背景模糊开关**：设置中增加了实时模糊开关，开启后背景应用高强度 `blur`，模拟单反大光圈景深。
- **文件上传预留**：底部输入框 `+` 按钮已完成文件选择器绑定，并预留了 `POST /api/v1/messages/attachments` 接口调用点。

---

## 二、当前代码状态 (2026-06-02 实际盘点)

### 总体评估：**UI 已定档**，视觉层完成度 100%。数据层全为 Mock，后续仅做后端对接。

---

### 2.1 packages/ui-shared/ — 🔒 已定档（简化为 stub）

**当前状态**：`ui-shared` 包已精简为最小 stub。所有组件导出为返回 null 的占位符，`useWebSocket` 提供空实现。各应用页面的玻璃拟态效果通过内联样式自行实现，不依赖此包。

**定档说明**：Login 等页面中 GlassCard / GlassButton 的引用由各页面自行处理样式，ui-shared 不再提供共享组件。后续如需复用，在各应用内部抽取，不动此包。

---

### 2.2 apps/web-admin/ — 🔒 UI 已定档 + 全静态数据

#### 文件清单（7 个 Vue 文件）
| 文件 | 行数 | 状态 |
|---|---|---|
| `App.vue` | 最小 | `<router-view />` 壳 |
| `layouts/AdminLayout.vue` | 20 行 | 🔒 定档：`<NConfigProvider>` + `<RouterView />`，无侧边栏导航 |
| `pages/Login.vue` | 52 行 | 🔒 定档：登录表单 |
| `pages/Dashboard.vue` | 499 行 | 🔒 定档：内联三视图单体 SFC（dashboard / api / settings） |
| `pages/Content/Personas.vue` | 中等 | 🔒 定档：NDataTable + 模拟数据 |
| `pages/Content/Knowledge.vue` | 中等 | 🔒 定档：NDataTable + NUpload + 模拟数据 |
| `pages/Content/Live2D.vue` | 中等 | 🔒 定档：NDataTable + NUpload + 模拟数据 |

#### 定档说明
- **AdminLayout.vue**：当前仅作为 NConfigProvider 容器，不提供侧边栏 / 菜单 / 导航。此为最终形态，不恢复导航结构。
- **Dashboard.vue**：三个视图（运营看板 / API 配置 / 系统设置）全部内联实现，使用手写 SVG 图表（非 echarts），所有数据为硬编码。此为最终 UI 形态。
- **认证守卫已注释**：`router.beforeEach` 禁用 —— 后续对接后端时启用，不改 UI。

---

### 2.3 apps/web-user/ — 🔒 UI 已定档 + 全 Mock 数据

#### 文件清单（10 个 Vue 文件）
| 文件 | 状态 |
|---|---|
| `App.vue` | 最小 `<router-view />` 壳 |
| `pages/Chat.vue` | 🔒 定档：426 行自包含单体，所有 UI 逻辑内联 |
| `pages/Login.vue` | 🔒 定档：登录表单 |
| `components/CameraMiniWindow.vue` | 🔒 定档：独立摄像头 PIP 组件（Chat.vue 自行内联实现） |
| `components/CharacterSpeechBubble.vue` | 🔒 定档：独立对话气泡组件（Chat.vue 自行内联实现） |
| `components/ChatInputArea.vue` | 🔒 定档：独立输入栏组件（Chat.vue 自行内联实现） |
| `components/QuickQuestionPanel.vue` | 🔒 定档：独立快捷问题组件（Chat.vue 自行内联实现） |
| `components/SettingsPanel.vue` | 🔒 定档：独立设置面板组件（Chat.vue 自行内联实现） |
| `components/TopSettingsButton.vue` | 🔒 定档：独立设置按钮组件（Chat.vue 自行内联实现） |
| `components/Live2DCanvas.vue` | 🔒 定档：Live2D 画布占位符 |

#### 定档说明
- **Chat.vue 采用内联模式**：所有 UI（对话气泡、输入栏、快捷问题、设置面板、摄像头窗口）直接在 Chat.vue 中实现，不引用 `components/` 下的子组件。7 个子组件作为独立参考保留，但不强制接入。**Chat.vue 当前形态即为最终 UI，不做组件化拆分。**
- **三个 Composable 保留**：`useChatSession`、`useLive2DController`、`useActionParser` 已完整实现，留待后续数据层对接时在 Chat.vue 的 `<script>` 中调用 —— 不改 template/CSS。

#### Chat.vue 当前功能清单
- 背景图展示 + 模糊切换
- 设置覆盖层（背景替换 / 模糊 / 语音 / 摄像头模式 / UI 位置 / 意见反馈）
- 模拟对话气泡（打字机效果，3 条固定回复随机返回）
- 快捷问题按钮（触发 mock 回复）
- 输入栏（语音按钮模拟 / 附件上传预留 / 发送触发 mock）
- 画中画摄像头窗口（`getUserMedia` 已注释，显示"API预留"）
- 桌面端响应式（>=1024px 适配）+ 安全区适配

#### Live2D 资产缺失
- `public/live2d/Hiyori/` 目录仅含 `Hiyori.model3.json`
- 缺失 `.moc3` / 纹理 PNG / `.physics3.json` / `.motion3.json`（**属于资源补充，非 UI 修改**）

---

## 三、基础设施对比（UI 定档后）

| 维度 | 原交付 (05-29) | 当前定档 (06-02) |
|---|---|---|
| **ui-shared 组件** | 4 个玻璃拟态组件 + CSS tokens | 🔒 简化为 stub，各页面自行实现样式 |
| **Admin 布局** | 完整侧边栏 + 菜单 + 导航 | 🔒 NConfigProvider 空壳，无导航 |
| **Admin 图表** | 计划使用 echarts | 🔒 手写 SVG，不引入 echarts |
| **Admin 数据** | 部分硬编码 | 🔒 全部硬编码，后续 API 对接 |
| **User 组件化** | Chat.vue 使用子组件 | 🔒 Chat.vue 全部内联，不拆分 |
| **User 数据** | 部分 Mock | 🔒 全部 Mock，后续 WebSocket 对接 |
| **WebSocket** | useChatSession 预留 | 🔒 Composable 已实现，待接入 |
| **Live2D 渲染** | useLive2DController 预留 | 🔒 Controller 已实现，待接入 + 补资产 |
| **摄像头** | 预留 | 🔒 getUserMedia 注释，待启用 |
| **认证守卫** | 有 | 🔒 已注释，待后端对接后启用 |
| **Token 刷新** | 无 | 🔒 待实现（纯逻辑，无 UI 影响） |
| **测试** | 无 | 🔒 待编写（不影响 UI） |
| **路由结构** | 完整 | ✅ 5 条 admin + 3 条 user |
| **Auth Store** | 基础 login/logout | ✅ localStorage + Axios 拦截器 |
| **HTTP 服务** | Axios 实例 | ✅ Bearer token 注入 |
| **UI 视觉效果** | 完整 | ✅ 玻璃拟态 / 动画 / 响应式 / 安全区 |

---

## 四、后续工作（仅数据层 / 后端对接，不动 UI）

> 🔒 以下所有任务均在 `<script>` 或后端层面完成，**禁止修改任何 `.vue` 文件的 `<template>` 和 `<style>` 部分**。UI 视觉形态已冻结。

### P0 — 认证与基础通信
1. **启用认证守卫**：恢复 `router.beforeEach`，连接后端 `/api/auth/login`，让 token 生效但不改 Login 页面 UI
2. **实现 Token 刷新**：Axios 响应拦截器 → 401 自动用 refreshToken 换新 accessToken（纯逻辑）
3. **Auth Store 补全**：`login` 方法增加用户信息解码；`logout` 增加后端通知（纯逻辑）

### P1 — 核心数据对接
4. **连接 useChatSession**：在 Chat.vue `<script>` 中调用 `useChatSession`，替换 `mockBackendResponse`，接入 WebSocket 实时对话（只改 JS 逻辑）
5. **连接 useLive2DController**：在 Chat.vue `<script>` 中调用 `useLive2DController`，初始化 PIXI 应用 + 加载模型（只改 JS 逻辑）
6. **连接 useActionParser**：在 Chat.vue `<script>` 中监听 WebSocket `agent.action` 消息，解析动作标签并触发 Live2D 动作
7. **Admin Dashboard 数据接入**：替换 Dashboard.vue `<script>` 中的硬编码数据为 API 调用（运营指标 / FAQ / 满意度 / 词云 / 情感分析）
8. **Admin 内容管理页数据接入**：Personas / Knowledge / Live2D 三个页面从 mock 数据切换为真实 API 调用

### P2 — 补充与完善
9. **补充 Live2D 模型资产**：下载 Hiyori 的 `.moc3` / 纹理 PNG / `.physics3.json` / `.motion3.json` 放入 `public/live2d/Hiyori/`（纯资源文件）
10. **启用摄像头**：在 Chat.vue `<script>` 中恢复 `getUserMedia` 调用，对接 CameraMiniWindow 逻辑
11. **Admin API 配置页对接**：LLM / TTS / ASR / Embedding / Web Search 设置表单与后端配置 API 双向绑定
12. **编写测试**：利用已配置的 vitest + @vue/test-utils + happy-dom（不涉及 UI 修改）

### ❌ 明确排除的事项
- ~~恢复 ui-shared 组件~~ → 不恢复，各页面自行处理
- ~~恢复 AdminLayout 导航~~ → 不恢复，当前空壳为最终形态
- ~~Chat.vue 组件化拆分~~ → 不拆分，内联模式为最终形态
- ~~echarts 集成~~ → 不引入，手写 SVG 为最终形态
- ~~修改任何 .vue 的 template 或 style~~ → 全面冻结

---

## 五、验证与启动

Admin 管理端：`pnpm --filter web-admin dev` → **http://localhost:5174/**
User 用户端：`pnpm --filter web-user dev` → **http://localhost:5173/**

当前可验证的交互：
1. **User 页面**：设置面板（背景模糊 / 摄像头模式 / UI 位置切换）、模拟对话、快捷问题
2. **Admin 页面**：三视图切换（Dashboard / API 配置 / 系统设置）、左右面板折叠、卡片展开、回复框、日期选择器、模型选择器下拉
3. **内容管理页**：Personas / Knowledge / Live2D 资产表格（需手动输入 URL 导航）
