# Phase 4 功能缺口闭合 Handoff — 4 项遗留问题

> 日期: 2026-06-08
> 分支: `chore/live2d-rewrite-and-handoff`
> 范围: 前端 4 文件（3 删除 + 3 修改）+ 后端 3 文件修改
> 前置: `2026-06-08-phase4-fixes-handoff.md` · `2026-06-08-phase4-p0-fixes-handoff.md`

---

## 修复概览

| # | 优先级 | 问题 | 状态 |
|---|--------|------|------|
| 3.1 | 🟡 P1 | Content/*.vue 死代码未清理，两套 UI 并存 | ✅ |
| 3.2 | 🟡 P1 | Persona 创建表单仅 4 字段，缺导入 JSON 按钮 | ✅ |
| 3.3 | 🟢 P2 | Knowledge Preview RAG 端点待验证 | ✅ (已验证，已闭合) |
| 3.4 | 🟡 P1 | persona_config.py / voice.py 共 3 处 TODO 占位未清理 | ✅ |

---

## 文件清单

### 前端

| 文件 | 操作 | 涉及问题 |
|------|------|----------|
| `apps/web-admin/src/pages/Content/Personas.vue` | **删除** | 3.1 |
| `apps/web-admin/src/pages/Content/Knowledge.vue` | **删除** | 3.1 |
| `apps/web-admin/src/pages/Content/Live2D.vue` | **删除** | 3.1 |
| `apps/web-admin/src/services/types.ts` | 修改 — 扩展 Persona / PersonaCreate 接口 | 3.2 |
| `apps/web-admin/src/services/api.ts` | 修改 — 新增 personaApi.import() | 3.2 |
| `apps/web-admin/src/pages/Dashboard.vue` | 修改 — NCollapse 表单 + 导入按钮 | 3.2 |

### 后端

| 文件 | 操作 | 涉及问题 |
|------|------|----------|
| `backend/app/api/rest/admin_personas.py` | 修改 — 新增 POST /import 端点 | 3.2 |
| `backend/app/api/rest/persona_config.py` | 修改 — 接入 system_settings 持久化 | 3.4 |
| `backend/app/api/rest/voice.py` | 修改 — 读取 Settings.asr 配置 | 3.4 |

**未修改文件：**
- `backend/app/api/rest/admin_documents.py` — 端点已验证存在且正常工作（3.3）

---

## 3.1 — 删除 Content/ 死代码

### 问题诊断

- `main.ts` 路由仅指向 `Dashboard.vue`（`/dashboard`），无任何 Content/*.vue 路由
- Phase 4 Fixes 将 Personas/Knowledge/Live2D 从独立路由页面迁移为 Dashboard.vue 内部视图（`currentView='xxx'`）
- P0 修复还多余地修改了 `Content/Live2D.vue`，但该文件从未被路由引用
- 三文件中功能均为残片（Personas 无 Modal、Knowledge 无 Preview、Live2D 无画布）

### 修复内容

删除 `Content/Personas.vue`、`Content/Knowledge.vue`、`Content/Live2D.vue` 及空目录 `Content/`。

---

## 3.2 — Persona 创建表单扩展 + 导入 JSON

### 问题诊断

**前后端字段不对齐：**

| 后端 PersonaCreateIn | 前端 PersonaCreate（旧） |
|------|------|
| name ✅ | name ✅ |
| description ✅ | description ✅ |
| personality | ❌ 缺 |
| scenario | ❌ 缺 |
| first_mes | ❌ 缺 |
| mes_example | ❌ 缺 |
| system_prompt | ❌ 缺 |
| avatar_asset_id | ❌ 缺 |
| live2d_asset_id | ❌ 缺（且前端错误命名为 model_id） |
| voice_id | voice_id ✅ |
| tags | ❌ 缺 |
| scope | ❌ 缺 |
| is_default | ❌ 缺 |

**导入端点缺失：**
- 后端 `POST /personas/import` 已存在（用户端路由），但 admin 路由无对应端点
- 前端 api.ts 无 import 方法

### 修复内容

#### types.ts

`Persona` 接口从 8 字段扩展到 18 字段（对齐 `PersonaOut`），`PersonaCreate` 从 4 字段扩展到 13 字段（对齐 `PersonaCreateIn`）。修正字段名 `model_id` → `live2d_asset_id`。

#### api.ts

新增 `personaApi.import(data, scope)` → `POST /admin/personas/import`。

#### Dashboard.vue

**Persona Modal 重构：** 使用 `NCollapse` / `NCollapseItem` 组件分为三组：

| 分组 | 默认状态 | 字段 | 组件 |
|------|---------|------|------|
| 基础信息 | 展开 | name（必填）、description | NInput + NInput textarea |
| 角色定义 | 折叠 | personality、scenario、first_mes、mes_example、system_prompt | NInput textarea × 5 |
| 高级设置 | 折叠 | live2d_asset_id、voice_id、tags、scope、is_default | NInput + NSelect + NSwitch |

- `tags` 使用逗号分隔输入，提交时 `split(',').map(trim).filter(Boolean)`
- `live2d_asset_id` 表单内为字符串（兼容 NInput），提交时 `Number(raw)` 转换为 int
- 编辑模式预填全部字段
- 新增 `NCollapse`、`NCollapseItem`、`NSelect`、`NSwitch` 到 naive-ui 导入

**导入 JSON 按钮：** "创建新角色卡"按钮旁添加"导入 JSON"，点击触发隐藏 `<input type="file" accept=".json">` → `FileReader` → `JSON.parse` → `personaApi.import()` → 刷新列表。

#### admin_personas.py

新增端点（复用 `personas.py` 的 `ImportIn` schema + `PersonaService.import_v2()`）：

```python
@router.post("/import", status_code=status.HTTP_201_CREATED, response_model=PersonaOut)
async def import_persona_admin(body: ImportIn, _admin, svc) -> PersonaOut
```

路由总数从 6 → 7。

---

## 3.3 — Knowledge Preview RAG 端点

### 验证结论：已闭合

`admin_documents.py:229` 的 `GET /{document_id}` 端点返回 `DocumentDetailOut`（含 `chunks: list[ChunkOut]`）。前端 `knowledgeApi.getDetail(id)` 已正确调用此端点，`Dashboard.vue` 的 `handleKnowledgePreview()` 完整展示 chunks（前 10 条截断 150 字符 + NSpin loading + 空状态提示）。

**此缺口在 Phase 4 Fixes（P1-5）中已解决，无需额外修改。**

---

## 3.4 — TODO 占位清理

### 3.4.1 persona_config.py

**现状：**
- `get_persona_config()` 返回空 `PersonaConfig()` — 前端每次刷新丢失配置
- `update_persona_config()` 返回 `{"success": True}` 但不持久化

**修复方案：** 复用已有的 `system_settings` 表（符合架构设计 §7.2"运行时配置：system_settings 表存可热改的项"），不新建 migration。

**实现：**
- 添加 `db: AsyncSession = Depends(get_db_session)` 参数到两个端点
- `GET /` → `SystemSettingService(db).get("persona_config")` → JSONB 反序列化为 `PersonaConfig`，无记录返回默认值
- `PATCH /` → 读取现有配置 → merge `updates.model_dump(exclude_unset=True)` → upsert 到 `system_settings`

**关键细节：** `exclude_unset=True` 确保仅覆盖前端显式传了的字段，未传字段保留原值。

### 3.4.2 voice.py ASR 配置

**现状：** 硬编码 `provider="xunfei"`、`enabled=False`，所有密钥字段 `None`

**修复：** 从 `get_settings().asr`（`config.py:59-65` 的 `AsrSettings`）读取实际配置：

```python
asr = get_settings().asr
return AsrConfigOut(
    provider=asr.provider,
    app_id=asr.app_id or None,
    api_key=asr.api_key or None,
    api_secret=None,
    websocket_url=asr.api_base or None,
    enabled=asr.provider != "mock" and bool(asr.api_key),
)
```

`enabled` 逻辑：非 mock provider 且 api_key 非空 → 启用。

---

## 架构决策

### Persona Config 持久化策略

选择 `system_settings` 表而非新建表的原因：
1. 架构设计 §7.2 明确此策略
2. `system_settings` 已有完整的 CRUD service + migration，无需新 migration
3. Persona 配置是全局单行配置，天然适合 key-value 模式
4. 存储格式：单 key `persona_config`，值为完整 JSONB blob

### Persona 导入端点位置

在 `admin_personas.py` 新增 `POST /import` 而非让前端调用 `/personas/import`，原因：
1. 前端 `personaApi` 所有方法统一使用 `/admin/personas` 前缀
2. 保持关注点分离：管理端路由统一在 admin_*.py 文件中
3. 实现仅 4 行委托代码，无维护负担

---

## 验证清单

- [x] TypeScript 编译通过 (`vue-tsc --noEmit` — 0 errors)
- [x] Python 语法通过 (`py_compile` — admin_personas / persona_config / voice 全部 OK)
- [x] Python 模块导入通过（admin_personas 7 routes, persona_config 2 routes, voice 3 routes）
- [x] Content/*.vue 死代码已物理删除（目录不存在）
- [x] 所有 `TODO: Phase 2` 已清理（`grep -r "TODO: Phase 2" backend/app/` — 零结果）
- [x] Persona 类型对齐后端 PersonaOut（18 字段）
- [x] PersonaCreate 类型对齐后端 PersonaCreateIn（13 字段）
- [x] 字段名 `model_id` → `live2d_asset_id` 已修正

### 待端到端验证（需启动完整环境）

- [ ] Persona 创建：填写三组全部字段 → 保存 → 编辑验证预填 → 列表刷新
- [ ] JSON 导入：选择 ST V2 JSON 文件 → 角色卡出现在列表
- [ ] Persona 配置持久化：修改模型/动作/语速 → 刷新页面后配置不丢失
- [ ] ASR 配置端点：`curl /voice/asr/config` 返回 Settings 实际值
- [ ] Knowledge Preview 回归：上传文档 → 向量化 → Preview RAG → chunks 正常展示

---

## 已知遗留（不在此次修复范围内）

以下问题在 Phase 4 P0 Fixes Handoff 中已标注为"已知遗留"，本次未处理：

1. **Asset 上传路径不匹配** — 前端 `POST /admin/assets/live2d` vs 后端 `POST /assets/live2d`
2. **Asset is_default 后端不支持** — assets 表无 `is_default` 列
3. **Dashboard 运营看板占位** — 7 个端点返回空数据（Phase 5 填充）

---

**签出**: 本修复由 Claude Opus 4.8 执行，基于 `docs/superpowers/plans/3-1-dashboard-melodic-rossum.md`。
**下一步**: 启动完整环境进行端到端验证，或继续 Phase 5（运营看板 + 数据管线）。
