# Eira 项目 Handoff · 2026-06-14 (Phase 5-6 续)

> **源会话**: 17 问题全量修复实施 + 实机业务测试 + 深层问题定位
> **测试基线**: 256 passed, 4 failed (embedding API 密钥过期), 1 skipped
> **分支**: master
> **前序文档**: docs/superpowers/handoff/eira-handoff-2026-06-14.md

---

## 1. 会话摘要

本次会话在上一次 handoff 基础上，对 17 个问题逐一实施修复，并进行多轮实机业务测试。共涉及 **6 个新建文件、18 个修改文件、9 个删除文件**。

### 修复阶段

| Phase | 内容 | 状态 |
|:-----:|------|:--:|
| 1a | 角色卡 resolver — 使 Persona DB 数据流入 orchestrator | ✅ |
| 1b | effective_settings — TTS/ASR/Embedding/Search 读取 DB 配置 | ✅ |
| 2 | RAG 注入 orchestrator + SystemSettingService UPSERT | ✅ |
| 3 | 前端配置对齐 + UX 修复（6 个问题） | ✅ |
| 4 | Live2D 方案 D (OSS zip + JSZip + IndexedDB) | ⚠️ 部分完成 |
| 5 | 错误模式统一/测试清理/死开关激活/废弃组件删除 | ✅ |
| 6 | 多轮测试修复（下载端点/动作标签/角色卡/端口冲突） | 🔴 残留问题 |

---

## 2. 新增文件

| 文件 | 用途 |
|------|------|
| `backend/app/domain/persona/resolver.py` | 查询默认 persona 的 system_prompt，fallback 链 |
| `backend/app/capabilities/effective_settings.py` | TTS/ASR/Embedding/Search DB-aware settings |
| `backend/app/core/error_schema.py` | 统一错误响应 `{ error, message, cause }` |
| `apps/web-user/src/composables/useLive2DModelLoader.ts` | 方案 D：JSZip 解压 + fetch 拦截 + IndexedDB 缓存 |
| `backend/scripts/seed_models.py` | 一次性上传 7 个模型到 OSS 并注册 |
| `docs/originalfile/2D/` (7个模型) | 本地模型归档 |

## 3. 已删除文件

- `apps/web-user/public/live2d/` 目录（模型文件）
- `apps/web-admin/public/live2d/` 目录（模型文件）
- 7 个 web-user 废弃组件 (`TopSettingsButton.vue` 等)

---

## 4. 关键架构变更

### 4.1 角色卡系统 → orchestrator 连接
- `chat.py` / `voice.py` 构造 ChatState 前调用 `get_default_persona_prompt()`
- 优先级：`persona.system_prompt` > `personality+scenario+first_mes` 构建 > 硬编码 fallback
- 硬编码导游提示词保留在 `resolver.py` 的 `DEFAULT_PERSONA_FALLBACK`

### 4.2 RAG/知识库自实例化
- `graph.py` `_retrieve_kb` / `_web_search` wrapper 内部创建 session + provider
- 不受 WebSocket 长连接限制
- embedding API 失败时自动降级到 MockEmbeddingProvider

### 4.3 Factory 统一读 DB
- 为 TTS/ASR/Embedding/Search 创建 `get_effective_*_settings()` (模式复用 LLM)
- `voice.py` (WS + REST)、`knowledge_worker.py` 全部改用 DB-aware settings
- admin_settings 缓存失效扩展覆盖所有 provider

### 4.4 Live2D 方案 D
- 存储：OSS `live2d-models/{model_id}.zip`
- 加载：前端 JSZip 解压 → fetch 拦截器提供 Blob URL → Cubism SDK
- 缓存：待实现 IndexedDB 持久化
- 优先级：用户自定义 > admin 全局默认
- 7 个模型已上传 OSS + 注册 assets 表

### 4.5 错误格式统一
- `ErrorResponse` pydantic model + 全局 HTTPException handler
- 保留 `detail` 键向后兼容
- String detail → `{error: "http_error", message: "...", detail: "..."}`

### 4.6 角色卡约束
- `set_default` 跨 scope 清除旧默认（`clear_default_for_scope` 不再限制 scope）
- `system_prompt` 必填（后端 `min_length=10`，前端 `required: true`）

### 4.7 动作标签剥离修复
- 正则从仅匹配 12 个预定义标签扩展为 `_ANY_BRACKET_RE` 剥离所有 `[...]` 模式

---

## 5. 🔴 当前已知未解决问题

### 5.1 Admin/User 下载端点 404（严重阻塞）

**现象**：
- `GET /admin/assets/{id}/download` 在 TestClient 中返回 401（正确），但通过 uvicorn HTTP 返回 404
- `GET /user/model/download-url` 同理
- 后端日志显示路由已注册，但实际 HTTP 请求无法匹配

**已尝试的修复**：
- 添加 `Authorization` header 到前端 `fetch()` 调用 ✅
- 移除 `DownloadUrlOut` response_model（简化） ✅
- 清除 `__pycache__` ✅
- 多次 `taskkill` 杀进程 ⚠️ 部分 PID 无法杀死
- 目前端口 8000 有 4 个残留进程（PID: 32380, 27128, 31860, 31044），均为旧代码

**根因推测**：旧 uvicorn 进程未被完全杀死，新进程绑定失败，旧代码仍在处理请求

**建议**：
1. 重启电脑或使用管理员权限 PowerShell 执行 `Get-Process -Id <PID> | Stop-Process -Force`
2. 或在 `main.py` 添加新端点后，从 backend 目录完整重启

### 5.2 User 端 `active_model_id` 为旧格式

**现象**：`api/user/model/download-url?oss_key=mao_pro_zh`
- `active_model_id = "mao_pro_zh"`（显示名）而非 `"live2d/8767b36fcc6c/mao_pro_zh.zip"`（OSS key）
- 用户偏好中存有旧值，跳过 fallback

**已修复**：`user.py` 增加旧格式检测 — `"/" not in str(current_model)` 时触发 persona_config fallback
**待验证**：后端重启后是否生效

### 5.3 Admin Live2D 加载失败

**现象**：`useLive2DPreview.ts` 加载模型时报 "Unknown model: live2d-model-128"
- `persona_config.active_model_id` 可能仍为旧格式
- `fetchAvailableModels` 模型描述符 `dir`/`fileName` 为空，依赖 JSZip 下载

**已修复**：
- `loadModel` 集成 JSZip 下载解压 + fetch 拦截器
- `changeModel` 支持三种匹配方式（显示名 / asset ID / OSS key）
- `fetch()` 添加 `Authorization` header

**待验证**：下载端点 404 修复后是否正常

### 5.4 知识库/角色卡测试数据未清理

Admin 面板可见大量 `failed` 状态的文档和测试产生的 personas。
**建议**：后端重启后通过 Admin UI 清理，或执行 SQL 清理脚本

### 5.5 角色卡删除提示后记录仍存在

软删除行为（`disabled=True`），当前 admin 列表未过滤 `disabled`。需确认是否为预期行为。

---

## 6. OSS 模型清单

| Asset ID | 名称 | OSS Key |
|:--------:|------|---------|
| 128 | mao_pro_zh | `live2d/8767b36fcc6c/mao_pro_zh.zip` |
| 129 | hiyori_pro_zh | `live2d/1bd1c6347b0e/hiyori_pro_zh.zip` |
| 130 | akari_vts | `live2d/1672aa665401/akari_vts.rar` |
| 131 | hiyori_vts | `live2d/7c028e0d654d/hiyori_vts.rar` |
| 132 | PinkHair_workshop_2802653785 | `live2d/bdd4212ef2f3/PinkHair_workshop_2802653785.rar` |
| 133 | haru | `live2d/d39eb5b06545/haru.zip` |
| 134 | MaidCyrene | `live2d/6b8ee25433ee/MaidCyrene20251105_....zip` |

当前默认：`mao_pro_zh` (OSS key: `live2d/8767b36fcc6c/mao_pro_zh.zip`)

---

## 7. 服务启动

```bash
# Docker 基础设施
docker compose -f deploy/docker-compose.dev.yml up -d

# 后端 (从 backend 目录执行！)
cd backend
EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
EIRA_REDIS_URL=redis://localhost:6379/0 \
EIRA_OSS_ENDPOINT=http://localhost:9000 \
EIRA_OSS__SECRET=eira-secret \
EIRA_JWT__SECRET=dev-secret \
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端 (从项目根目录执行)
pnpm --filter @eira/web-user dev      # port 5173
pnpm --filter @eira/web-admin dev     # port 5174

# 测试
cd backend
python -m pytest tests/ -v --tb=short
```

**Admin 凭据**: admin@eira.dev / admin123

---

## 8. Suggested Skills

新 agent 建议按顺序调用：

1. **`using-superpowers`** — 了解可用技能
2. **`systematic-debugging`** — 处理下载端点 404 和 Live2D 加载失败
3. **`verification-before-completion`** — 修改后先跑测试再声称完成
4. **`brainstorming`** — 如需重新设计 Live2D 加载方案或角色卡架构
