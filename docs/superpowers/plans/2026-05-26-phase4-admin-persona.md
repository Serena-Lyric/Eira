---
name: 2026-05-26-phase4-admin-persona
title: Phase 4 · 管理后台后端 + 角色卡 + 数据对接
date: 2026-05-26
status: draft
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
overview: docs/superpowers/plans/2026-05-26-overview.md
prev: docs/superpowers/plans/2026-05-26-phase3-voice-multimodal-shell.md
revision: 2026-06-02 — 管理 UI 已完成，聚焦后端 CRUD + 权限 + 数据对接
---

# Phase 4 实施计划 · 管理后台后端 + 角色卡 + 数据对接

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现管理后台所有后端 CRUD API + 权限控制 + 审计日志，并将已完成的管理 UI 页面从 mock 数据切换为真实 API 调用。完成后管理员可完全通过 UI 运营，无需进数据库。

## 🔒 前端 UI 状态

**管理端 UI 已 100% 基线定档（7 个 Vue 文件）：**

| 文件 | 状态 |
|---|---|
| `AdminLayout.vue` | 🔒 NConfigProvider + RouterView 空壳（无侧边栏导航） |
| `Login.vue` | 🔒 登录表单 |
| `Dashboard.vue` | 🔒 内联三视图（运营/API/设置），手写 SVG 图表 |
| `Content/Personas.vue` | 🔒 NDataTable + 模拟数据 |
| `Content/Knowledge.vue` | 🔒 NDataTable + NUpload + 模拟数据 |
| `Content/Live2D.vue` | 🔒 NDataTable + NUpload + 模拟数据 |

**关键实际偏差（已确认，不回退）：**
- Admin 布局无侧边栏导航（当前空壳为最终形态）
- 图表使用手写 SVG（不引入 ECharts）
- 三个内容管理页面使用 NDataTable（非原计划的 Naive UI + ui-shared 混合）
- 认证守卫已注释（待后端对接后启用）

**本 Phase 前端工作：** 在 `<script>` 中替换 mock 数据为 API 调用、启用认证守卫。必要时（由后端实现需求驱动）可调整 UI。

**Architecture:**
- 角色卡 schema 对齐 SillyTavern：`name / description / personality / scenario / first_mes / mes_example / system_prompt / avatar / live2d_model_id / voice_id / tags`。
- 系统设置走 `system_setting` 键值对表。
- 操作审计：`audit_log` 表 + AuditMiddleware。
- 权限：visitor / admin 角色隔离，require_admin 依赖注入。

**Tech Stack:** FastAPI 路由、Alembic 迁移 0006-0008、Pinia 数据层。

**前置条件：** Phase 0/1/2/3 全部 Validation Gate passed。

**本 Phase 不做：** 运营看板数据（Phase 5）、长期记忆（Phase 6）、多租户（Phase 7+）。

**重述全局约定：** TDD；commit 前缀；密钥不入库；管理操作必须留痕；UI 修改需有后端需求依据。

---

## 任务依赖图

```
T4.1 用户管理后端（列表/封禁/改角色 API）
  ↓
T4.2 persona 表 + 迁移 0006
  ↓
T4.3 角色卡 REST CRUD（含 SillyTavern V2 导入/导出）
  ↓
T4.4 系统设置（默认模型/预算/配额/安全黑名单）
  ↓
T4.5 audit_log + AuditMiddleware + 审计查询 API
  ↓
T4.6 前端数据对接 — Admin 全部页面从 mock 切换为 API + 启用认证守卫
  ↓
🚦 G-4.1 / G-4.2 / G-4.3 / G-4.4
```

---

## 后端任务

### Task 4.1: 用户管理后端

**Files:**
- Create: `backend/app/api/rest/admin_users.py`
- Modify: `backend/app/domain/identity/service.py`（追加 list_users / disable_user / set_role）
- Modify: `backend/app/infra/alembic/versions/0006_persona_and_users_extras.py`（users 加 disabled / deleted_at 列）
- Create: `backend/tests/integration/test_admin_users.py`

REST：
- `GET /admin/users?keyword=&role=&page=&size=` — 分页列表
- `GET /admin/users/{id}` — 单用户详情（含资源用量）
- `PATCH /admin/users/{id}` — 改 role / disabled
- `DELETE /admin/users/{id}` — 软删

> ⚠️ 防护规则：不允许自降级/自禁用；至少保留一个未禁用 admin。

---

### Task 4.2: persona 表 + 迁移

**Files:**
- Create: `backend/app/infra/alembic/versions/0006_persona_and_users_extras.py`
- Create: `backend/app/domain/persona/models.py`
- Create: `backend/app/domain/persona/schemas.py`

字段：scope(public/user) / user_id / name / description / personality / scenario / first_mes / mes_example / system_prompt / avatar_asset_id / live2d_asset_id / voice_id / tags / disabled。

---

### Task 4.3: 角色卡 REST CRUD（含导入/导出）

**Files:**
- Create: `backend/app/api/rest/personas.py`（用户端）
- Create: `backend/app/api/rest/admin_personas.py`（管理端）
- Create: `backend/app/domain/persona/service.py`
- Create: `backend/app/domain/persona/repository.py`
- Create: `backend/tests/integration/test_personas.py`
- Create: `backend/tests/unit/test_persona_silly_import.py`

REST：
- 用户端：`GET /personas?scope=public|mine` / `POST /personas` / `PATCH /personas/{id}` / `DELETE /personas/{id}` / `POST /personas/import` / `GET /personas/{id}/export`
- 管理端：`GET /admin/personas` / `POST /admin/personas` / `PATCH /admin/personas/{id}` / `DELETE /admin/personas/{id}`

> ⚠️ SillyTavern V2 JSON 导入：MVP 只支持 V2 JSON（PNG 导入留 backlog）。字段映射保持原名兼容。

---

### Task 4.4: 系统设置

**Files:**
- Create: `backend/app/infra/alembic/versions/0007_system_setting.py`
- Create: `backend/app/domain/system/models.py`
- Create: `backend/app/domain/system/service.py`
- Create: `backend/app/api/rest/admin_settings.py`
- Create: `backend/tests/integration/test_admin_settings.py`

设置项分组：LLM 默认（provider/model）、Embedding（provider/unit_price）、Web Search（provider/daily_budget）、配额（background/live2d/document per user）、安全（blacklist/redact patterns）、语音（persist_audio）。

> ⚠️ API key 真值不在 UI 暴露，仅显示 Provider 配置状态（✅/⚠️）。修改后 Redis pub/sub `settings:reload` 触发各副本刷新。

---

### Task 4.5: 审计日志

**Files:**
- Create: `backend/app/infra/alembic/versions/0008_audit_log.py`
- Create: `backend/app/core/middleware/audit.py`
- Create: `backend/app/api/rest/admin_audit.py`
- Create: `backend/tests/integration/test_audit.py`

middleware 记录 `/admin/**` 下 POST/PUT/PATCH/DELETE。body_summary 脱敏（password/token/api_key/secret → `***`）。查询页支持过滤 + 分页 + CSV 导出。保留期 180 天。

---

## 前端数据对接任务

### Task 4.6-FE: Admin 全页面数据对接 + 启用认证守卫

**Files:**
- Modify: `apps/web-admin/src/pages/Dashboard.vue`（`<script>` only）
- Modify: `apps/web-admin/src/pages/Content/Personas.vue`（`<script>` only）
- Modify: `apps/web-admin/src/pages/Content/Knowledge.vue`（`<script>` only）
- Modify: `apps/web-admin/src/pages/Content/Live2D.vue`（`<script>` only）
- Modify: `apps/web-admin/src/router/index.ts`（启用 beforeEach 守卫）
- Modify: `apps/web-user/src/router/index.ts`（启用 beforeEach 守卫）

**工作内容：**

1. **启用认证守卫**：
   - 恢复 `router.beforeEach`，连接后端 `/auth/login`
   - 无 token → `/login`；非 admin 访问 admin 路由 → `/forbidden`
   - 配合 Axios 响应拦截器 401 → 自动 refreshToken → 失败跳登录

2. **Dashboard 数据对接**：
   - 替换硬编码 SVG 数据为 API 调用（运营指标/FAQ/满意度/词云/情感分析）
   - API 端点由 Phase 5 提供（Phase 4 期间可用 `/admin/metrics/realtime` 等占位）

3. **内容管理页数据对接**：
   - Personas.vue：替换 mock 数据为 `GET /admin/personas` / `POST` / `PATCH` / `DELETE`
   - Knowledge.vue：替换 mock 数据为 `GET /documents` / `POST /documents/upload` / `DELETE` / `POST .../reprocess`
   - Live2D.vue：替换 mock 数据为 `GET /assets?kind=live2d` / `POST /assets` / `DELETE`

4. **用户端角色卡切换**：
   - SettingsPanel 角色卡 tab 数据源切换为 `GET /personas?scope=public|mine`
   - 切换角色 → 更新 `currentPersonaId` → 创建新 session

**验证：** 启动全栈 → 登录 admin → 各页面显示真实 API 数据 → CRUD 操作正常 → 认证守卫工作正常。

---

## 🚦 Validation Gates

### G-4.1 · 管理员功能完整性
- 6 个动作（禁用用户/增删改角色卡/上传重处理文档/上传删除资源/修改系统设置/查询审计日志）100% 通过 Playwright E2E。

### G-4.2 · 角色卡编辑器可用性
- 5 名测试者完成"创建角色卡 → 切换到用户端使用"流程，平均耗时 ≤ 8 分钟。

### G-4.3 · 知识库重新向量化稳定性
- 5 篇 ready 文档 reprocess → 100% 成功；处理中检索不中断。

### G-4.4 · 权限边界 + 审计完整性
- 普通用户 `/admin/**` 全部 403；admin 自禁/降级被拒；审计 100% 覆盖；body_summary 不含密钥。

---

## 完成状态

Phase 4 完成 ⇔ G-4.1 / 4.2 / 4.3 / 4.4 全部 passed。MVP + 后台运营基础具备。

## Revision 2026-06-02

- **移除 T4.1/T4.5-T4.8 前端 UI 构建任务**（Admin 骨架/角色卡编辑器/角色卡列表/知识库管理 UI/资源管理 UI）—— 管理端所有 UI 页面已完成。
- **新增 T4.6-FE**（Admin 全页面数据对接 + 认证守卫启用）。
- Admin 布局无侧边栏导航（当前空壳为最终形态，不回退到原计划的三栏布局）。
- Dashboard 使用手写 SVG 图表（不引入 ECharts，不回退）。
- 角色卡编辑器 UI（PersonaEditor/PersonaPreview）已内联实现于 Dashboard.vue + Content/Personas.vue 中。

## Handoff: docs/superpowers/handoff/2026-06-08-phase4-handoff.md
