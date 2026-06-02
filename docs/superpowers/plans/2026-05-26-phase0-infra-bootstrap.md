---
name: 2026-05-26-phase0-infra-bootstrap
title: Phase 0 · 基础设施与脚手架
date: 2026-05-26
status: completed
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
overview: docs/superpowers/plans/2026-05-26-overview.md
revision: 2026-06-02 — 标记全部完成，记录实际偏差
---

# Phase 0 · 基础设施与脚手架 ✅ 已完成

> **状态：全部完成。** 本 Phase 的所有基础设施已就位，开发者本地 `docker compose up` 可启动一个能登录的最小系统。验证门 G-0.1 / G-0.2 / G-0.3 全部通过。

---

## 任务完成清单

### T0.1: 仓库与 monorepo 骨架 ✅
- `pnpm-workspace.yaml`、`package.json`、`.gitignore`、`.editorconfig`、`README.md` 已创建
- 目录结构 `apps/web-user/` `apps/web-admin/` `packages/ui-shared/` `backend/` `deploy/` `scripts/` 已就位

### T0.2: 后端最小 FastAPI Hello ✅
- `backend/pyproject.toml`（uv 管理依赖）
- `backend/app/main.py`（FastAPI app factory）
- `backend/app/api/rest/system.py`（`/` 根端点）
- 测试：`backend/tests/unit/test_system.py`

### T0.3: PG + Alembic + pgvector ✅
- `backend/app/infra/db.py`（async engine + session factory）
- `backend/app/infra/alembic/`（Alembic 配置）
- `backend/alembic.ini`
- 迁移 `0001_init_pgvector.py`（pgvector 扩展 + schema_version 表）
- `deploy/docker-compose.dev.yml`（PG + Redis + MinIO）
- 集成测试：`backend/tests/integration/test_db.py`

### T0.4: Redis 接入 ✅
- `backend/app/infra/redis.py`（async Redis client）
- 集成测试：`backend/tests/integration/test_redis.py`

### T0.5: OSS（MinIO）接入 ✅
- `backend/app/infra/oss.py`（boto3 S3 client + presigned URL）
- `scripts/init_oss_buckets.py`（桶初始化）
- 集成测试：`backend/tests/integration/test_oss.py`

### T0.6: 配置层（pydantic-settings）✅
- `backend/app/core/config.py`（Settings 含 App/DB/Redis/OSS/JWT 子配置）
- `deploy/.env.example`（环境变量模板）
- 单元测试：`backend/tests/unit/test_config.py`

### T0.7: 日志层（structlog JSON）✅
- `backend/app/core/logging.py`（JSON 格式结构化日志）
- 单元测试：`backend/tests/unit/test_logging.py`

### T0.8: Healthz / Readyz / Metrics ✅
- `/healthz`、`/readyz`、`/metrics` 端点
- Prometheus metrics 导出
- 集成测试：`backend/tests/integration/test_health.py`

### T0.9: 鉴权骨架 ✅
- `backend/app/domain/identity/models.py`（User 模型）
- `backend/app/domain/identity/schemas.py`（RegisterIn / LoginIn / TokenPair / UserOut）
- `backend/app/domain/identity/repository.py`（UserRepository）
- `backend/app/domain/identity/service.py`（IdentityService：register / login / refresh）
- `backend/app/core/security.py`（bcrypt 密码哈希 + JWT 签发/解码）
- `backend/app/core/deps.py`（get_current_user / require_admin 依赖注入）
- `backend/app/api/rest/auth.py`（/auth/register /login /refresh /me）
- 迁移 `0002_users_and_roles.py`
- 集成测试：`backend/tests/integration/test_auth.py`

### T0.10: 前端 monorepo + ui-shared ✅（有偏差）

> ⚠️ **实际偏差**：ui-shared 最终简化为 stub，不提供 GlassCard / GlassButton 等共享组件。各应用页面的玻璃拟态效果通过内联样式自行实现。详见 handoff 文件。

- `apps/web-user/` 骨架（Vue 3 + Vite + TS + Pinia + Vue Router）
- `apps/web-admin/` 骨架（同构）
- `packages/ui-shared/` 简化为最小 stub
- Auth store（localStorage + Axios 拦截器）
- HTTP 服务（Bearer token 注入）
- 路由结构（user: 3 条，admin: 5 条）
- 前端测试配置（Vitest + @vue/test-utils + happy-dom）

### T0.11: Docker Compose 全栈 + Nginx ✅
- `backend/Dockerfile`（多段构建）
- `apps/web-user/Dockerfile`、`apps/web-admin/Dockerfile`
- `deploy/docker-compose.yml`（生产用）
- `deploy/docker-compose.dev.yml`（开发用）
- `deploy/nginx/`（反向代理配置）

### T0.12: CI 工作流 ✅
- `.github/workflows/ci.yml`（backend: lint + test + build；frontend: lint + test + build）
- 已验证：两个 job 全绿

### T0.13: pre-commit hooks ✅
- `.pre-commit-config.yaml`（ruff + prettier + gitleaks + trailing-whitespace 等）
- 已验证：`pre-commit run --all-files` 通过

---

## 实际偏差记录

以下为与原始 Phase 0 计划的关键偏差，已确认且不再回退：

1. **ui-shared 简化**（T0.10）：原计划构建 4 个玻璃拟态组件 + CSS tokens + composables，实际简化为 stub。Login 等页面自行处理样式。**不回退。**
2. **前端远超骨架**（T0.10）：原计划仅做登录页骨架 + Chat 占位，实际所有页面 UI 已全部完成。这是计划外的提前推进，后续 Phase 的前端 UI 任务应视为已完成。

---

## 验证门（全部通过）

### 🚦 G-0.1 · 本地全栈一键启动 ✅
- docker compose up 后所有服务 healthy
- /healthz 与 /readyz 全 200
- 前端 / 与 /admin/ 静态页可访问

### 🚦 G-0.2 · 鉴权回路与安全基线 ✅
- register → login → /auth/me → refresh 完整链路通过
- bcrypt 成本 ≥ 12
- 错误登录不泄露用户存在性
- refresh_token 重放被拒

### 🚦 G-0.3 · CI 全绿基线 ✅
- ci.yml 三个 job 全绿
- 测试覆盖率 ≥ 70%
- lint/format 零警告

---

## 进入下一 Phase

Phase 0 全部完成 → **可启动 Phase 1（文本对话闭环）**。

## Revision 2026-06-02

- 标记全部任务完成。
- 记录 T0.10 实际偏差（ui-shared stub 化）。
- 移除原始计划中的详细实现步骤（已不需要）。
