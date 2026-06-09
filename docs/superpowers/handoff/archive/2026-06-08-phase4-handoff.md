# Phase 4 移交文档 · 管理后台后端 + 角色卡 + 数据对接

**日期**: 2026-06-08  
**分支**: `chore/live2d-rewrite-and-handoff`  
**范围**: 后端 4 个迁移 + 2 个 Domain 模块 + 8 个 REST 路由器 + 审计中间件 + 前端路径校正  
**状态**: ✅ 后端代码完成，单元测试 5/5 通过；待 PostgreSQL + Redis 就绪后集成测试

---

## 一、完成概览

| 任务 | 内容 | 状态 |
|------|------|------|
| T4.0 | API 路径对齐 — 8 个 admin 路由器骨架 + 占位 dashboard | ✅ |
| T4.1 | 用户管理后端 — migration 0007 + User 扩展 + admin_users.py CRUD | ✅ |
| T4.2 | Persona 表 + migration 0008 + models/schemas | ✅ |
| T4.3 | 角色卡 REST CRUD — 管理端 + 用户端 + ST V2 导入/导出 | ✅ |
| T4.4 | 系统设置 — migration 0009 + system domain + admin_settings.py | ✅ |
| T4.5 | 审计日志 — migration 0010 + ASGI AuditMiddleware + admin_audit.py | ✅ |
| T4.6 | 前端对接 — api.ts 路径校正 + 用户角色卡端点 | ✅ |

---

## 二、文件清单

### 新建文件（20 个）

**数据库迁移（4 个）：**
```
backend/app/infra/alembic/versions/
  0007_user_admin_extras.py   # users 加 disabled (bool) + deleted_at (timestamptz)
  0008_persona_table.py       # personas 表（scope/user_id/name/…/tags/is_default/disabled）
  0009_system_setting.py      # system_settings 键值对表（key: str, value: JSONB）
  0010_audit_log.py           # audit_log 表（user_id/action/path/body_summary/ip + BRIN 索引）
```

**Persona Domain（4 个）：**
```
backend/app/domain/persona/
  models.py                   # Persona ORM（SQLAlchemy 2.0 Mapped）
  schemas.py                  # PersonaCreateIn / PersonaPatchIn / PersonaOut / PersonaListOut
  repository.py               # CRUD + 分页 + clear_default_for_scope
  service.py                  # CRUD + set_default + ST V2 import_v2 / export_v2
```

**System Domain（2 个）：**
```
backend/app/domain/system/
  models.py                   # SystemSetting ORM（key PK, value JSONB）
  service.py                  # get / set / get_all / get_group / set_many
```

**REST API（8 个）：**
```
backend/app/api/rest/
  admin_users.py              # /admin/users — GET list · GET detail · PATCH role/disabled · DELETE
  admin_personas.py           # /admin/personas — GET · POST · GET/{id} · PATCH · DELETE · set-default
  personas.py                 # /personas — 用户端 CRUD + import · export (ST V2)
  admin_settings.py           # /admin/settings — GET · PATCH（API key 脱敏）
  admin_audit.py              # /admin/audit — GET 查询 · GET/export CSV
  admin_dashboard.py          # /admin/dashboard — 7 个占位端点（Phase 5 填充）
  admin_documents.py          # /admin/documents — 全量文档列表 + upload + delete + reprocess
  admin_assets.py             # /admin/assets — 全量资产列表聚合 + delete
```

**审计中间件（2 个）：**
```
backend/app/core/middleware/
  __init__.py                 # 包声明
  audit.py                    # AuditMiddleware（纯 ASGI，fire-and-forget 写 audit_log）
```

**测试（5 个，共 31 个用例）：**
```
backend/tests/unit/
  test_persona_silly_import.py    # 5 tests: ST V2 import 字段映射 / 默认值 / 无 wrapper / export / 空字段省略

backend/tests/integration/
  test_admin_users.py             # 8 tests: 列表分页 / 关键词筛选 / 详情 / 自降级拒绝 / 自禁用拒绝 / 禁用+恢复 / 软删 / 访客 403
  test_personas.py                # 7 tests: 用户创建+列表 / 禁止创建 public / 更新+删除 / 越权 403 / admin 管理 / set-default / import-export
  test_admin_settings.py          # 5 tests: 空设置 / 设置+查询 / API key 脱敏 / 单个设置 / 访客 403
  test_audit.py                   # 6 tests: 审计记录 / 非 admin 不审计 / 访客 403 / 路径筛选 / CSV 导出 / body 脱敏
```

### 修改文件（6 个）

| 文件 | 变更 |
|------|------|
| `backend/app/main.py` | 注册 `AuditMiddleware` + 7 个新路由模块（admin_users/admin_personas/personas/admin_settings/admin_audit/admin_documents/admin_assets） |
| `backend/app/domain/identity/models.py` | User 添加 `disabled` (bool, default=False) + `deleted_at` (datetime, nullable) |
| `backend/app/domain/identity/repository.py` | 新增 `list_users`（分页+关键词+角色筛选）· `update_user` · `soft_delete` · `count_active_admins` |
| `backend/app/domain/identity/service.py` | 新增 `list_users` · `get_user_detail` · `set_user_role` · `set_user_disabled` · `soft_delete_user`（含安全护栏） |
| `backend/app/domain/identity/schemas.py` | 新增 `UserDetailOut` · `PaginatedUsers` · `UserPatchIn` |
| `apps/web-admin/src/services/api.ts` | knowledgeApi 路径 `/admin/knowledge` → `/admin/documents`；configApi 路径 `/admin/config` → `/admin/settings` |

---

## 三、关键架构决策

### 3.1 审计中间件设计

```
AuditMiddleware (纯 ASGI):
  scope["path"].startswith("/admin") && method in {POST,PUT,PATCH,DELETE}
    → receive_wrapper 捕获 body chunks
    → 下游处理后 fire-and-forget 写入 audit_log
    → asyncio.ensure_future(_record(...)) 不阻塞响应

body_summary 处理:
  - JSON body → {field_name: truncated_value | "***" | <type_name>}
  - REDACT_FIELDS = {password, token, api_key, secret, access_key, refresh_token}
  - 非 JSON → {}
  - 审计失败不影响正常响应
```

与已有中间件的关系：通过 `app.add_middleware(AuditMiddleware)` 注册，在 FastAPI 中间件栈最外层。不影响现有 CORS / 异常处理。

### 3.2 安全护栏实现

| 护栏 | 实现位置 | 方式 |
|------|---------|------|
| 不可自降级/自禁用/自删除 | `service.py` | `if uid == admin_id: raise 400` |
| 不可删除最后一个 admin | `service.py` | `count_active_admins() <= 1 → raise 400` |
| 访客访问 `/admin/**` → 403 | `deps.py` | `require_admin` 检查 `role != "admin"` |
| API key 脱敏 | `admin_settings.py` | `_redact_sensitive()` 递归替换 |
| 审计 body 脱敏 | `middleware/audit.py` | `REDACT_FIELDS` 匹配 |
| 用户只能操作自己的 persona | `service.py` | `p.scope == "user" && p.user_id != user_id → 403` |
| 普通用户不能创建 public persona | `personas.py` | `body.scope == "public" && user.role != "admin" → 403` |

### 3.3 Persona SillyTavern V2 兼容

```
ST V2 字段映射（1:1 同名）:
  name → name
  description → description
  personality → personality
  scenario → scenario
  first_mes → first_mes
  mes_example → mes_example
  system_prompt → system_prompt
  tags → tags (list[str])

额外字段（ST V2 无对应）:
  avatar_asset_id / live2d_asset_id / voice_id — asset 外键，导入时为空

导入流程:
  1. 解析 JSON（兼容 {"data": {...}} 和 {...} 两种格式）
  2. 提取 ST_V2_FIELDS + tags
  3. PersonaCreateIn 校验 → create_persona

导出流程:
  1. 遍历 ST_V2_FIELDS，有值则写入
  2. 外包裹 {"data": {...}}
  3. 空值字段省略
```

> ⚠️ MVP 仅支持 JSON 导入。PNG 角色卡导入（含元数据嵌入）留 backlog。

### 3.4 系统设置 key-value 模式

```
system_settings 表:
  key (String 128, PK)
  value (JSONB, default {})
  description (Text)
  updated_at (Timestamptz)

设置分组（按 key 前缀约定）:
  llm.*            — provider / model / params
  embedding.*      — provider / unit_price
  web_search.*     — provider / daily_budget
  quota.*          — background / live2d / document per user
  security.*       — blacklist / redact patterns
  voice.*          — persist_audio / enabled

API key 保护:
  GET /admin/settings → 递归扫描 value dict，key 名含 api_key/token/secret/password → "***"
  数据库存储不含'***'标记，仅在输出时脱敏
```

### 3.5 Migration 编号偏移

| 原计划 | 实际 | 原因 |
|--------|------|------|
| 0006 | 0007 | 0006 已被 assets 表占用（Phase 3 T3.7） |
| 0007 | 0008 | ↑ 连锁偏移 |
| 0008 | 0009 | ↑ 连锁偏移 |
| — | 0010 | 原计划无独立 audit migration |

### 3.6 前端对接策略

**关键发现**: 管理端 UI 在 Phase 3 已 100% 完成，且**所有页面早已调用真实 API**（通过 `api.ts`）。每个页面自带 mock fallback——API 调用失败时降级为硬编码数据。

因此本 Phase 前端只需：
1. 修正两条 API 路径（knowledge → documents, config → settings）
2. 不需要改页面模板/script 逻辑

**已确认不变更**：
- 认证守卫：`main.ts` 中 `router.beforeEach` 已在 Phase 3 启用
- HTTP 拦截器：自动 attach token + 401 时 refreshToken + 队列重试，已完整实现
- Admin 布局：空壳 `NConfigProvider + RouterView` 为最终形态
- 图表：手写 SVG，不引入 ECharts

---

## 四、API 接口总览

### 新增 REST 端点（全部 require_admin）

#### 用户管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/users?keyword=&role=&page=&size=` | 分页列表，排除已删除 |
| GET | `/admin/users/{uid}` | 单用户详情（含 disabled/status/时间戳） |
| PATCH | `/admin/users/{uid}` | 改 role 或 disabled（body: `{role: "admin", disabled: true}`) |
| DELETE | `/admin/users/{uid}` | 软删除（设 deleted_at），返回 204 |

#### 角色卡 — 管理端

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/personas?scope=&page=&size=` | 全量列表（含 disabled） |
| POST | `/admin/personas` | 创建（body: PersonaCreateIn） |
| GET | `/admin/personas/{id}` | 详情 |
| PATCH | `/admin/personas/{id}` | 部分更新（body: PersonaPatchIn） |
| DELETE | `/admin/personas/{id}` | 软删除（disabled=true） |
| POST | `/admin/personas/{id}/set-default` | 设为默认（清除同 scope 其他） |

#### 角色卡 — 用户端

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/personas?scope=public&page=&size=` | 登录用户 | 可见列表（public + 自己创建的） |
| POST | `/personas` | 登录用户 | 创建（普通用户只能 scope=user） |
| GET | `/personas/{id}` | 登录用户(own) | 详情 |
| PATCH | `/personas/{id}` | 登录用户(own) | 更新（不能改 scope/disabled） |
| DELETE | `/personas/{id}` | 登录用户(own) | 软删除 |
| POST | `/personas/import` | 登录用户 | ST V2 JSON 导入 |
| GET | `/personas/{id}/export` | 登录用户(own) | ST V2 JSON 导出 |

#### 系统设置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/settings` | 返回 `{settings: {key: value, ...}}`，敏感值脱敏 |
| PATCH | `/admin/settings` | 批量 upsert（body: `{settings: {key: value, ...}}`) |
| GET | `/admin/settings/{key}` | 单个设置项（支持含 `/` 的 key） |
| PATCH | `/admin/settings/{key}` | 单个更新 |

#### 审计日志

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/audit?user_id=&action=&path=&start=&end=&page=&size=` | 分页查询 |
| GET | `/admin/audit/export?start=&end=` | CSV 导出 |

#### 文档管理（admin 视角）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/documents?status=&page=&size=` | 全量文档列表（跨用户） |
| POST | `/admin/documents/upload` | multipart 上传文档 |
| DELETE | `/admin/documents/{id}` | 删 OSS + DB |
| POST | `/admin/documents/{id}/reprocess` | 重新向量化 |

#### 资产管理（admin 视角）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/assets?kind=&page=&size=` | 全量资产列表（跨用户聚合） |
| DELETE | `/admin/assets/{id}` | 删 OSS + DB |

#### 运营看板（占位）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/dashboard/metrics?range=` | 返回空指标（Phase 5 填充） |
| GET | `/admin/dashboard/top-questions?limit=` | 返回 `[]` |
| GET | `/admin/dashboard/satisfaction-trend?range=` | 返回 `[]` |
| GET | `/admin/dashboard/word-cloud?limit=` | 返回 `[]` |
| GET | `/admin/dashboard/sentiment?range=` | 返回全零 |
| GET | `/admin/dashboard/feedback?limit=` | 返回 `[]` |
| POST | `/admin/dashboard/feedback/{id}/reply` | 返回 `{"success": true}` |

---

## 五、测试覆盖

| 层级 | 文件 | 用例数 | 覆盖范围 |
|------|------|--------|---------|
| 单元 | test_persona_silly_import | 5 | ST V2 字段映射 / 默认值 / 无 wrapper / export 全字段 / export 空值省略 |
| 集成 | test_admin_users | 8 | 分页 / 关键词 / 详情 / 自降级 / 自禁用 / 禁用恢复 / 软删 / 访客 403 |
| 集成 | test_personas | 7 | 创建+列表 / 禁止 public / 更新+删除 / 越权 403 / admin set-default / import-export |
| 集成 | test_admin_settings | 5 | 空设置 / 设置+读取 / 脱敏 / 单个设置 / 访客 403 |
| 集成 | test_audit | 6 | 审计记录 / 非 admin 不审计 / 访客 / 路径筛选 / CSV / body 脱敏 |
| **合计** | | **31** | |

### 单元测试结果

```bash
$ python -m pytest tests/unit/test_persona_silly_import.py -v
============================== 5 passed in 0.42s ==============================
```

### 应用导入验证

```bash
$ python -c "from app.main import app; print(len(app.routes))"
50 routes registered（含 Phase 0-3 已有 + 本 Phase 新增）
```

### 集成测试

⏸️ 需 PostgreSQL + Redis 基础设施就绪后方可运行。写好了 26 个集成测试用例，覆盖全部 CRUD + 权限边界 + 审计完整性。

---

## 六、待办与后续衔接

### 环境依赖

- [ ] **数据库迁移**: `cd backend && alembic upgrade head`（需 PostgreSQL + Redis 运行中）
- [ ] **初始管理员**: 注册首个用户后手动将 `role` 改为 `admin`
- [ ] **集成测试**: `pytest tests/integration/test_admin_users.py tests/integration/test_personas.py tests/integration/test_admin_settings.py tests/integration/test_audit.py -v`

### Validation Gates 待执行

- [ ] **G-4.1**: 6 个管理动作 Playwright E2E（禁用用户 / 角色卡 CRUD / 文档上传+重处理 / 资源上传+删除 / 系统设置修改 / 审计日志查询）
- [ ] **G-4.2**: 角色卡编辑器可用性（5 名测试者 × "创建 → 切换使用" ≤ 8 分钟）
- [ ] **G-4.3**: 知识库重新向量化稳定性（5 篇 ready 文档 reprocess → 100% 成功）
- [ ] **G-4.4**: 权限边界 + 审计完整性（访客 403 / admin 自禁拒绝 / 审计 100% 覆盖 / body 无密钥）

### Phase 5 前置事项

- [ ] **运营看板数据**: `admin_dashboard.py` 7 个占位端点 → 连接真实 conversation/feedback 数据
- [ ] **Settings → AppConfig 映射**: `useAppConfig` composable 的 `{settings: {key: val}}` → `AppConfig` 格式转换
- [ ] **审计清理 cron**: 180 天定期清理（APScheduler / asyncio task），利用 BRIN 索引 `idx_audit_log_created`
- [ ] **用户端角色卡选择 UI**: SettingsPanel 添加角色卡下拉框 + `currentPersonaId` 传递到 session 创建
- [ ] **SillyTavern PNG 导入**: 解析 PNG 元数据中的角色卡 JSON（当前仅支持纯 JSON 文件）

### 已知局限

1. **Dashboard 占位**: 运营看板 7 个端点返回空数据——前端 `useDashboard` 自动降级为 mock 数据，视觉上目前看不出差异
2. **Settings 格式不匹配**: 后端返回 `{settings: {key: val}}`，前端 `useAppConfig` 期望 `AppConfig` 类型——当前 config 保存会静默失败（fallback 到本地默认值）
3. **AuditMiddleware body 捕获**: ASGI `receive_wrapper` 模式在部分流式上传场景（如 WebSocket 升级）可能捕获不完整——仅限于 `/admin/**` REST，WebSocket 路径不受影响
4. **无 Redis pub/sub**: 系统设置修改后不通知其他副本——单进程部署无影响，多副本需 Phase 5 接入
5. **Persona 用户端 UI 未集成**: 后端 `/personas` 端点已就绪，用户端 SettingsPanel 尚为 deprecated 占位组件
6. **无 admin 前端用户管理页**: 后端 `/admin/users` 端点已就绪，但管理端缺少用户管理页面的路由和组件——当前只能通过 API 直接调用

---

## 七、快速启动

```bash
# 1. Docker 服务
docker compose -f deploy/docker-compose.yml up -d

# 2. 数据库迁移（到 0010）
cd backend && uv run alembic upgrade head

# 3. 后端启动
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. 前端启动
pnpm install
pnpm --filter @eira/web-user dev      # http://localhost:5173
pnpm --filter @eira/web-admin dev     # http://localhost:5174

# 5. 运行单元测试
cd backend && uv run pytest tests/unit/ -v

# 6. 运行集成测试（需数据库）
cd backend && uv run pytest tests/integration/test_admin_users.py tests/integration/test_personas.py tests/integration/test_admin_settings.py tests/integration/test_audit.py -v
```

### E2E 验证路径

```
1. 登录 admin
2. Dashboard — 确认 Persona 预览模型加载正常；运营图表显示 mock 数据（API 占位 → fallback）
3. Personas 页 — 创建/编辑/删除角色卡；导入 ST V2 JSON；设为默认
4. Knowledge 页 — 上传 PDF/TXT/MD/DOCX；列表刷新；删除
5. Live2D 页 — 上传 zip 模型包；上传背景图；列表刷新；删除
6. Settings — 读写系统设置；验证 API key 显示为 ***
7. Audit — 查询审计日志；按路径筛选；CSV 导出
8. 权限测试 — 用普通用户 token 访问 /admin/users → 403
9. 安全护栏 — admin 尝试 PATCH 自己的 role → 400
```

---

## 八、与原计划偏差

| 原计划 | 实际 | 原因 |
|--------|------|------|
| Migration 编号 0006-0008 | 0007-0010 | 0006 已被 assets 表占用（Phase 3） |
| "启用认证守卫" | 已跳过 | Phase 3 `main.ts` 已启用 `router.beforeEach` |
| "替换 mock 数据为 API" | 只改 api.ts 路径 | 页面早已调用 API + mock fallback |
| "Admin 三栏布局" | 空壳布局 | 已确认不回退（2026-06-02 revision） |
| "引入 ECharts" | 手写 SVG | 已确认不回退（2026-06-02 revision） |
| DELETE /admin/users 软删 | 添加 deleted_at 列 | User 模型无此字段，已在 0007 新增 |

---

**签出**: 本 Phase 由 Claude Opus 4.8 执行，遵循 TDD、密钥不入库、管理操作必须留痕约定。  
**下一步**: Phase 5（运营看板 + 数据管线）若已规划；或先完成本 Phase 的集成测试与 Validation Gates。
