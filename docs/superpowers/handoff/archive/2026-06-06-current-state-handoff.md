# Eira 当前状态交接 (2026-06-06)

> 基于 2026-06-04 交接文档的增量更新。本文档是项目当前真实状态的**单一权威入口**。
> **最后更新**: 2026-06-06（第二轮——前端优化 + 后端 API 补全）

---

## 一、总览

| 层 | 技术栈 | 状态 |
|---|---|---|
| 基础设施 | Docker: PostgreSQL16+pgvector / Redis7 / MinIO | ✅ 正常运行 |
| 后端 | FastAPI + SQLAlchemy(async) + LangGraph orchestrator + DeepSeek LLM | ✅ Phase 1 文本对话闭环 + 用户/反馈/语音 API 骨架就绪 |
| 前端 web-user | Vue3 + Pinia + Official Cubism SDK 5 | ✅ UI 定档，认证/WebSocket/API 层完成 |
| 前端 web-admin | Vue3 + NaiveUI + Official Cubism SDK 5 | ✅ UI 定档，认证/API 层完成，Live2D 预览集成 |
| 共享包 | `@eira/ui-shared` (stub) | ⚠️ Glass 组件为 null stub，各 app 内联实现 |

**当前阶段**：Phase 1（文本对话 + Live2D 画布），前端数据层已完成对接准备，后端新增 API 端点已注册（部分为 Phase 2 占位）。

---

## 二、启动指南

### Docker 依赖
```bash
docker compose -f deploy/docker-compose.dev.yml up -d
```

### 后端
```bash
cd backend
EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
EIRA_REDIS_URL=redis://localhost:6379/0 \
EIRA_OSS_ENDPOINT=http://localhost:9000 \
python -m uv run alembic upgrade head

EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
EIRA_REDIS_URL=redis://localhost:6379/0 \
EIRA_OSS_ENDPOINT=http://localhost:9000 \
python -m uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 前端
```bash
pnpm install
pnpm --filter @eira/web-user dev    # http://localhost:5173
pnpm --filter @eira/web-admin dev   # http://localhost:5174
```

### 测试账号
| 地址 | 邮箱 | 密码 |
|------|------|------|
| http://localhost:5173/login | `admin@eira.dev` | `Admin123!` |
| http://localhost:5174/login | `admin@eira.dev` | `Admin123!` |

---

## 三、本次会话 (2026-06-06) 完成内容

### A. 认证体系（P0）

| 项目 | 内容 |
|------|------|
| 认证守卫 | 两个 app 的 `router.beforeEach` 已启用，localStorage key 统一为 `eira:at` / `eira:admin:at` |
| Token 刷新 | `services/http.ts` 添加 401 响应拦截器：自动 refresh → 重试请求，并发请求排队，refresh 失败跳转登录 |
| Auth Store | 引入 `authApi` 服务层，登录后自动调用 `GET /auth/me` 拉取用户信息 |
| Vite 代理 | 代理添加 `rewrite` 规则剥离 `/api` 前缀（后端路由无 `/api` 前缀） |

### B. API 服务层（P1）

**新建文件：**

| 文件 | 说明 |
|------|------|
| `apps/web-user/src/services/types.ts` | 用户端所有 TypeScript 类型定义 |
| `apps/web-user/src/services/api.ts` | 用户端 API 函数（auth / conversation / user / voice / file / feedback） |
| `apps/web-admin/src/services/types.ts` | 管理端所有 TypeScript 类型定义 |
| `apps/web-admin/src/services/api.ts` | 管理端 API 函数（auth / dashboard / persona / knowledge / asset / config） |

### C. 管理端 Live2D 预览（P1）

| 项目 | 说明 |
|------|------|
| Framework | 复制 `live2d-framework/` (59 个 .ts + 内联着色器) 到 web-admin |
| 集成层 | `src/live2d/` 11 个文件（lapp* + touchmanager） |
| Core 运行时 | `public/live2d-core/` + `public/live2d/` (Mao + Hiyori 模型) |
| 预览控制器 | `useLive2DPreview` composable，支持模型切换、拖拽平移、滚轮缩放 |
| 构建配置 | `tsconfig.json` + `vite.config.ts` 添加 `@framework` alias |

### D. 管理端功能修复与对接（P1）

| 修复项 | 说明 |
|--------|------|
| Content 页空白 | Personas / Knowledge / Live2D 的 `<GlassCard>` 替换为本地玻璃拟态 div |
| Dashboard 数据 | 创建 `useDashboard` composable，全部指标/图表/反馈替换为 API 驱动 |
| API 配置页 | LLM/TTS/ASR/Embedding 等所有 select/input 绑定 v-model + 保存按钮 |
| 系统设置页 | 语音持久化 / 文档配额绑定 config composable |
| 认证守卫 | 父路由添加 `meta: { requiresAuth: true }` |

### E. 用户端功能完善（P2）

| 修复项 | 说明 |
|--------|------|
| 摄像头 | 默认关闭；桌面端检测后置摄像头，无则置灰；`muted` 属性修复自动播放；facingMode 回退容错 |
| 对话气泡 | 无内容时自动隐藏（`showBubble` computed） |
| 设置面板 | 防止穿透拖拽/滚轮缩放；添加上传反馈提示 |
| 模型上传 | 设置中新增模型上传模块（支持 .zip / .7z / .rar），含格式验证 + 解析成功提示 |
| 背景上传 | 限制仅图片格式（JPG/PNG/WebP），含验证 + 上传成功提示 |
| 语音录制 | 麦克风按钮接入 MediaRecorder，录制中显示红点，停止后输出 WebM blob |
| 快捷提问开关 | 已移除（与位置设置的隐藏选项冲突） |
| 反馈提交 | 绑定 `feedbackApi.submit()` |

### F. Live2D 交互修复

| 修复项 | 说明 |
|--------|------|
| 拖拽方向 | `panBy` 移除手动 Y 取反，`_deviceToScreen` 矩阵内建映射自动处理 XY 双向 |
| 缩放后定位 | `panBy` 添加 `viewScale` 除数，缩放后拖拽位移与屏幕一致 |
| 滚轮穿透 | 设置面板/展开卡片打开时滚轮不再触发 Live2D 缩放 |
| 模型初始位置 | 管理端加载后 zoom 65% + 向右上微移 |

### G. 第二轮优化 (2026-06-06 #2)

**Live2D 交互深度修复：**

| 修复项 | 说明 |
|--------|------|
| 位置边界扩大 | `ViewLogicalMax*` 从 ±4.0 → ±10.0，解决缩小后拖拽立即触碰 clamp 无法移动 |
| 缩放改为模型中心 | 滚轮缩放原点从鼠标位置改为画布中心（`rect.width/2, rect.height/2`），两个 composable 同步修改 |
| Admin 模型默认位置 | `panBy` 从无效的 `(0.12, 0.08)` CSS 像素改为按画布比例 `(rect.width * 0.15, -rect.height * 0.12)` |

**摄像头修复：**

| 修复项 | 说明 |
|--------|------|
| 视频无法显示 | **根因**: Vue 响应式时序 bug——`v-if/v-else` 导致 video 元素在 `cameraStreamActive=true` 前不存在于 DOM，ref 为空。**修复**: 改用 `v-show` 保持元素在 DOM 中 + watcher 添加 `await nextTick()` |
| 后置摄像头检测 | 权限获取前 `enumerateDevices()` 返回空 label → `hasRearCamera=false`；修复：`startCamera()` 成功后重新调用 `detectCameras()` 即可正确读取 label |
| 默认状态 | 摄像头默认 `'hidden'`（关闭/隐藏），电脑端和手机端均如此 |

**语音输入模式：**

| 模式 | 说明 |
|------|------|
| `click`（默认） | 点击按钮开始录音，再次点击停止并发送到 ASR |
| `persistent` | 常驻监听模式，点击开启持续录音 |
| `smart` | 智能检测——AudioContext + AnalyserNode 实时音量检测，语音开始自动录音，静音 2 秒自动停止 |
| `hidden` | 隐藏模式——麦克风按钮不响应、不可见 |

设置面板中新增"语音输入模式"分段选择器，仅 `showMic=true` 时可见。`voice_input_mode` 已纳入 `UserPreferences` 持久化。

**上传逻辑重构：**

| 上传类型 | 之前 | 现在 |
|----------|------|------|
| 背景上传 | FileReader 完成后立即提示「✓ 已更新」 | 本地预览 → 后端 API 确认 → 成功才提示 ✓；按错误类型（413/400/网络错误/401）展示不同中文提示 |
| 模型上传 | `setTimeout` 模拟成功后提示 | 本地模拟解析 → 后端 API → 双重确认成功才提示；错误码分级处理 |

**意见反馈：**
- `feedbackApi.submit()` 返回 `FeedbackResponse {success, message, feedback_id, created_at}` 而非 void
- `submitFeedback()` 根据 `success` 字段展示成功/错误消息
- 网络错误、401 等按类型给出中文提示

---

## 四、后端新增 API 端点 (2026-06-06 #2)

以下端点已在 `backend/app/api/rest/` 下创建并注册到 `main.py`：

### 4.1 语音 (voice.py)

| 方法 | 路径 | 状态 | 说明 |
|------|------|------|------|
| `POST` | `/voice/tts` | 🟡 Phase 2 占位 | TTS 文本转语音，接收 `{text, voice?, speed?}`，当前返回 501 |
| `GET` | `/voice/asr/config` | 🟡 Phase 2 占位 | 返回 ASR 配置 `{provider, app_id, api_key, websocket_url, enabled}` |

### 4.2 用户反馈 (feedback.py)

| 方法 | 路径 | 状态 | 说明 |
|------|------|------|------|
| `POST` | `/feedback` | ✅ 已实现 | 提交反馈，返回 `{success, message, feedback_id, created_at}`。需认证 |

### 4.3 用户数据 (user.py)

| 方法 | 路径 | 状态 | 说明 |
|------|------|------|------|
| `GET` | `/user/preferences` | 🟡 返回默认值 | 获取用户偏好（含 `voice_input_mode` 字段） |
| `PATCH` | `/user/preferences` | 🟡 占位 | 部分更新用户偏好 |
| `POST` | `/user/background` | ✅ 已实现 | 上传背景图（JPG/PNG/WebP，≤10MB），格式+大小验证，返回 `{success, message, url}` |
| `POST` | `/user/model` | ✅ 已实现 | 上传模型包（.zip/.7z/.rar，≤100MB），格式+大小验证，返回 `{success, message, model_id}` |

> **依赖变更**: `pyproject.toml` 新增 `python-multipart>=0.0.9`。

---

## 五、文件结构快照

### web-user (`apps/web-user/src/`)
```
main.ts                     — 路由 + 认证守卫（已启用）
pages/
  Login.vue                 — 登录表单
  Chat.vue                  — 主页面（UI 内联，~650行）
composables/
  useChatSession.ts         — WebSocket 实时对话
  useLive2DController.ts    — Live2D 渲染控制
  useActionParser.ts        — Action Tag → Live2D Motion
services/
  http.ts                   — Axios + Bearer Token + 401 自动刷新
  api.ts                    — 所有 API 函数
  types.ts                  — TypeScript 类型定义
stores/
  auth.ts                   — Pinia 认证状态
live2d-framework/           — Cubism SDK Framework vendored (59 .ts)
live2d/                     — 集成层 (11 .ts)
components/                 — 7 个 @deprecated 孤立组件
```

### web-admin (`apps/web-admin/src/`)
```
main.ts                     — 路由 + 认证守卫（已启用）
layouts/
  AdminLayout.vue           — NConfigProvider 壳
pages/
  Dashboard.vue             — 三视图单体（运营看板/API配置/系统设置） + Live2D 预览
  Login.vue                 — 登录表单
  Content/
    Personas.vue            — 角色管理（NDataTable + API）
    Knowledge.vue           — 知识库管理（NUpload + NDataTable + API）
    Live2D.vue              — 资产管理（NUpload + NDataTable + API）
composables/
  useDashboard.ts           — 运营数据（API + mock 回退）
  useAppConfig.ts           — 应用配置（API + 默认值回退）
  useLive2DPreview.ts       — Live2D 预览控制
services/
  http.ts                   — Axios + Bearer Token + 401 自动刷新
  api.ts                    — 所有管理端 API 函数
  types.ts                  — 管理端 TypeScript 类型定义
stores/
  auth.ts                   — Pinia 认证状态
live2d-framework/           — Cubism SDK Framework vendored (59 .ts)
live2d/                     — 集成层 (11 .ts)
public/
  live2d-core/              — Cubism Core 运行时 + 着色器
  live2d/                   — mao_pro_zh / hiyori_pro_zh 模型
```

---

## 六、遗留事项

### 🔴 新增依赖
- **`python-multipart`** 已添加到 `backend/pyproject.toml`，需运行 `python -m uv sync` 或在启动时自动安装

### 🟡 中优先级
- **后端管理端 API 未实现**：`/admin/dashboard/*`、`/admin/personas`、`/admin/knowledge`、`/admin/assets`、`/admin/config` — 前端已定义完整类型契约和 API 函数
- **后端 TTS/ASR 实际实现**：`/voice/tts` 和 `/voice/asr/config` 当前为占位，Phase 2 需接入实际 TTS/ASR 引擎
- **用户偏好持久化**：`/user/preferences` GET/PATCH 当前返回默认值，Phase 2 需接入数据库

### 🟢 低优先级
- **ui-shared 空 stub**：Glass 组件仍为 `render(){return null}`，各 app 自行内联
- **孤立组件**：web-user `components/` 下 7 个组件已标注 `@deprecated`
- **语音录制完整闭环**：前端录制 + ASR API 链路已就绪，等待后端 `/voice/asr` 实际对接讯飞/阿里云后自动填入输入框

---

## 七、验证门禁

```bash
# 前端类型检查
pnpm --filter @eira/web-user exec vue-tsc --noEmit   # 0 errors
pnpm --filter @eira/web-admin exec vue-tsc --noEmit   # 0 errors

# 前端构建
pnpm --filter @eira/web-user build                    # ✓ (1.08s)
pnpm --filter @eira/web-admin build                   # ✓ (3.11s)

# 后端
cd backend && python -m uv run pytest tests/ -v       # 测试
python -m uv run ruff check app/ tests/               # lint

# 后端启动验证
cd backend && python -m uv run python -c "from app.main import app; print(app.title)"  # "Eira Backend" (20 routes)
```

---

## 八、后端文件结构快照（新增）

```
backend/app/api/rest/
  voice.py          ← NEW — POST /voice/tts, GET /voice/asr/config
  feedback.py       ← NEW — POST /feedback
  user.py           ← NEW — GET/PATCH /user/preferences, POST /user/background, POST /user/model
  system.py         — 已有
  auth.py           — 已有
  conversations.py  — 已有

backend/app/main.py  ← 修改 — 注册 voice, feedback, user 三个新 router
backend/pyproject.toml ← 新增 python-multipart 依赖
```
