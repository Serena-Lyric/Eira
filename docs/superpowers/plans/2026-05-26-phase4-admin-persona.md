---
name: 2026-05-26-phase4-admin-persona
title: Phase 4 · 管理后台 + 角色卡 + 资源/系统设置
date: 2026-05-26
status: draft
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
overview: docs/superpowers/plans/2026-05-26-overview.md
prev: docs/superpowers/plans/2026-05-26-phase3-voice-multimodal-shell.md
---

# Phase 4 实施计划 · 管理后台 + 角色卡 + 资源/系统设置

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地管理员侧 SPA：16:9 三栏布局壳层 + 用户管理 + SillyTavern 风格角色卡编辑器 + 知识库管理（含"重新向量化"按钮）+ 资源管理 UI（背景 / Live2D 模型 / 头像）+ 系统设置（默认模型 / Web Search 预算 / 配额）+ 操作审计日志。完成后管理员可独立完成日常运营，无需进数据库。

**Architecture:**
- 管理后台 SPA 复用 Phase 0 的 `@eira/ui-shared`，16:9 布局参考 `docs/DESIGN.txt`：顶栏 72px、左栏 26%、中栏 38%、右栏 36%（Phase 5 分析模块占用右栏，Phase 4 暂留占位）。
- 角色卡 schema 对齐 SillyTavern：`name / description / personality / scenario / first_mes / mes_example / system_prompt / avatar / live2d_model_id / voice_id / tags`，存 `persona` 表；用户端切换走 `/personas?scope=public|mine`。
- 系统设置走 `system_setting` 键值对表，敏感项（模型 API key 已在 Phase 1 走 env，本 phase 不在 UI 暴露真值）。
- 操作审计：写 `audit_log` 表，所有管理员的 POST/PUT/DELETE 接口走 `AuditMiddleware` 留痕；只读查询不写。

**Tech Stack:** Vue 3 + Vite + TS（web-admin）、Naive UI 或继续用 `@eira/ui-shared`（推荐前者拼简单表格 / 表单更快；本计划默认 Naive UI 作为表格/表单库，玻璃风组件由 ui-shared 提供顶层 Modal/Card）、Pinia、FastAPI 路由复用 Phase 0 RBAC、Alembic 迁移 0006/0007。

**前置条件：** Phase 0/1/2/3 全部 Validation Gate passed；用户端 MVP 已可灰度。

**本 Phase 不做：** 运营看板（Phase 5）、长期记忆（Phase 6）、多租户（Phase 7+）、移动端适配（spec 锁定 Windows 优先）。

**重述全局约定：** TDD；commit 前缀；密钥不入库；管理操作必须留痕；裸 SQL 禁；前端模板插值禁混业务字符串（用 `<context>` 标签）。

---

## 任务依赖图

```
T4.1 web-admin SPA 骨架 + 路由 + 鉴权
  ↓
T4.2 用户管理（列表 / 详情 / 封禁 / 改角色）
  ↓
T4.3 persona 表 + 迁移 0006
  ↓
T4.4 角色卡 REST CRUD（含导入/导出 JSON）
  ↓
T4.5 角色卡编辑器 UI（SillyTavern 风格表单 + 预览）
  ↓
T4.6 用户端角色卡列表 + 切换（联动 settings panel）
  ↓
T4.7 知识库管理 UI（列表 / 上传 / 重新向量化 / 删除 / 预览）
  ↓
T4.8 资源管理 UI（背景 / Live2D / 头像统一界面）
  ↓
T4.9 系统设置（默认模型 / Web Search 预算 / 配额 / 安全黑名单）
  ↓
T4.10 audit_log + AuditMiddleware + 审计查询页
  ↓
🚦 G-4.1 / G-4.2 / G-4.3 / G-4.4
```

---

## Task 4.1: web-admin SPA 骨架 + 路由 + 鉴权

**Files:**
- Create: `apps/web-admin/src/main.ts`
- Create: `apps/web-admin/src/App.vue`
- Create: `apps/web-admin/src/router/index.ts`
- Create: `apps/web-admin/src/layouts/AdminLayout.vue`（顶栏 72px + 左栏 26% + 中栏 38% + 右栏 36%）
- Create: `apps/web-admin/src/pages/LoginPage.vue`
- Create: `apps/web-admin/src/pages/DashboardPage.vue`（占位，Phase 5 实装看板）
- Modify: `apps/web-admin/package.json`（追加 naive-ui、@vicons/ionicons5）
- Create: `apps/web-admin/tests/unit/router-guard.spec.ts`

> ⚠️ **要点**：
> - 路由守卫：未登录跳 `/login`；登录后但角色 != admin 跳 `/forbidden` 静态页；用 Phase 0 的 `useAuthStore.user.role`。
> - 顶栏左：站点 logo + "Eira Admin"；中：当前页面 breadcrumb；右：当前管理员 username + 退出按钮。
> - 左栏菜单：仪表盘 / 用户 / 角色卡 / 知识库 / 资源 / 系统设置 / 审计日志（按 spec 锁定的功能模块顺序）。
> - 中栏 = 主内容；右栏 Phase 4 留 `<aside class="placeholder">`，Phase 5 接入分析卡片。

- [ ] **Step 1: 失败测试**

```ts
// tests/unit/router-guard.spec.ts
import { describe, it, expect, beforeEach, vi } from "vitest"
import { setActivePinia, createPinia } from "pinia"
import { useAuthStore } from "@eira/ui-shared/stores/auth"
import { beforeEachGuard } from "../../src/router"

describe("admin router guard", () => {
  beforeEach(() => setActivePinia(createPinia()))

  it("redirects unauthenticated to /login", async () => {
    const next = vi.fn()
    await beforeEachGuard({ path: "/users", meta: { requiresAuth: true } } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith({ path: "/login" })
  })

  it("redirects non-admin to /forbidden", async () => {
    const auth = useAuthStore()
    auth.$patch({ token: "x", user: { id: 1, role: "user" } as any })
    const next = vi.fn()
    await beforeEachGuard({ path: "/users", meta: { requiresAdmin: true } } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith({ path: "/forbidden" })
  })

  it("passes admin through", async () => {
    const auth = useAuthStore()
    auth.$patch({ token: "x", user: { id: 1, role: "admin" } as any })
    const next = vi.fn()
    await beforeEachGuard({ path: "/users", meta: { requiresAdmin: true } } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith()
  })
})
```

- [ ] **Step 2/3: 实现 + 运行 + 提交**

`router/index.ts`：

```ts
import { createRouter, createWebHistory, type NavigationGuardWithThis } from "vue-router"
import { useAuthStore } from "@eira/ui-shared/stores/auth"
const routes = [
  { path: "/login", component: () => import("../pages/LoginPage.vue") },
  { path: "/forbidden", component: () => import("../pages/ForbiddenPage.vue") },
  {
    path: "/", component: () => import("../layouts/AdminLayout.vue"),
    meta: { requiresAdmin: true },
    children: [
      { path: "", redirect: "/dashboard" },
      { path: "dashboard", component: () => import("../pages/DashboardPage.vue") },
      { path: "users", component: () => import("../pages/UsersPage.vue") },
      { path: "personas", component: () => import("../pages/PersonasPage.vue") },
      { path: "knowledge", component: () => import("../pages/KnowledgePage.vue") },
      { path: "assets", component: () => import("../pages/AssetsPage.vue") },
      { path: "settings", component: () => import("../pages/SettingsPage.vue") },
      { path: "audit", component: () => import("../pages/AuditPage.vue") },
    ],
  },
]
export const beforeEachGuard: NavigationGuardWithThis<undefined> = async (to, _from, next) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth || to.meta.requiresAdmin) {
    if (!auth.token) return next({ path: "/login" })
    if (to.meta.requiresAdmin && auth.user?.role !== "admin") return next({ path: "/forbidden" })
  }
  next()
}
export const router = createRouter({ history: createWebHistory(), routes })
router.beforeEach(beforeEachGuard)
```

提交：`feat(web-admin): bootstrap admin spa with route guard and 16:9 layout`。

---

## Task 4.2: 用户管理

**Files:**
- Create: `backend/app/api/rest/admin_users.py`（前缀 `/admin/users`）
- Modify: `backend/app/domain/identity/service.py`（追加 `list_users / disable_user / enable_user / set_role`）
- Create: `apps/web-admin/src/pages/UsersPage.vue`
- Create: `apps/web-admin/src/services/usersApi.ts`
- Create: `backend/tests/integration/test_admin_users.py`

REST：

| Method | Path | 说明 |
|---|---|---|
| GET | `/admin/users?keyword=&role=&disabled=&page=&size=` | 分页列表 |
| GET | `/admin/users/{id}` | 单用户（含资源用量） |
| PATCH | `/admin/users/{id}` | 改 role / disabled |
| DELETE | `/admin/users/{id}` | 软删（设 `deleted_at`，**不级联删** persona/document，留审计） |

> ⚠️ **要点**：
> - 前置：Phase 0 `users` 表已存在；本 Task 在迁移 0006 中增加 `disabled boolean default false`、`deleted_at timestamptz null` 两列。
> - 不允许把自己降级为 user / 不允许把自己禁用：`if target.id == current_user.id: 400`。
> - 至少保留一个未禁用的 admin：`if target.role == "admin" and (mutation 会让 admin 数 < 1): 409`（与角色卡"最后一个不可删"一致的语义）。

- [ ] **Step 1: 失败测试**

```python
# tests/integration/test_admin_users.py
import pytest

@pytest.mark.asyncio
async def test_admin_can_disable_normal_user(client, admin_token, normal_user):
    r = await client.patch(f"/admin/users/{normal_user.id}",
                           json={"disabled": True},
                           headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200 and r.json()["disabled"] is True

@pytest.mark.asyncio
async def test_admin_cannot_disable_self(client, admin_token, admin_user):
    r = await client.patch(f"/admin/users/{admin_user.id}",
                           json={"disabled": True},
                           headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 400

@pytest.mark.asyncio
async def test_cannot_demote_last_admin(client, admin_token, admin_user):
    r = await client.patch(f"/admin/users/{admin_user.id}",
                           json={"role": "user"},
                           headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 409
```

- [ ] **Step 2/3: 实现 + 运行 + 提交**

UI 用 `n-data-table`：列 `id / username / role / disabled / created_at / 操作`；操作列 = 编辑（弹窗）+ 禁用/启用。

提交：`feat(admin): user management with self-protection rules`。

---

## Task 4.3: persona 表 + 迁移 0006

**Files:**
- Create: `backend/app/infra/alembic/versions/0006_persona_table.py`
- Create: `backend/app/domain/persona/models.py`
- Create: `backend/app/domain/persona/schemas.py`

> ⚠️ **要点**：
> - persona 是"角色卡"；既支持公共角色（`scope='public'`，所有用户可见），也支持用户私有（`scope='user'` + `user_id`）。
> - 默认 Eira 角色由 seed 脚本插入 `id=1, scope='public'`，UI 上"最后一个不可删"约束作用在「用户当前可见的列表」（spec 锁定）。
> - SillyTavern 字段保留原名以兼容导入：`first_mes / mes_example` 等用 snake_case。

迁移：

```python
def upgrade():
    op.create_table(
        "persona",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("scope", sa.String(16), nullable=False),  # public/user
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("personality", sa.Text, nullable=False, server_default=""),
        sa.Column("scenario", sa.Text, nullable=False, server_default=""),
        sa.Column("first_mes", sa.Text, nullable=False, server_default=""),
        sa.Column("mes_example", sa.Text, nullable=False, server_default=""),
        sa.Column("system_prompt", sa.Text, nullable=False, server_default=""),
        sa.Column("avatar_asset_id", sa.BigInteger, sa.ForeignKey("asset.id"), nullable=True),
        sa.Column("live2d_asset_id", sa.BigInteger, sa.ForeignKey("asset.id"), nullable=True),
        sa.Column("voice_id", sa.String(64), nullable=True),
        sa.Column("tags", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("disabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_check_constraint("ck_persona_scope", "persona", "scope IN ('public','user')")
    op.create_check_constraint("ck_persona_scope_user_id", "persona",
        "(scope='public' AND user_id IS NULL) OR (scope='user' AND user_id IS NOT NULL)")
    op.create_index("ix_persona_user", "persona", ["user_id"])

    # users 增列（接 T4.2）
    op.add_column("users", sa.Column("disabled", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
```

提交：`infra(persona): add persona table and users disable columns`。

---

## Task 4.4: 角色卡 REST CRUD（含导入/导出 JSON）

**Files:**
- Create: `backend/app/api/rest/personas.py`（用户端）
- Create: `backend/app/api/rest/admin_personas.py`（管理端）
- Create: `backend/app/domain/persona/service.py`
- Create: `backend/app/domain/persona/repository.py`
- Create: `backend/tests/integration/test_personas.py`
- Create: `backend/tests/unit/test_persona_silly_import.py`

> ⚠️ **要点**：
> - SillyTavern 的角色卡有两种格式：(a) `Tavern Card V1`（嵌入在 PNG 的 EXIF/tEXt chunk 里 base64）；(b) `Tavern Card V2`（独立 JSON）。MVP **只支持 V2 JSON 导入**，PNG 导入留 backlog。
> - 字段映射（`SillyTavernV2 → 我们的 schema`）：
>   - `data.name → name`
>   - `data.description → description`
>   - `data.personality → personality`
>   - `data.scenario → scenario`
>   - `data.first_mes → first_mes`
>   - `data.mes_example → mes_example`
>   - `data.system_prompt → system_prompt`
>   - 其余字段忽略（`creator / character_version / extensions` 等）
> - 导出格式严格按 V2 JSON spec，便于回流。

REST：

```
# 用户端（仅可操作 scope=user 且 user_id=自己 的）
GET    /personas?scope=public|mine   # public + mine 合并默认
POST   /personas                      # 创建私有
PATCH  /personas/{id}
DELETE /personas/{id}                 # 但「最后一个可见角色不可删」交前端校验，后端只在「全删自己且 public 也都禁用」时拒绝（极端兜底）
POST   /personas/import               # 导入 SillyTavern V2 JSON → 创建私有
GET    /personas/{id}/export          # 返回 V2 JSON

# 管理端
GET    /admin/personas                 # 含 public + 全部 user 的
POST   /admin/personas                 # 默认 scope=public
PATCH  /admin/personas/{id}
DELETE /admin/personas/{id}            # 不允许删最后一个 public
```

- [ ] **Step 1: 失败测试**

```python
# tests/unit/test_persona_silly_import.py
from app.domain.persona.service import map_silly_v2

def test_silly_v2_basic_mapping():
    raw = {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": "Eira Test",
            "description": "AI guide",
            "personality": "warm and curious",
            "scenario": "at the summer palace",
            "first_mes": "你好，今天我陪你游览。",
            "mes_example": "<START>\n{{user}}: 这是哪？\n{{char}}: 这是颐和园。",
            "system_prompt": "You are Eira.",
        }
    }
    p = map_silly_v2(raw, user_id=1)
    assert p.name == "Eira Test" and p.scope == "user"
    assert p.first_mes.startswith("你好")
```

```python
# tests/integration/test_personas.py
@pytest.mark.asyncio
async def test_user_can_create_and_export_persona(client, user_token):
    body = {"name": "我的角色", "personality": "活泼", "scenario": "茶馆"}
    r = await client.post("/personas", json=body, headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 201
    pid = r.json()["id"]
    e = await client.get(f"/personas/{pid}/export", headers={"Authorization": f"Bearer {user_token}"})
    assert e.status_code == 200 and e.json()["spec"] == "chara_card_v2"
```

- [ ] **Step 2/3: 实现 + 运行 + 提交**

`service.map_silly_v2` 关键校验：
- `raw.spec in {"chara_card_v2", "chara_card"}`；否则 422 `unsupported persona format`
- 字段长度上限：`name ≤ 64`、`description/personality/scenario ≤ 8000`、`first_mes ≤ 4000`、`mes_example ≤ 16000`；超长截断 + 告警日志（不静默）

> ⚠️ **要点**：导出 endpoint 返回 `Content-Type: application/json` + `Content-Disposition: attachment; filename="persona-{id}.json"`，前端用 `<a download>` 下载。

提交：`feat(persona): rest crud with sillytavern v2 import/export`。

---

## Task 4.5: 角色卡编辑器 UI

**Files:**
- Create: `apps/web-admin/src/pages/PersonasPage.vue`
- Create: `apps/web-admin/src/components/PersonaEditor.vue`
- Create: `apps/web-admin/src/components/PersonaPreview.vue`
- Create: `apps/web-admin/src/services/personasApi.ts`
- Create: `apps/web-admin/tests/unit/PersonaEditor.spec.ts`

布局（中栏占大头）：

```
┌── 左栏 26% ─────────────┐ ┌── 中栏 38% ──────────────────────┐ ┌── 右栏 36% ──────────┐
│ Persona 列表             │ │ ▢ name                          │ │ Live2D 预览（可拖动）│
│  + 新建                  │ │ ▢ description (textarea)        │ │                      │
│  - Eira (public)         │ │ ▢ personality                   │ │ Avatar 头像          │
│  - 我的导游 (user) [选中]│ │ ▢ scenario                      │ │                      │
│  - …                     │ │ ▢ first_mes                     │ │ system_prompt 预览    │
│  ▢ 导入 V2 JSON          │ │ ▢ mes_example                   │ │ （只读 Markdown）     │
│  ▢ 导出当前              │ │ ▢ system_prompt                 │ │                      │
│  ▢ 删除                  │ │ ▢ avatar / live2d / voice 选择   │ │                      │
└─────────────────────────┘ └─────────────────────────────────┘ └──────────────────────┘
```

> ⚠️ **要点**：
> - 改动后 5s 自动保存（debounce）+ 顶栏右上角"已保存 14:32:01"；网络失败显式 toast，不静默。
> - 删除 confirm modal：要求输入 `name` 文字才允许（防误删）；最后一个不可删（前后端共同约束）。
> - 长表单 textarea 支持高度拖拽（`resize: vertical`）；`mes_example` 需提示模板：`{{user}} / {{char}} / <START>`。
> - 导入 V2 JSON：`<input type="file" accept=".json">` → 解析 → 显示对照 diff → 用户确认后写入。
> - 字段超长由后端 422 错误透传到 UI 并定位到具体字段。

- [ ] **Step 1: 失败测试**

```ts
// tests/unit/PersonaEditor.spec.ts
import { mount } from "@vue/test-utils"
import PersonaEditor from "../../src/components/PersonaEditor.vue"

it("emits save with patched fields after debounce", async () => {
  vi.useFakeTimers()
  const wrapper = mount(PersonaEditor, { props: { modelValue: { name: "x" } } })
  await wrapper.find("input[name=name]").setValue("y")
  vi.advanceTimersByTime(5000)
  expect(wrapper.emitted("save")?.[0]?.[0]).toMatchObject({ name: "y" })
})
```

- [ ] **Step 2/3: 实现 + 运行 + 提交**

提交：`feat(admin): persona editor with autosave and v2 import/export`。

---

## Task 4.6: 用户端角色卡列表 + 切换

**Files:**
- Modify: `apps/web-user/src/components/SettingsPanel.vue`（追加角色卡 tab）
- Create: `apps/web-user/src/components/PersonaSwitcher.vue`
- Create: `apps/web-user/src/services/personasApi.ts`
- Modify: `apps/web-user/src/stores/preferences.ts`（追加 `currentPersonaId`）
- Modify: `apps/web-user/src/composables/useChatSession.ts`（切换 persona 时复位会话）

> ⚠️ **要点**：
> - 切换 persona ⇒ 当前 session 不沿用：弹 confirm "切换角色将重置当前会话，确认？"；用户选"保留"则后端按新 persona_id 创建新 session。
> - 列表区分 `public` 与 `mine`，显示头像 + name + 删除（仅 `mine`）。
> - "最后一个不可删"前端约束：当 `personas.length == 1` 时禁用删除按钮 + tooltip。
> - 切换后调用 chat ws `state` 帧更新 `persona_id`，后端从 `persona` 查 system_prompt 拼入。

提交：`feat(frontend): persona switcher in settings panel with session reset`。

---

## Task 4.7: 知识库管理 UI

**Files:**
- Create: `apps/web-admin/src/pages/KnowledgePage.vue`
- Create: `apps/web-admin/src/components/DocumentRow.vue`
- Create: `apps/web-admin/src/components/DocumentPreviewModal.vue`
- Create: `apps/web-admin/src/services/knowledgeApi.ts`

复用 Phase 2 已建 `/documents` REST 端点，本任务仅做 UI。

布局：

```
中栏：
┌─ 上传区（拖拽 + 点击选择）─────┐
│ 支持 .pdf .docx .md .txt       │
│ 单文件 ≤ 50MB；可多选          │
└─────────────────────────────┘
┌─ 列表 ──────────────────────┐
│ filename  status   chunks  cost  updated_at  操作              │
│ 颐和园.pdf ready    132     ¥0.08 11:02       预览 重新向量化 删除 │
│ 历史.md  processing 12/45    -    11:05       预览（禁用） 删除  │
│ ...                                                            │
└────────────────────────────┘
```

> ⚠️ **要点**：
> - "重新向量化"按钮（spec 锁定）：调 `POST /documents/{id}/reprocess`；按钮二次 confirm（"将重新解析、分块并产生 Embedding 调用，预估成本 ¥{est}"）。
> - 估算成本来自 `meta_json.last_chunk_count * embed_unit_price`（前端读 `system_setting/embedding_unit_price`）；首次重处理时 `last_chunk_count=null`，文案改"无法预估"。
> - status 进行中（pending/processing）轮询：每 3s `GET /documents?ids=...&fields=status,chunks_done,chunks_total`；ready 或 failed 后停。
> - 预览：左侧文件原文 segments 列表，右侧 chunk 列表 + 嵌入分数（点 chunk 高亮原文段）。预览仅返回前 50 chunks，避免大文件卡死。
> - 失败 chunk 行红字显示错误原因；提供"仅重试失败"按钮 → `POST /documents/{id}/reprocess?only_failed=true`。

提交：`feat(admin): knowledge base management ui with reprocess and preview`。

---

## Task 4.8: 资源管理 UI（背景 / Live2D / 头像统一）

**Files:**
- Create: `apps/web-admin/src/pages/AssetsPage.vue`
- Create: `apps/web-admin/src/components/AssetGrid.vue`
- Create: `apps/web-admin/src/components/AssetUploadModal.vue`
- Create: `apps/web-admin/src/services/assetsApi.ts`

> ⚠️ **要点**：
> - 顶部 tab：背景 / Live2D 模型 / 头像；切 tab 即换 `kind` 参数。
> - 背景：缩略图墙（image 直接显示，video 用首帧 `poster`）；点击预览大图；操作 = 重命名 / 删除。
> - Live2D：缩略图（用上传时附带 `meta_json.thumbnail_oss_key` 或 model.json 中第一张 texture）；点击 → 右栏跑模型预览（`Live2DCanvas` 复用），用于试看动作 / 表情。
> - 头像：圆形 96px 缩略；删除时检查是否被 persona 引用（`avatar_asset_id`），若是则提示 `409: 该头像被 N 个角色引用，先解除后再删除`。
> - 上传：Modal 走 `POST /assets` multipart；进度条；失败保留入口续传（MVP 不做断点续传，保留文案"失败请重新上传")。
> - 配额触发：上传前先 `GET /assets/quota?kind=...` 显示 `已用 3/5`；超额拒绝并提示删除老的。

提交：`feat(admin): unified asset management ui with quota awareness`。

---

## Task 4.9: 系统设置（默认模型 / Web Search 预算 / 配额 / 安全黑名单）

**Files:**
- Create: `backend/app/infra/alembic/versions/0007_system_setting.py`
- Create: `backend/app/domain/system/models.py`
- Create: `backend/app/domain/system/service.py`
- Create: `backend/app/api/rest/admin_settings.py`
- Create: `apps/web-admin/src/pages/SettingsPage.vue`
- Create: `apps/web-admin/src/services/settingsApi.ts`
- Create: `backend/tests/integration/test_admin_settings.py`

迁移：

```python
op.create_table(
    "system_setting",
    sa.Column("key", sa.String(128), primary_key=True),
    sa.Column("value_json", sa.JSON, nullable=False),
    sa.Column("description", sa.String(255), nullable=False, server_default=""),
    sa.Column("updated_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
)
```

> ⚠️ **要点**：
> - 设置项是「键值对」，不动 schema；新增/废弃只动 seed + UI。
> - **不在 UI 暴露真实 API key**：所有 `*_api_key` 字段后端读 env，不允许通过 UI 写入；UI 只显示「Provider 已配置 ✅ / 未配置 ⚠️」状态。
> - 修改后 fan-out：通过 `redis pub/sub channel "settings:reload"` 触发各副本刷新本地 cache（cache TTL 60s 兜底）。
> - 写操作必经 `audit_log`（T4.10）。

UI 分组：

| 组 | 键 | 类型 | 默认 |
|---|---|---|---|
| LLM 默认 | `llm.default_provider` | enum(deepseek/openai/...) | deepseek |
| LLM 默认 | `llm.default_model` | str | deepseek-chat |
| Embedding | `embedding.default_provider` | enum | openai |
| Embedding | `embedding.unit_price_per_1k_tokens` | float | 0.00002 |
| Web Search | `search.default_provider` | enum(tavily/bocha) | tavily |
| Web Search | `search.daily_budget` | int | 200 |
| 配额 | `quota.background_per_user` | int | 5 |
| 配额 | `quota.live2d_per_user` | int | 10 |
| 配额 | `quota.document_per_user` | int | 100 |
| 安全 | `safety.input_blacklist` | list[str] | [...] |
| 安全 | `safety.output_redact_patterns` | list[str] | [`sk-[A-Za-z0-9]+`, `AKIA[0-9A-Z]{16}`] |
| 语音 | `voice.persist_user_audio` | bool | false |

REST：

```
GET   /admin/settings              # 全部 key（屏蔽含 api_key 的真值）
PATCH /admin/settings              # body: {key: value_json, ...}（一次可改多个）
GET   /admin/settings/providers    # provider 配置状态（仅返回 configured: true/false）
```

- [ ] **Step 1: 失败测试**

```python
@pytest.mark.asyncio
async def test_admin_can_update_search_budget(client, admin_token):
    r = await client.patch("/admin/settings",
        json={"search.daily_budget": 500},
        headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    g = await client.get("/admin/settings", headers={"Authorization": f"Bearer {admin_token}"})
    assert g.json()["search.daily_budget"] == 500

@pytest.mark.asyncio
async def test_admin_setting_response_does_not_leak_keys(client, admin_token):
    r = await client.get("/admin/settings/providers",
        headers={"Authorization": f"Bearer {admin_token}"})
    body = r.json()
    for p in body:
        assert "api_key" not in p
        assert set(p.keys()) <= {"name", "configured", "model_default"}
```

- [ ] **Step 2/3: 实现 + 运行 + 提交**

提交：`feat(system): system settings with redis pubsub fanout`。

---

## Task 4.10: 审计日志

**Files:**
- Create: `backend/app/infra/alembic/versions/0008_audit_log.py`
- Create: `backend/app/core/middleware/audit.py`
- Create: `backend/app/api/rest/admin_audit.py`
- Create: `apps/web-admin/src/pages/AuditPage.vue`

迁移：

```python
op.create_table(
    "audit_log",
    sa.Column("id", sa.BigInteger, primary_key=True),
    sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("actor_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True),
    sa.Column("actor_role", sa.String(16), nullable=False),
    sa.Column("method", sa.String(8), nullable=False),
    sa.Column("path", sa.String(255), nullable=False),
    sa.Column("status", sa.Integer, nullable=False),
    sa.Column("ip", sa.String(45), nullable=True),
    sa.Column("user_agent", sa.String(255), nullable=True),
    sa.Column("body_summary", sa.String(2000), nullable=False, server_default=""),
)
op.create_index("ix_audit_actor_ts", "audit_log", ["actor_id", "ts"])
op.create_index("ix_audit_path_ts", "audit_log", ["path", "ts"])
```

> ⚠️ **要点**：
> - middleware 记录 `/admin/**` 路径下所有 POST/PUT/PATCH/DELETE；GET 不记。
> - `body_summary`：把请求 body JSON 打平后取前 2000 字符；**字段名包含 `password / token / api_key / secret` 的 value 替换为 `***`**。
> - response 4xx/5xx 也记，便于排查。
> - 查询页：表格 + 顶部过滤（actor / path / 时间范围）；分页；导出 CSV（5000 条上限）。
> - 保留期：默认 180 天，超期由 cron 删除（T4.10 不做 cron，仅记入 spec 修订段，留 Phase 5 一起做）。

提交：`feat(audit): admin audit log middleware and viewer page`。

---

## 🚦 Validation Gate G-4.1 · 管理员功能完整性

| 项 | 内容 |
|---|---|
| 指标 | 管理员可在不进数据库的情况下完成：禁用用户 / 增删改角色卡 / 上传重处理删除文档 / 上传删除资源 / 修改默认模型与预算 / 查询审计日志 |
| 阈值 | 上述 6 个动作 100% 通过 Playwright E2E |
| 测试方法 | `tests/e2e/admin-shell.spec.ts` 跑全流程 + 手动 checklist |
| 数据源 | `docs/superpowers/validations/G-4.1.md` 含 Playwright 报告链接 + checklist |
| 通过分支 | 进入 G-4.2 |
| 不通过分支 | 任一项不通过 → 回相应 task；若是 UI 阻塞 → 优先用 `@eira/ui-shared` 兜底再优化 |

---

## 🚦 Validation Gate G-4.2 · 角色卡编辑器可用性

| 项 | 内容 |
|---|---|
| 指标 | 5 名内部测试者完成"创建一张完整 SillyTavern 风格角色卡 → 切换到用户端使用"的全流程；记录耗时与卡点 |
| 阈值 | 平均耗时 ≤ 8 分钟；无人放弃；自动保存功能用户感知正确率 100% |
| 测试方法 | 评测脚本 `scripts/persona_usability.md`；提供 V2 JSON 模板让评测者可选导入或从零编辑 |
| 数据源 | `docs/superpowers/validations/G-4.2.md` 含 5 份记录 |
| 通过分支 | 进入 G-4.3 |
| 不通过分支 | 卡点集中在某字段 → 加 placeholder/示例；自动保存被怀疑丢失 → 顶栏加"上次保存 N 秒前"实时刻度；耗时 > 8min → 提供「从模板新建」预设 |

---

## 🚦 Validation Gate G-4.3 · 知识库重新向量化稳定性

| 项 | 内容 |
|---|---|
| 指标 | 对 5 篇 ready 文档点击「重新向量化」→ 监控状态切回 processing → ready；过程中其他用户检索是否中断 |
| 阈值 | 100% 重处理成功；处理中检索仍可命中（旧 chunks 在事务结束前可见，新 chunks 事务后切换）；P95 重处理耗时 ≤ 60s（30 页 PDF 量级，沿用 G-2.1 阈值） |
| 测试方法 | 脚本：1 后台 reprocess + 1 前台连续 retrieve 查询；`docs/superpowers/validations/G-4.3.md` 记录响应是否中断 |
| 数据源 | structlog grep `event=knowledge.reprocess` + 前台 chat 日志 |
| 通过分支 | 进入 G-4.4 |
| 不通过分支 | 检索中断 → 把 `replace_chunks` 改为先写新 chunks（带临时 version_tag）再原子切换 active version；超时 → 排查 embedding provider 限流，调小 batch_size |

---

## 🚦 Validation Gate G-4.4 · 权限边界 + 审计完整性

| 项 | 内容 |
|---|---|
| 指标 | (a) 普通用户访问 `/admin/**` 全部 403；(b) admin 自禁/降级被拒；(c) 审计日志 100% 覆盖 admin 写操作；(d) `body_summary` 不含密钥/密码原值 |
| 阈值 | 4 项全 pass |
| 测试方法 | `tests/integration/test_admin_authz.py` + `tests/integration/test_audit_coverage.py`；后者跑 30 个写操作并断言每个都有 audit 记录 |
| 数据源 | `docs/superpowers/validations/G-4.4.md` |
| 通过分支 | 合入，标 `gate-G-4-passed`；进入 Phase 5 |
| 不通过分支 | 漏记 → 检查 middleware 是否提前 return；密钥泄露 → 全局红线，立即吊销暴露 key + 修 sanitizer + 全量日志审计 |

---

## 完成状态

Phase 4 完成 ⇔ G-4.1 / 4.2 / 4.3 / 4.4 全部 passed。MVP + 后台运营基础已具备，进入 Phase 5 运营看板。

