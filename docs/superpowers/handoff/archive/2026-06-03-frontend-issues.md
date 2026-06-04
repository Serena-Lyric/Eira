# 前端问题分析 · `http://localhost:5173/chat` 黑屏

**日期:** 2026-06-03（更新于同日联调前）
**状态:** 根因已定位，待修复后进入联调

---

## 根因确认：Live2D Cubism Core SDK 文件缺失

### 定位过程

1. **vue-tsc 类型检查**：首次报 `mockBackendResponse` 不存在 → 已修复（模板现用 `handleQuickQuestion`）
2. **再次 vue-tsc**：通过，0 错误
3. **后端测试**：65 passed，0 failed
4. **仍黑屏** → 问题不在 TypeScript 层面，在运行时

### 真正原因

`index.html` 第 8 行引用了一个**不存在的本地文件**：

```html
<script src="/live2d-core/live2dcubismcore.min.js"></script>
```

对应的物理文件 `public/live2d-core/live2dcubismcore.min.js` **不存在**。

验证结果：
```
$ ls public/
live2d    ← 只有模型目录，没有 live2d-core/

$ find . -name "live2dcubismcore*"
(无结果)
```

### 黑屏机理

1. `<script>` 在 `<head>` 中**同步加载**（无 `async`/`defer`）
2. 浏览器遇到 script 标签 → 暂停 HTML 解析 → 发起 GET `/live2d-core/live2dcubismcore.min.js`
3. Vite dev server 返回 **404**
4. 浏览器等待 script 加载完成（即使 404 也需要完整响应周期）
5. `<body>` 的 `background: #000` 在此期间已渲染 → **全黑屏**
6. Vue 应用的 `<script type="module">` 在第 12 行，被第 8 行的同步脚本**阻塞**，始终无法执行

### 修复方案

**方案 A（推荐 — 快速恢复）：** 恢复 CDN 引用
```html
<script src="https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js" defer></script>
```

**方案 B：** 从 Live2D 官网下载 SDK，放入 `public/live2d-core/` 目录

---

## 已修复的相关问题

| # | 问题 | 状态 |
|---|---|---|
| 1 | 模板 `@click="mockBackendResponse(q)"` 引用已删除函数 | ✅ 已改为 `handleQuickQuestion` |
| 2 | FastAPI `/docs` `/redoc` 自动文档页面 | ✅ 已禁用 |
| 3 | 初始问候语在 `onMounted` 中被 no-op | ✅ 添加 `initialGreeting` + `hasInteracted` 标记 |
| 4 | Live2D `containerRef` 未绑定模板 | ✅ 模板已有 `ref="live2dContainerRef"` |
| 5 | 未登录 WS 连接静默失败 | ✅ 无 token 时自动跳转 `/login` |

---

## 联调准备状态

### 后端 ✅
```
65 passed, 0 failed — 82% coverage
```
- REST: `/auth/*`, `/conversations/*`
- WS: `/ws/chat?token=<jwt>`
- Provider: DeepSeek (`EIRA_LLM__PROVIDER=deepseek`), API key 已配置
- DB: PostgreSQL (pgvector), Redis, MinIO — Docker 已启动
- Migration: `chat_session`, `chat_message` 表已创建

### 前端 ⚠️ 待修复
```
vue-tsc --noEmit → 0 errors
```
- 一个阻塞 bug：Cubism Core SDK 本地文件缺失

### 启动命令
```bash
# 终端 1: 后端
cd backend
EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
EIRA_REDIS_URL=redis://localhost:6379/0 \
EIRA_OSS_ENDPOINT=http://localhost:9000 \
python -m uvicorn app.main:app --reload --port 8000

# 终端 2: 前端
pnpm --filter web-user dev
# → http://localhost:5173 → 自动跳转 /chat
```
