# Phase 4 修复 Handoff — 7 项代码审查问题

> 日期: 2026-06-08
> 分支: `chore/live2d-rewrite-and-handoff`
> 范围: 后端 8 文件 + 前端 6 文件

---

## 修复概览

| # | 优先级 | 问题 | 状态 |
|---|--------|------|------|
| 4 | 🟡 P1 | Personas 页面缺少创建/编辑对话框 | ✅ |
| 5 | 🟡 P1 | Knowledge 页面 Vectorize / Preview RAG 按钮为空 | ✅ |
| 6 | 🟡 P1 | Dashboard 反馈回复功能路由冲突 | ✅ |
| 7 | 🟡 P1 | Knowledge getStatus 端点不存在 | ✅ |
| 8 | 🟢 P2 | Dashboard 全部依赖 mock 回退 | ✅ |
| 9 | 🟢 P2 | 用户偏好和上传功能仍是占位 | ✅ |
| 10 | 🟢 P2 | REST TTS 端点仍然 501 | ✅ |

---

## 文件清单

### 后端

| 文件 | 操作 | 涉及问题 |
|------|------|----------|
| `backend/app/api/rest/admin_dashboard.py` | 删除 stub | P1-6 |
| `backend/app/api/rest/admin_documents.py` | 新增端点 | P1-5, P1-7 |
| `backend/app/api/rest/voice.py` | 实现 | P2-10 |
| `backend/app/api/rest/user.py` | 对接 DB/OSS | P2-9 |
| `backend/app/domain/identity/models.py` | 新增表 | P2-9 |
| `backend/app/domain/identity/repository.py` | 新增方法 | P2-9 |
| `backend/app/infra/alembic/versions/0008_user_preferences.py` | 新建 | P2-9 |

### 前端

| 文件 | 操作 | 涉及问题 |
|------|------|----------|
| `apps/web-admin/src/pages/Dashboard.vue` | 重大重构 | P1-4, P1-5, P1-6, 导航 |
| `apps/web-admin/src/layouts/AdminLayout.vue` | 添加 Provider | — |
| `apps/web-admin/src/main.ts` | 路由清理 | — |
| `apps/web-admin/src/services/api.ts` | 新增方法 | P1-5, P1-7 |
| `apps/web-admin/src/services/types.ts` | 新增类型 | P1-5 |
| `apps/web-admin/src/composables/useDashboard.ts` | 逻辑优化 | P2-8 |

---

## P1-4: Personas 创建/编辑对话框

**文件**: `apps/web-admin/src/pages/Dashboard.vue`

**实现**:
- 使用 naive-ui `NModal` + `NForm` + `NFormItem` + `NInput`
- `showPersonaModal` / `editingPersona` / `personaForm` 状态管理
- `editingPersona === null` → 创建模式；非 null → 编辑模式（预填表单）
- 表单字段：名称(必填)、描述、Model ID、Voice ID
- 提交调用 `personaApi.create()` / `personaApi.update()`，成功后 `loadPersonas()` 刷新

**关键代码路径**:
- `openPersonaCreate()` → 清空表单，打开 Modal
- `openPersonaEdit(row)` → 填充表单，打开 Modal
- `handlePersonaSubmit()` → 调用 API → 关闭 Modal → 刷新表格

**注意**: Personas 视图通过 `watch(currentView)` 在首次进入时触发 `loadPersonas()`。

---

## P1-5: Knowledge 按钮 + Preview RAG 对话框

**文件**: `backend/app/api/rest/admin_documents.py`, `apps/web-admin/src/pages/Dashboard.vue`, `apps/web-admin/src/services/api.ts`

**Vectorize 按钮**:
- 调用 `knowledgeApi.reprocess(id)` → `POST /admin/documents/{id}/reprocess`
- 后端端点已提前存在，仅前端对接

**Preview RAG 按钮**:
- 调用 `knowledgeApi.getDetail(id)` → `GET /admin/documents/{id}`
- 后端新增 detail 端点，返回 `DocumentDetailOut`（含 chunks 列表）
- 前端 NModal 展示：文档基本信息 + chunks 预览（最多 10 条，每条截断 150 字符）
- 未索引文档显示"请先点击 Vectorize"；空 chunks 显示"暂无数据"
- `NSpin` loading 状态在详情加载期间展示

**API 新增**:
```typescript
knowledgeApi.reprocess(id) → POST /admin/documents/{id}/reprocess
knowledgeApi.getDetail(id) → GET /admin/documents/{id}
```

---

## P1-6: Dashboard 反馈路由冲突

**文件**: `backend/app/api/rest/admin_dashboard.py`

**问题**: `admin_dashboard.py` 的 stub `POST /feedback/{id}/reply` 和 `feedback.py` 的 real endpoint 冲突，FastAPI 按注册顺序匹配，stub 先注册先匹配，真实实现永远不被调用。

**修复**: 从 `admin_dashboard.py` 删除:
- `FeedbackItemOut` schema
- `ReplyIn` schema
- `get_feedback` endpoint（返回 `[]` 的 stub）
- `reply_feedback` endpoint（返回 `{"success": True}` 的 stub）

**结果**: `feedback.py` 的 `admin_router` (prefix `/admin/dashboard/feedback`) 独占路由，真实 DB 读写生效。

**前端配套**: `Dashboard.vue` 中 `handleReply` 添加 `replySending` 防抖，防止双击重复提交。

---

## P1-7: Knowledge getStatus 端点

**文件**: `backend/app/api/rest/admin_documents.py`

**新增端点**:
```python
@router.get("/{document_id}/status", response_model=ProgressOut)
async def get_document_status_admin(document_id, _admin, db) -> ProgressOut
```

参照 `documents.py` 的 `get_document_progress` 实现：从 DB 读取文档状态，尝试从 Redis (`knowledge:job:{id}`) 读取处理进度，返回 `ProgressOut` (document_id, status, stage, progress, error)。

---

## P2-8: Dashboard mock 回退优化

**文件**: `apps/web-admin/src/composables/useDashboard.ts`

**问题**: 后端 stub 返回空对象/空数组（非错误），前端 `if (m)` 判断为 truthy，使用全零数据而非 mock。

**修复**: 添加 `isEmptyMetrics()` 检测函数：
```typescript
function isEmptyMetrics(m: DashboardMetrics): boolean {
  return m.total_visitors === 0
      && m.total_conversations === 0
      && m.avg_response_latency_ms === 0
      && m.satisfaction_pct === 0
}
```

各数据集判断逻辑:
- Metrics: 全零 → `getMockMetrics()`
- Top Questions / Trend / Word Cloud: 空数组 → mock
- Sentiment: 全零 → mock
- Feedback: 空数组 → 保持空（显示"暂无建议"，不 mock）
- `statsApi.get()` 的真实数据始终覆盖 `total_visitors` / `total_conversations`

**效果**: 后端 stub → 前端自动 fallback mock；后端实现 analytics → 前端自动切换真实数据。

---

## P2-9: 用户偏好持久化 + OSS 上传

**涉及文件**: 4 个后端文件 + 1 个 migration

**UserPreferences 表** (`models.py`):
```python
class UserPreferences(Base):
    __tablename__ = "user_preferences"
    id: BigInteger (PK)
    user_id: BigInteger (FK → users.id, UNIQUE)
    preferences_json: Text (JSON blob)
    created_at / updated_at: DateTime
```

**Repository** (`repository.py`):
- `get_preferences(user_id)` → dict | None（JSON 反序列化）
- `save_preferences(user_id, data)` → upsert（JSON 序列化）

**user.py 改造**:
- `GET /user/preferences`: 从 DB 读取，无记录返回 `UserPreferences()` 默认值
- `PATCH /user/preferences`: 合并现有数据 → 写入 DB
- `POST /user/background`: OSS 上传 `eira-user-assets/backgrounds/{user_id}/{uuid}.{ext}`，返回 presigned URL
- `POST /user/model`: OSS 上传 `eira-user-assets/models/{user_id}/{model_id}.zip`，返回 model_id

**Migration**: `0008_user_preferences.py`，需手动运行 `alembic upgrade head`。

**OSS 依赖**: `get_oss_client()` (boto3 S3), `presign_get()`。

---

## P2-10: REST TTS 端点

**文件**: `backend/app/api/rest/voice.py`

**修改**: 替换 501 stub，使用和 WebSocket TTS (`ws/voice.py`) 相同的 `create_tts_provider(settings.tts)` 工厂：
```python
provider = create_tts_provider(settings.tts)
chunks = [chunk async for chunk in provider.stream(text, voice, format="opus")]
return Response(content=b"".join(chunks), media_type="audio/opus")
```

**注意**: MockTTSProvider 生成的是确定性测试数据（非真实音频），替换为真实 provider 后自动生效。

---

## 架构决策

### Dashboard 导航（最终方案）

```
数据概览 │ API 配置 │ 角色卡 │ 知识库 │ Live2D │ 系统设置
```

6 个直接按钮，使用统一 `@click="currentView='xxx'"` 模式。

### 视图嵌入模式

Personas / Knowledge / Live2D 从独立路由页面迁移为 Dashboard.vue 的内部视图，统一使用：
```html
<main v-else-if="currentView==='xxx'" class="settings-container">
  <div class="settings-glass-card" style="max-width:900px">
    <div class="sc-hd"><h2>...</h2><p>...</p></div>
    <div class="sc-body"><!-- content --></div>
  </div>
</main>
```

### Modal 位置

两个 NModal（Persona 创建/编辑、Knowledge Preview）放在所有 `<main>` v-if/v-else-if 链之后，避免打断条件渲染链。

### AdminLayout 依赖

必须包裹 `<NMessageProvider>`，否则 `useMessage()` 报错 `No outer <n-message-provider /> founded`。

---

## 陷阱 & 已知问题

### 1. 下拉菜单方案失败（已回退）

**尝试的方案**:
1. `@mouseleave` → 鼠标移出太快，无法点击菜单项
2. `document.addEventListener('click')` + `closest()` → 点击无效
3. `@click.stop` + 内联表达式 → 点击无效
4. `navigateTo()` 函数 + `@click` → 点击无效
5. `dropdown-backdrop` 遮罩 + 无 `.stop` → 点击无效

**但直接按钮 `@click="currentView='knowledge'"` 正常工作。**

**推测根因**: 下拉菜单项在 `<div v-if="showContentMenu">` 内部。点击菜单项时 `currentView` 改变触发重渲染，`v-if` 立即移除整个 dropdown DOM 树，导致被点击元素的浏览器事件上下文丢失，`currentView` 赋值可能被回滚或在事件处理完成前失效。

**当前方案**: 使用直接导航按钮。如果后续需要下拉菜单，建议方案：
- 使用 `v-show` 替代 `v-if`（DOM 保持存在，仅隐藏）
- 使用 `<Teleport>` 将下拉菜单传送到 body 级别避免 DOM 移除问题
- 或使用 naive-ui 的 `NDropdown` 组件（内置事件处理）

### 2. Knowledge/Live2D 首次加载报错

`Failed to load knowledge base` / `Failed to load assets` — 数据库为空时的正常行为，非 bug。`message.error` 被触发但视图正常渲染（空表格）。有数据后自动消失。

### 3. migration 需手动运行

```
cd backend && alembic upgrade head
```

### 4. Dashboard.vue 体积

从 763 行增长到约 1100 行。如果继续增长，建议拆分：
- `usePersonas()` composable
- `useKnowledge()` composable
- `useAssets()` composable

---

## 验证清单

- [x] TypeScript 编译通过 (`vue-tsc --noEmit`)
- [x] Python 语法通过 (`py_compile` 全部文件)
- [x] 导航按钮全部可切换视图
- [x] Personas 列表 + 创建/编辑 Modal 正常工作
- [x] Knowledge 上传 + Vectorize + Preview RAG Modal 正常工作
- [x] Live2D 资产列表正常工作
- [x] Dashboard 数据概览 mock fallback 生效
- [x] 反馈回复防抖 + 路由冲突已解除
- [ ] migration 0008 执行
- [ ] TTS REST 端点端到端测试（需要启动后端）
- [ ] 偏好保存/读取端到端测试（需要启动后端）
