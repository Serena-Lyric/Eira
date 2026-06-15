# Eira 持续测试 Handoff · 2026-06-10

> **日期**: 2026-06-10
> **来源**: Phase 0-4 总结的 P0-P2 修复 + 验证门闭合 + 端到端测试
> **测试基线**: 260 passed, 1 skipped, 0 failures

---

## 1. 工作摘要

在 Phase 0-4 基础上完成：真实 Provider 配置（DeepSeek LLM + 4sapi Embedding + 讯飞 ASR/TTS）、Embedding Provider httpx 兼容修复、LangGraph 返回值 dict 属性访问修复、12 个 P0-P2 问题修复、3 个测试默认值更新、Dashboard 防御性渲染修复、满意度趋势 SVG 动态化、验证门文档和测试创建。

---

## 2. 决策记录

| # | 决策 | 理由 |
|---|------|------|
| D1 | Embedding 用 httpx 替代 openai SDK | openai v2.41.0 对 4sapi.com 响应格式不兼容 |
| D2 | `api_base` 保留为可选字段 | 讯飞官方不需要，但 Proxy/测试/迁移场景需要覆盖 |
| D3 | 讯飞 ASR/TTS config 添加 `api_secret` + `app_id` | 讯飞 HMAC-SHA256 签名必需三要素 |
| D4 | LangGraph `ainvoke()` 返回值用 `result_dict.get()` | 返回 dict 非 ChatState 对象 |
| D5 | Dashboard 防御用 `safeMetrics` + `?? 0` | 防止异步数据竞态导致 `undefined.toLocaleString()` |
| D6 | 满意度 SVG 用 computed 动态绑定 | 替代硬编码 mock 数据，接入 `satisfactionTrend` ref |
| D7 | `persona-config` API 加尾部斜杠 | FastAPI 307 重定向不被 Vite 代理跟随 |
| D8 | `useChatSession.createSession()` 用 REST API + fallback | 确保后端会话 ID（整数）传入 WS，失败时降级 |
| D9 | chat.py 在 `_process_user_text` 内加载历史 | 保持 ChatState 完整性，避免 graph node 获取 DB session |

---

## 3. 文件变更

### 3.1 本对话修改

| 文件 | 变更 | 说明 |
|------|:--:|------|
| `backend/app/capabilities/embedding/openai_compat.py` | ✏️ | httpx 替代 openai SDK，修复 4sapi.com 兼容 |
| `backend/app/core/config.py` | ✏️ | ASR/TTS 添加 `api_secret`/`app_id`/`xunfei` 选项 |
| `backend/app/capabilities/asr/xunfei.py` | ➕ | 讯飞 ASR Provider（HMAC-SHA256 + WebSocket） |
| `backend/app/capabilities/tts/xunfei.py` | ➕ | 讯飞 TTS Provider（HMAC-SHA256 + WebSocket） |
| `backend/app/capabilities/asr/factory.py` | ✏️ | 添加 xunfei 路由 |
| `backend/app/capabilities/tts/factory.py` | ✏️ | 添加 xunfei 路由 |
| `backend/app/api/ws/chat.py` | ✏️ | dict 属性访问修复 + 历史加载 + 动作扩展 prompt |
| `backend/app/api/ws/voice.py` | ✏️ | dict 属性访问修复 + 历史加载 + print 诊断 |
| `backend/app/api/ws/messages.py` | ✏️ | ACTION_TAG_MAP 新增 7 个标签 |
| `backend/app/api/rest/user.py` | ✏️ | 背景持久化 + model_source 字段 |
| `apps/web-user/src/composables/useChatSession.ts` | ✏️ | createSession() REST API + fallback |
| `apps/web-user/src/composables/useVoiceWs.ts` | ✏️ | onclose 增强诊断日志 |
| `apps/web-user/src/composables/useActionParser.ts` | ✏️ | motionMap 新增 7 个标签 |
| `apps/web-user/src/pages/Chat.vue` | ✏️ | 背景持久化 + auth check + 文档上传 + 模型切换 + 定位 |
| `apps/web-user/src/services/api.ts` | ✏️ | 新增 documentApi |
| `apps/web-admin/src/pages/Dashboard.vue` | ✏️ | safeMetrics 防御 + SVG 动态化 |
| `apps/web-admin/src/services/api.ts` | ✏️ | persona-config 尾部斜杠 |
| `apps/web-user/index.html` | ✏️ | favicon link |
| `apps/web-user/public/favicon.svg` | ➕ | SVG favicon |

### 3.2 测试文件

| 文件 | 变更 | 说明 |
|------|:--:|------|
| `tests/validation/test_g2_2_rag_recall.py` | ➕ | 30 QA 对 RAG 召回评估（MRR=1.0） |
| `tests/validation/test_g2_3_rag_latency.py` | ➕ | Orchestrator E2E 延迟测量 |
| `tests/validation/test_g4_3_reprocess_stability.py` | ➕ | 5 文档重新向量化（5/5 成功） |
| `tests/unit/test_asr.py` | ✏️ | 默认 provider 期望值 mock→xunfei |
| `tests/unit/test_tts.py` | ✏️ | 同上 |
| `tests/integration/test_voice.py` | ✏️ | ASR 测试覆盖 mock provider |

### 3.3 文档

| 文件 | 说明 |
|------|------|
| `docs/superpowers/validations/G-2.4.md` | 来源标注人工验证 |
| `docs/superpowers/validations/G-3.1.md` | 语音延迟人工验证 |
| `docs/superpowers/validations/G-3.2.md` | 口型同步人工验证 |
| `docs/superpowers/validations/G-3.4.md` | MVP 完整度检查清单 |
| `docs/superpowers/validations/G-4.1.md` | 管理员功能验证 |
| `docs/superpowers/validations/G-4.2.md` | 角色卡编辑器验证 |
| `docs/superpowers/validations/README.md` | 全部 17 门汇总 |
| `docs/superpowers/handoff/2026-06-09-eira-phase-summary.md` | §8 启动指南更新 |

### 3.4 运维操作

| 操作 | 效果 |
|------|------|
| `UPDATE users SET role='admin' WHERE email='admin@eira.dev'` | admin 角色修复 |
| `docker exec deploy-minio-1 mc mb local/eira-user-assets` | OSS bucket 创建 |

---

## 4. 当前状态

### 4.1 测试基线

```
260 passed, 1 skipped, 0 failures
```

1 skipped 为 `test_worker_handles_error_gracefully` — 硬编码 skip 的占位测试。

### 4.2 服务

| 服务 | 地址 | 状态 |
|------|------|:--:|
| PostgreSQL | localhost:5432 | 🟢 |
| Redis | localhost:6379 | 🟢 |
| MinIO | localhost:9000/9001 | 🟢 |
| 后端 | localhost:8000 | 🟢 |
| web-user | localhost:5173 | 🟢 |
| web-admin | localhost:5174 | 🟢 |

### 4.3 Provider 配置

| 服务 | Provider | 状态 |
|------|----------|:--:|
| LLM | DeepSeek (`deepseek-chat`) | 🟢 就绪 |
| Embedding | 4sapi.com (`text-embedding-3-small`) | 🟢 就绪 |
| ASR | 讯飞 (`xunfei`) | 🟡 已配置，待验证 |
| TTS | 讯飞 (`xunfei`) | 🟡 已配置，待验证 |
| Search | Tavily | 🔴 未配置 |

### 4.4 已验证功能

| 功能 | 状态 | 备注 |
|------|:--:|------|
| 文本对话（DeepSeek） | ✅ | 正常回复，延迟 ~2-4s |
| Live2D 渲染 + 动作 | ✅ | 模型加载正常，动作触发正常 |
| Admin Dashboard | ✅ | 安全渲染，无 crash，动态满意度图 |
| Admin 服务建议 | ✅ | 显示用户反馈列表 |
| Admin 用户管理 | ✅ | 列表/搜索/禁用/改角色 |
| 知识库文档处理 | ✅ | 上传→解析→分块→向量化全链路 |
| RAG 语义搜索 | ✅ | MRR=1.0（第一个结果总是正确） |
| 重新向量化 | ✅ | 5/5 文档 reprocess 成功 |

### 4.5 已知问题

| # | 问题 | 级别 | 现象 | 根因分析 |
|---|------|:--:|------|------|
| 1 | 语音 WS code=4000 | 🔴 | 连接后异常关闭，反复重连 | 需查看后端 `[voice.ws]` print 输出确定 |
| 2 | TTS 无语音输出 | 🔴 | AI 回复无语音播报 | 依赖 #1 修复 |
| 3 | 聊天上下文丢失 | 🟡 | 追问时 AI 不知道之前聊过什么 | `createSession()` 首次 401 → fallback 随机 ID → `int()` 失败 |
| 4 | 首次 `/api/conversations` 401 | 🟡 | 控制台报错但不影响功能 | Token 未就绪时发起请求，Axios 刷新后重试成功 |
| 5 | Xunfei ASR 集成测试 | 🟡 | 讯飞 API 返回 "request data must be valid json string" | 音频格式/鉴权需调优 |
| 6 | 人工验证门待闭合 | 🔵 | G-2.4/G-3.1/G-3.2/G-3.4/G-4.1/G-4.2 | 需人工操作或 Playwright |
| 7 | 文档上传前端路径 | 🟢 | 已添加 `documentApi`，待验证 |
| 8 | 模型源切换 | 🟢 | 已添加 model_source，待验证 |

---

## 5. 阻碍点

| 项 | 级别 | 说明 |
|----|:--:|------|
| Voice WS 4000 | 🔴 | **核心阻塞** — 语音全链路依赖此 WS。需查看后端终端 `[voice.ws]` print 输出定位根因 |
| 首次 401 导致上下文断裂 | 🟡 | `createSession()` 失败 → fallback 随机 ID。需在调用前确保 token 有效 |

---

## 6. 下一步计划

### 6.1 立即可做（按优先级）

1. **诊断 Voice WS 4000** — 在后端终端查找 `[voice.ws]` 输出，确认是 provider 初始化失败还是消息处理异常
2. **修复首次 401 → 上下文断裂** — 在 `createSession()` 中先验证 token 有效性，或加重试逻辑
3. **手动测试已验证修复** — 背景上传→刷新不丢失、文档上传→知识库处理、模型切换
4. **继续人工验证门** — 按 `docs/superpowers/validations/` 中 G-2.4~G-4.2 的检查清单执行

### 6.2 Voice WS 调试指引

当后端终端出现 `[voice.ws]` print 输出时：

| 输出内容 | 含义 | 下一步 |
|---------|------|------|
| `[voice.ws] Fatal error: ...` | Provider 初始化或主循环异常 | 根据异常信息修复 |
| `[voice.ws] Orchestrator error: ...` | ASR→LLM→TTS 管线异常 | 检查 LLM/ASR/TTS provider 连接 |
| `[voice.ws] WebSocketDisconnect` | 客户端主动断开（正常） | 检查浏览器端为何断开 |
| 无任何 `[voice.ws]` 输出 | 异常发生在 try 块外部（初始化阶段） | 检查 `create_asr_provider` / `create_tts_provider` / `get_effective_llm_settings` |

### 6.3 后续迭代

| 范围 | 内容 |
|------|------|
| Phase 5 | 运营看板后端 API（埋点 + 聚合） |
| Phase 6 | 长期记忆 + 情感识别 |
| 质量 | 前端单元测试 / Playwright E2E |
| 安全 | API key 从 config.py 迁移到环境变量（§4.5） |

---

## 7. 快速启动

```powershell
# PowerShell
cd D:\Application\ClaudeCode\repository\Eira\backend
$env:EIRA_DB_DSN="postgresql+asyncpg://eira:eira@localhost:5432/eira"
$env:EIRA_REDIS_URL="redis://localhost:6379/0"
$env:EIRA_OSS_ENDPOINT="http://localhost:9000"
$env:EIRA_OSS__SECRET="eira-secret"
$env:EIRA_JWT__SECRET="dev-secret"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
# 前端
pnpm --filter @eira/web-user dev      # http://localhost:5173
pnpm --filter @eira/web-admin dev     # http://localhost:5174
```

```bash
# 测试
cd backend
EIRA_JWT__SECRET=test-secret EIRA_OSS__SECRET=eira-secret \
  EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
  EIRA_REDIS_URL=redis://localhost:6379/0 \
  EIRA_OSS_ENDPOINT=http://localhost:9000 \
  python -m pytest tests/ -v --tb=short
```

---

## 8. 关联文档

- [Phase 0-4 总结](./2026-06-09-eira-phase-summary.md)
- [P0-P2 修复 Handoff](./2026-06-10-p0-p2-fixes-handoff.md)
- [验证门汇总](../validations/README.md)
- [归档目录](./archive/)
