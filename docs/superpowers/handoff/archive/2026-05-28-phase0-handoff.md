---
title: Phase 0 Handoff · 基础设施与脚手架
date: 2026-05-28
status: completed
next_phase: 2026-05-26-phase1-text-chat.md
---

# Phase 0 完成交接

## 总体状态

Phase 0 所有 13 项任务（T0.1–T0.13）已完成。后端基础设施通过全部测试（12/12），linting / 类型检查零警告。

| 验证门禁 | 状态 |
|----------|------|
| G-0.1 全部测试通过 | 12/12 后端 + ruff + mypy 零错误 |
| G-0.2 Docker 服务启动 | PostgreSQL 16 / Redis 7 / MinIO 健康 |
| G-0.3 Linting / 类型检查 | ruff clean, mypy 24 files 零 issue |

## 后端基础设施清单

### 目录结构

```
backend/
  app/
    core/          # config(pydantic-settings), security(JWT+bcrypt), deps(FastAPI DI), logging(structlog)
    infra/         # db(asyncpg), redis(async), oss(boto3/MinIO), alembic/
    domain/identity/  # User model, repository, service, schemas
    api/rest/      # system(healthz/readyz/metrics), auth(register/login/refresh/me)
  tests/
    unit/           # config, logging, system (3 tests)
    integration/    # auth, db, health, oss, redis (9 tests)
  alembic.ini
  pyproject.toml
  Dockerfile
```

### 数据库

- PostgreSQL 16 + pgvector 扩展 + pgcrypto
- 迁移：`backend/app/infra/alembic/versions/`
  - `0001_init_pgvector.py` — CREATE EXTENSION vector/pgcrypto + schema_version 表
  - `0002_users_and_roles.py` — users 表（id/email/password_hash/display_name/role/status）
- 连接 DSN 通过 `EIRA_DB__DSN` 或 `EIRA_DB_DSN` 环境变量配置

### Auth 链路

- `POST /auth/register` — 注册（bcrypt cost=12，默认 role=visitor）
- `POST /auth/login` — 登录（失败不泄露用户存在性）
- `POST /auth/refresh` — 刷新 token（旧 refresh token 在 Redis 中拉黑）
- `GET /auth/me` — 当前用户信息（需 Bearer token）
- JWT 双 token：access（15min）+ refresh（7d），jti 唯一标识符
- `/healthz` / `/readyz` / `/metrics` 端点正常

## 实施中修复的关键问题

以下问题在 Phase 0 实施中遇到并已修复，供后续参考：

### 1. FastAPI DI 中的 AsyncSession 提交问题

**文件：** `backend/app/core/deps.py`

`async_sessionmaker` 的 `async with` 上下文管理器在 FastAPI generator dependency 中不会正确触发 `__aexit__`，导致 `UserRepository.create()` 调用 `flush()` 后数据未真正提交到数据库。

**修复：** 使用显式 try/commit/rollback/close 模式替代 `async with`：

```python
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    s = factory()
    try:
        yield s
        await s.commit()
    except Exception:
        await s.rollback()
        raise
    finally:
        await s.close()
```

### 2. JWT 唯一性问题

**文件：** `backend/app/core/security.py`

原始实现中 `iat` 精度仅到秒，同一秒内生成的两个 token 完全相同。添加 `jti: uuid.uuid4().hex` 确保每个 token 唯一。

### 3. 密码哈希库选型

passlib 1.7.x 与 bcrypt 5.0.0 不兼容（`AttributeError: module 'bcrypt' has no attribute '__about__'`）。

**修复：** 放弃 passlib，直接使用 bcrypt 4.x：

```python
import bcrypt

def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

def verify_password(p: str, h: str) -> bool:
    return bcrypt.checkpw(p.encode("utf-8"), h.encode("utf-8"))
```

### 4. Python 3.14 + Windows 兼容性

Python 3.14 的默认 `ProactorEventLoop` 与 asyncpg 不兼容。

**修复：** `tests/conftest.py` 中设置 `WindowsSelectorEventLoopPolicy`，且 event loop scope 设为 `session`：

```python
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_default_test_loop_scope = "session"
```

## 运行指南

### 启动依赖服务

```bash
docker compose -f deploy/docker-compose.dev.yml up -d
```

### 初始化

```bash
cd backend
uv sync --extra dev
uv run alembic upgrade head
python ../scripts/init_oss_buckets.py
```

### 运行后端测试

```bash
cd backend
uv run pytest tests/ -v
uv run ruff check app/ tests/
uv run mypy app/
```

## 前端代码说明

前端代码（`apps/web-admin/`、`apps/web-user/`、`packages/ui-shared/`）已在本次 handoff 前全部删除。原因：已有前端代码存在架构问题，将由开发者重新编写。

删除内容包括：
- `apps/web-admin/` — 管理后台（Dashboard、Login、Content 页面、naive-ui 集成）
- `apps/web-user/` — 用户端（Chat、Login、Live2D 组件、Camera 组件）
- `packages/ui-shared/` — Glassmorphism UI 组件库（GlassButton、GlassCard、GlassInput、GlassModal）

重新编写前端时参考：
- Phase 0 计划 T0.10 中的前端骨架搭建步骤
- `docs/superpowers/specs/2026-05-26-architecture-design.md` 中的设计规范
- Phase 1 计划中的文本聊天 UI 需求

`pnpm-workspace.yaml` 和根 `package.json` 保留，`node_modules/` 和 `pnpm-lock.yaml` 已清理。

## 环境依赖

| 工具 | 版本 | 备注 |
|------|------|------|
| Python | 3.14.5 | 当前环境；建议后续生产用 3.11 |
| uv | 通过 python -m pip install uv | 可能不在 PATH 中，使用 `python -m uv` |
| Node.js | 20 LTS | 前端重写时使用 |
| pnpm | 9.0.0 | 前端重写时使用 |
| Docker Desktop | 24+ | PostgreSQL/Redis/MinIO 运行环境 |

## 后续 Phase 1 进入条件

Phase 1（文本聊天）启动前需满足：
1. Docker 服务正常运行
2. 后端 12 个测试全部通过
3. Alembic migration 已应用到最新
4. OSS buckets 已初始化

当前以上条件均已满足。

## 未完成项 / 已知限制

- 注册接口无邮箱验证（计划在 Phase 4 补）
- 无线程安全的生产密钥管理（当前 JWT secret 硬编码 dev-only）
- CI workflows 需要 GitHub Actions 环境验证
- pre-commit hooks 需要本地 `pip install pre-commit && pre-commit install`
- Frontend 待重写
