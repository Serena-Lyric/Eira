---
name: 2026-05-26-phase0-infra-bootstrap
title: Phase 0 · 基础设施与脚手架
date: 2026-05-26
status: draft
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
overview: docs/superpowers/plans/2026-05-26-overview.md
---

# Phase 0 实施计划 · 基础设施与脚手架

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建后续所有 Phase 共用的工程骨架——monorepo 结构、Docker 化本地环境、CI、PG/pgvector/Redis/OSS 接入、鉴权骨架、共享 UI 包初版。本 Phase 完成后，开发者本地 `docker compose up` 可启动一个能登录的最小系统。

**Architecture:** Python 3.11/FastAPI + Vue 3/Vite + PostgreSQL 16 + pgvector 0.7+ + Redis 7 + MinIO（OSS 本地替身）+ Nginx（仅生产路径）。

**Tech Stack:** uv（Python 包管理）、pnpm workspace、Alembic、SQLAlchemy 2.x（async）、pydantic-settings、structlog、passlib、python-jose、Vitest、Pytest、Playwright、ruff、mypy、pre-commit、GitHub Actions。

**前置条件：**
- 安装 Docker Desktop / Docker Engine 24+
- 安装 Node.js 20 LTS + pnpm 9+
- 安装 Python 3.11+ + uv
- Git 配置完毕，能访问代码托管

**本 Phase 不做：** Live2D、LLM 接入、知识库、WS 业务消息（仅留 ping/pong）。

**重述全局约定（详见 overview.md）：**
- TDD 强制，每 Step 5 提交。
- commit 前缀：`feat/fix/test/refactor/chore/docs/infra`。
- 密钥不入库不入日志。
- 所有 Validation Gate 数据归档至 `docs/superpowers/validations/<gate-id>.md` 且必须 commit。

---

## 任务依赖图

```
T0.1 仓库与 monorepo 骨架
  ↓
T0.2 Python 后端骨架（FastAPI Hello）
  ↓
T0.3 PG + Alembic + 第一张表（schema_version）
  ↓
T0.4 Redis 接入与健康检查
  ↓
T0.5 OSS（MinIO）接入与签名 URL
  ↓
T0.6 配置层（pydantic-settings）  ─┐
  ↓                                │
T0.7 日志层（structlog）           │ 横切层并行可
  ↓                                │
T0.8 Healthz / metrics / readyz   ─┘
  ↓
T0.9 鉴权骨架（用户表 + JWT 双 token + 路由）
  ↓
T0.10 前端 monorepo + ui-shared 初版  ──┐
                                         │ 与 T0.11 并行可
T0.11 Docker Compose 全栈 + Nginx    ──┘
  ↓
T0.12 CI（lint + test + build）
  ↓
T0.13 pre-commit hooks
  ↓
🚦 G-0.1 / G-0.2 / G-0.3 验证门
```

---

## Task 0.1: 仓库与 monorepo 骨架

**Files:**
- Create: `pnpm-workspace.yaml`
- Create: `package.json`（顶层）
- Create: `.gitignore`
- Create: `.editorconfig`
- Create: `README.md`
- Create: `LICENSE`（可选 MIT/Apache-2.0）
- Create: `docs/superpowers/validations/.gitkeep`
- Create: 空目录 `apps/web-user/` `apps/web-admin/` `packages/ui-shared/` `backend/` `deploy/` `scripts/`

- [ ] **Step 1: 写测试 — 校验目录结构存在**

`scripts/check_structure.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
required=(
  apps/web-user
  apps/web-admin
  packages/ui-shared
  backend
  deploy
  scripts
  docs/superpowers/specs
  docs/superpowers/plans
  docs/superpowers/validations
)
for d in "${required[@]}"; do
  if [[ ! -d "$d" ]]; then
    echo "missing: $d"
    exit 1
  fi
done
echo "structure ok"
```

- [ ] **Step 2: 运行验证（应失败）**

```
bash scripts/check_structure.sh
```

预期：FAIL，列出缺失目录。

- [ ] **Step 3: 创建目录与基础文件**

```
mkdir -p apps/web-user apps/web-admin packages/ui-shared \
         backend deploy scripts \
         docs/superpowers/{specs,plans,validations}
touch apps/web-user/.gitkeep apps/web-admin/.gitkeep \
      packages/ui-shared/.gitkeep backend/.gitkeep \
      deploy/.gitkeep scripts/.gitkeep \
      docs/superpowers/validations/.gitkeep
```

`pnpm-workspace.yaml`:

```yaml
packages:
  - "apps/*"
  - "packages/*"
```

`package.json`（顶层，最小）:

```json
{
  "name": "eira",
  "private": true,
  "version": "0.0.0",
  "packageManager": "pnpm@9.0.0",
  "scripts": {
    "lint": "pnpm -r run lint",
    "test": "pnpm -r run test",
    "build": "pnpm -r run build"
  }
}
```

`.gitignore`（节选）:

```
# python
__pycache__/
*.pyc
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# node
node_modules/
dist/
.vite/

# env & secrets
.env
.env.*
!.env.example

# os
.DS_Store
Thumbs.db

# logs
*.log
```

`.editorconfig`:

```ini
root = true
[*]
indent_style = space
indent_size = 2
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true
[*.py]
indent_size = 4
```

- [ ] **Step 4: 再次运行验证应通过**

```
bash scripts/check_structure.sh
```

预期：`structure ok`。

- [ ] **Step 5: 提交**

```
git add .
git commit -m "infra: bootstrap monorepo skeleton with pnpm workspace"
```

---

## Task 0.2: 后端最小 FastAPI Hello

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/rest/__init__.py`
- Create: `backend/app/api/rest/system.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/unit/__init__.py`
- Create: `backend/tests/unit/test_system.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_system.py`:

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root_returns_service_info():
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "eira-backend"
    assert "version" in body
```

- [ ] **Step 2: 验证失败**

```
cd backend && uv run pytest tests/unit/test_system.py -v
```

预期：FAIL（`app.main` 不存在）。

- [ ] **Step 3: 写最小实现**

`backend/pyproject.toml`:

```toml
[project]
name = "eira-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.111",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.7",
  "pydantic-settings>=2.3",
  "structlog>=24.1",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
  "httpx>=0.27",
  "ruff>=0.5",
  "mypy>=1.10",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
pythonpath = ["."]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = false  # phase 0 only; will tighten in phase 1
```

`backend/app/main.py`:

```python
from fastapi import FastAPI
from app.api.rest import system

def create_app() -> FastAPI:
    app = FastAPI(title="Eira Backend", version="0.1.0")
    app.include_router(system.router)
    return app

app = create_app()
```

`backend/app/api/rest/system.py`:

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def root() -> dict:
    return {"service": "eira-backend", "version": "0.1.0"}
```

- [ ] **Step 4: 验证通过**

```
cd backend && uv sync --extra dev && uv run pytest tests/unit -v
```

预期：1 passed。

- [ ] **Step 5: 提交**

```
git add backend/
git commit -m "feat(backend): bootstrap fastapi skeleton with root endpoint"
```

---

## Task 0.3: PG + Alembic + schema_version 表

**Files:**
- Create: `backend/app/infra/__init__.py`
- Create: `backend/app/infra/db.py`
- Create: `backend/app/infra/alembic/env.py`
- Create: `backend/app/infra/alembic/script.py.mako`
- Create: `backend/alembic.ini`
- Create: `backend/app/infra/alembic/versions/0001_init_pgvector.py`
- Modify: `backend/pyproject.toml`（加 sqlalchemy / asyncpg / alembic / pgvector）
- Create: `backend/tests/integration/__init__.py`
- Create: `backend/tests/integration/test_db.py`
- Create: `deploy/docker-compose.dev.yml`（仅起 PG）

> ⚠️ **注意**：本任务首次引入数据库，集成测试需 PG 实例。先建 `docker-compose.dev.yml`，再开始 TDD。pgvector 扩展 `CREATE EXTENSION` 必须超级用户执行。

- [ ] **Step 1: 准备本地 PG（先于测试）**

`deploy/docker-compose.dev.yml`:

```yaml
services:
  pg:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: eira
      POSTGRES_USER: eira
      POSTGRES_PASSWORD: eira
    ports: ["5432:5432"]
    volumes: [eira-pg-data:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "eira"]
      interval: 5s
      retries: 10

volumes:
  eira-pg-data:
```

启动：

```
docker compose -f deploy/docker-compose.dev.yml up -d pg
```

验证：

```
docker compose -f deploy/docker-compose.dev.yml exec pg psql -U eira -d eira -c "SELECT 1;"
```

- [ ] **Step 2: 写失败测试**

`backend/tests/integration/test_db.py`:

```python
import pytest
from sqlalchemy import text
from app.infra.db import get_engine

@pytest.mark.asyncio
async def test_pgvector_extension_available():
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname='vector'")
        )
        assert result.scalar() == "vector"

@pytest.mark.asyncio
async def test_schema_version_table_exists():
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT to_regclass('public.schema_version')")
        )
        assert result.scalar() == "schema_version"
```

- [ ] **Step 3: 验证失败**

```
cd backend && uv run pytest tests/integration/test_db.py -v
```

预期：FAIL（模块缺失）。

- [ ] **Step 4: 加依赖**

修改 `backend/pyproject.toml`，`dependencies` 追加：

```
"sqlalchemy[asyncio]>=2.0",
"asyncpg>=0.29",
"alembic>=1.13",
"pgvector>=0.3",
```

执行 `uv sync --extra dev`。

- [ ] **Step 5: 写实现**

`backend/app/infra/db.py`:

```python
from functools import lru_cache
import os
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

def _build_dsn() -> str:
    return os.environ.get(
        "EIRA_DB_DSN",
        "postgresql+asyncpg://eira:eira@localhost:5432/eira",
    )

@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(_build_dsn(), pool_pre_ping=True)

@lru_cache
def get_session_factory() -> async_sessionmaker:
    return async_sessionmaker(get_engine(), expire_on_commit=False)
```

`backend/alembic.ini`（核心字段，省略默认日志段）:

```ini
[alembic]
script_location = app/infra/alembic
prepend_sys_path = .
sqlalchemy.url =
```

`backend/app/infra/alembic/env.py`:

```python
import asyncio
from logging.config import fileConfig
from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool, engine_from_config
from app.infra.db import _build_dsn

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", _build_dsn().replace("+asyncpg", ""))

target_metadata = None  # phase 0 仅手写 SQL；phase 1 改成模型 metadata

def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"),
                      target_metadata=target_metadata,
                      literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section),
                                     prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

`backend/app/infra/alembic/script.py.mako`（用 alembic 默认模板即可，可 `alembic init` 后保留）。

`backend/app/infra/alembic/versions/0001_init_pgvector.py`:

```python
"""init pgvector and schema_version

Revision ID: 0001
Revises:
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "schema_version",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("applied_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
    )
    op.execute("INSERT INTO schema_version(note) VALUES ('phase 0 init')")

def downgrade() -> None:
    op.drop_table("schema_version")
```

- [ ] **Step 6: 跑迁移**

```
cd backend && EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
  uv run alembic upgrade head
```

预期：`Running upgrade -> 0001`。

- [ ] **Step 7: 验证测试通过**

```
uv run pytest tests/integration/test_db.py -v
```

预期：2 passed。

- [ ] **Step 8: 提交**

```
git add backend/ deploy/
git commit -m "infra(db): integrate postgres + pgvector + alembic baseline"
```

---

## Task 0.4: Redis 接入

**Files:**
- Create: `backend/app/infra/redis.py`
- Modify: `backend/pyproject.toml`（加 `redis>=5.0`）
- Modify: `deploy/docker-compose.dev.yml`（追加 redis 服务）
- Create: `backend/tests/integration/test_redis.py`

- [ ] **Step 1: docker-compose 追加 Redis**

```yaml
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 10
```

```
docker compose -f deploy/docker-compose.dev.yml up -d redis
```

- [ ] **Step 2: 写失败测试**

`backend/tests/integration/test_redis.py`:

```python
import pytest
from app.infra.redis import get_redis

@pytest.mark.asyncio
async def test_redis_set_and_get():
    r = get_redis()
    await r.set("test:key", "hello", ex=10)
    assert await r.get("test:key") == "hello"
    await r.delete("test:key")
```

- [ ] **Step 3: 验证失败**

```
uv run pytest tests/integration/test_redis.py -v
```

预期：FAIL。

- [ ] **Step 4: 实现**

`backend/app/infra/redis.py`:

```python
from functools import lru_cache
import os
from redis.asyncio import Redis

@lru_cache
def get_redis() -> Redis:
    url = os.environ.get("EIRA_REDIS_URL", "redis://localhost:6379/0")
    return Redis.from_url(url, decode_responses=True)
```

修改 `pyproject.toml` 加 `redis>=5.0` 并 `uv sync --extra dev`。

- [ ] **Step 5: 验证通过**

```
uv run pytest tests/integration/test_redis.py -v
```

预期：1 passed。

- [ ] **Step 6: 提交**

```
git add backend/ deploy/
git commit -m "infra(redis): integrate redis async client"
```

---

## Task 0.5: OSS（MinIO）接入与签名 URL

**Files:**
- Create: `backend/app/infra/oss.py`
- Modify: `backend/pyproject.toml`（加 `boto3>=1.34`）
- Modify: `deploy/docker-compose.dev.yml`（追加 minio）
- Create: `scripts/init_oss_buckets.py`
- Create: `backend/tests/integration/test_oss.py`

> ⚠️ **注意**：MinIO S3 兼容层使用 boto3。生产环境切换为阿里云 OSS / 腾讯云 COS 时仅替换 endpoint + signature 版本，不改业务代码。

- [ ] **Step 1: 追加 MinIO**

```yaml
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: eira
      MINIO_ROOT_PASSWORD: eira-secret
    ports: ["9000:9000", "9001:9001"]
    volumes: [eira-minio-data:/data]
```

`volumes:` 段补 `eira-minio-data:`。

启动：

```
docker compose -f deploy/docker-compose.dev.yml up -d minio
```

- [ ] **Step 2: 桶初始化脚本**

`scripts/init_oss_buckets.py`:

```python
import os
import boto3

ENDPOINT = os.environ.get("EIRA_OSS_ENDPOINT", "http://localhost:9000")
KEY = os.environ.get("EIRA_OSS_KEY", "eira")
SECRET = os.environ.get("EIRA_OSS_SECRET", "eira-secret")

BUCKETS = ["eira-documents", "eira-live2d", "eira-backgrounds",
           "eira-audio", "eira-avatars"]

def main():
    s3 = boto3.client("s3", endpoint_url=ENDPOINT,
                      aws_access_key_id=KEY, aws_secret_access_key=SECRET,
                      region_name="us-east-1")
    for b in BUCKETS:
        try:
            s3.create_bucket(Bucket=b)
            print(f"created {b}")
        except s3.exceptions.BucketAlreadyOwnedByYou:
            print(f"exists  {b}")

if __name__ == "__main__":
    main()
```

跑：

```
python scripts/init_oss_buckets.py
```

- [ ] **Step 3: 写失败测试**

`backend/tests/integration/test_oss.py`:

```python
import pytest
from app.infra.oss import get_oss_client, presign_get

@pytest.mark.asyncio
async def test_put_and_presign():
    s3 = get_oss_client()
    s3.put_object(Bucket="eira-documents", Key="health/probe.txt",
                  Body=b"hello")
    url = presign_get("eira-documents", "health/probe.txt", expires=60)
    assert url.startswith("http")
    assert "X-Amz-Signature" in url or "Signature=" in url
```

- [ ] **Step 4: 验证失败**

```
uv run pytest tests/integration/test_oss.py -v
```

预期：FAIL。

- [ ] **Step 5: 实现**

`backend/app/infra/oss.py`:

```python
from functools import lru_cache
import os
import boto3
from botocore.client import Config

def _opts() -> dict:
    return {
        "endpoint_url": os.environ.get("EIRA_OSS_ENDPOINT", "http://localhost:9000"),
        "aws_access_key_id": os.environ.get("EIRA_OSS_KEY", "eira"),
        "aws_secret_access_key": os.environ.get("EIRA_OSS_SECRET", "eira-secret"),
        "region_name": os.environ.get("EIRA_OSS_REGION", "us-east-1"),
        "config": Config(signature_version="s3v4"),
    }

@lru_cache
def get_oss_client():
    return boto3.client("s3", **_opts())

def presign_get(bucket: str, key: str, expires: int = 600) -> str:
    return get_oss_client().generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )

def presign_put(bucket: str, key: str, expires: int = 600) -> str:
    return get_oss_client().generate_presigned_url(
        "put_object", Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )
```

修改 `pyproject.toml` 加 `boto3>=1.34`，`uv sync --extra dev`。

- [ ] **Step 6: 验证通过**

```
uv run pytest tests/integration/test_oss.py -v
```

预期：1 passed。

- [ ] **Step 7: 提交**

```
git add backend/ deploy/ scripts/
git commit -m "infra(oss): integrate s3-compatible storage with presigned urls"
```

---

## Task 0.6: 配置层（pydantic-settings）

**Files:**
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `deploy/.env.example`
- Modify: `backend/app/infra/db.py` `redis.py` `oss.py`（改读 settings）
- Create: `backend/tests/unit/test_config.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_config.py`:

```python
import os
from app.core.config import get_settings

def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("EIRA_DB_DSN", "postgresql+asyncpg://x:y@h/d")
    monkeypatch.setenv("EIRA_REDIS_URL", "redis://h:6379/1")
    get_settings.cache_clear()
    s = get_settings()
    assert s.db.dsn == "postgresql+asyncpg://x:y@h/d"
    assert s.redis.url == "redis://h:6379/1"
    assert s.app.env in ("dev", "staging", "prod")
```

- [ ] **Step 2: 验证失败**

预期：FAIL。

- [ ] **Step 3: 实现**

`backend/app/core/config.py`:

```python
from functools import lru_cache
from typing import Literal
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseModel):
    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174"]

class DBSettings(BaseModel):
    dsn: str = "postgresql+asyncpg://eira:eira@localhost:5432/eira"

class RedisSettings(BaseModel):
    url: str = "redis://localhost:6379/0"

class OssSettings(BaseModel):
    endpoint: str = "http://localhost:9000"
    key: str = "eira"
    secret: str = "eira-secret"
    region: str = "us-east-1"

class JwtSettings(BaseModel):
    secret: str = "dev-only-change-me"
    access_ttl_seconds: int = 900
    refresh_ttl_seconds: int = 7 * 24 * 3600
    algorithm: str = "HS256"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EIRA_", env_nested_delimiter="__",
        env_file=".env", extra="ignore",
    )
    app: AppSettings = AppSettings()
    db: DBSettings = DBSettings()
    redis: RedisSettings = RedisSettings()
    oss: OssSettings = OssSettings()
    jwt: JwtSettings = JwtSettings()

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

环境变量映射示例：`EIRA_DB__DSN=...`、`EIRA_JWT__SECRET=...`。**注意**：`pydantic-settings` 嵌套字段使用 `__` 分隔（已在 `env_nested_delimiter` 定义）。但为了兼容已有 `EIRA_DB_DSN` 直接形式，下面同时支持顶层别名。

`backend/app/core/config.py` 末尾追加（仅在测试已存在习惯上）：

```python
# 兼容直接形式：EIRA_DB_DSN / EIRA_REDIS_URL
import os
def _legacy_overrides(s: Settings) -> Settings:
    if v := os.environ.get("EIRA_DB_DSN"):
        s.db.dsn = v
    if v := os.environ.get("EIRA_REDIS_URL"):
        s.redis.url = v
    if v := os.environ.get("EIRA_OSS_ENDPOINT"):
        s.oss.endpoint = v
    return s

# 重新装饰 get_settings 以应用兼容
_orig = get_settings
@lru_cache
def get_settings() -> Settings:  # type: ignore[no-redef]
    return _legacy_overrides(_orig.__wrapped__())
```

> 简化建议：执行人可选择直接抛弃旧形式，统一用 `EIRA_DB__DSN`，并把测试改写。

`deploy/.env.example`:

```
EIRA_APP__ENV=dev
EIRA_APP__LOG_LEVEL=DEBUG

EIRA_DB__DSN=postgresql+asyncpg://eira:eira@pg:5432/eira
EIRA_REDIS__URL=redis://redis:6379/0

EIRA_OSS__ENDPOINT=http://minio:9000
EIRA_OSS__KEY=eira
EIRA_OSS__SECRET=eira-secret

EIRA_JWT__SECRET=please-replace-in-prod
EIRA_JWT__ACCESS_TTL_SECONDS=900
EIRA_JWT__REFRESH_TTL_SECONDS=604800
```

- [ ] **Step 4: 修改 infra 模块改读 settings**

修改 `app/infra/db.py`：

```python
from app.core.config import get_settings

def _build_dsn() -> str:
    return get_settings().db.dsn
```

`redis.py`、`oss.py` 同理改成 `get_settings().redis.url` / `get_settings().oss.*`。

- [ ] **Step 5: 验证通过**

```
uv run pytest tests/unit/test_config.py tests/integration -v
```

预期：全 pass。

- [ ] **Step 6: 提交**

```
git add backend/ deploy/.env.example
git commit -m "feat(core): centralize config with pydantic-settings"
```

---

## Task 0.7: 日志层（structlog JSON）

**Files:**
- Create: `backend/app/core/logging.py`
- Modify: `backend/app/main.py`（启动时调用 `configure_logging()`）
- Create: `backend/tests/unit/test_logging.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_logging.py`:

```python
import json
import logging
import structlog
from app.core.logging import configure_logging

def test_log_emits_json(capsys):
    configure_logging()
    log = structlog.get_logger()
    log.info("hello", request_id="r1", user_id="u1", latency_ms=42)
    captured = capsys.readouterr().out.strip()
    payload = json.loads(captured)
    assert payload["event"] == "hello"
    assert payload["request_id"] == "r1"
    assert payload["user_id"] == "u1"
    assert payload["latency_ms"] == 42
    assert "ts" in payload and "level" in payload
```

- [ ] **Step 2: 验证失败**

```
uv run pytest tests/unit/test_logging.py -v
```

预期：FAIL。

- [ ] **Step 3: 实现**

`backend/app/core/logging.py`:

```python
import logging
import sys
import structlog
from app.core.config import get_settings

def configure_logging() -> None:
    level = getattr(logging, get_settings().app.log_level.upper(), logging.INFO)
    logging.basicConfig(stream=sys.stdout, level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", key="ts"),
            structlog.processors.add_log_level,
            structlog.processors.EventRenamer("event"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

修改 `app/main.py`：

```python
from app.core.logging import configure_logging

def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Eira Backend", version="0.1.0")
    app.include_router(system.router)
    return app
```

> ⚠️ **注意**：禁止在日志中输出敏感字段（password、token、API key、refresh_token）。后续 Phase 1 将增加 `redactors` 处理器自动脱敏。

- [ ] **Step 4: 验证通过**

```
uv run pytest tests/unit/test_logging.py -v
```

预期：1 passed。

- [ ] **Step 5: 提交**

```
git add backend/
git commit -m "feat(core): structured json logging with structlog"
```

---

## Task 0.8: Healthz / Readyz / Metrics

**Files:**
- Modify: `backend/app/api/rest/system.py`（追加 healthz / readyz / metrics）
- Modify: `backend/pyproject.toml`（加 `prometheus-client>=0.20`）
- Create: `backend/tests/integration/test_health.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/integration/test_health.py`:

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_healthz_alive():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

def test_readyz_checks_dependencies():
    resp = client.get("/readyz")
    # 允许 503（无依赖时），但 200 时必须含 db/redis/oss 字段
    assert resp.status_code in (200, 503)
    body = resp.json()
    for k in ("db", "redis", "oss"):
        assert k in body

def test_metrics_endpoint_exists():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "process_cpu_seconds_total" in resp.text
```

- [ ] **Step 2: 验证失败**

```
uv run pytest tests/integration/test_health.py -v
```

预期：FAIL。

- [ ] **Step 3: 实现**

修改 `backend/app/api/rest/system.py`:

```python
from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from app.infra.db import get_engine
from app.infra.redis import get_redis
from app.infra.oss import get_oss_client

router = APIRouter()

@router.get("/")
async def root() -> dict:
    return {"service": "eira-backend", "version": "0.1.0"}

@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}

@router.get("/readyz")
async def readyz(response: Response) -> dict:
    out = {"db": "down", "redis": "down", "oss": "down"}
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        out["db"] = "up"
    except Exception:
        pass
    try:
        if await get_redis().ping():
            out["redis"] = "up"
    except Exception:
        pass
    try:
        get_oss_client().list_buckets()
        out["oss"] = "up"
    except Exception:
        pass
    if "down" in out.values():
        response.status_code = 503
    return out

@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

加 `prometheus-client>=0.20` 到 `pyproject.toml` 后 `uv sync --extra dev`。

- [ ] **Step 4: 验证通过**

```
uv run pytest tests/integration/test_health.py -v
```

预期：3 passed（依赖已起则全 up；未起则 readyz 503 但字段齐全）。

- [ ] **Step 5: 提交**

```
git add backend/
git commit -m "feat(observability): add healthz/readyz/metrics endpoints"
```

---

## Task 0.9: 鉴权骨架（用户表 + JWT 双 token + 路由）

**Files:**
- Create: `backend/app/domain/__init__.py`
- Create: `backend/app/domain/identity/__init__.py`
- Create: `backend/app/domain/identity/models.py`
- Create: `backend/app/domain/identity/schemas.py`
- Create: `backend/app/domain/identity/repository.py`
- Create: `backend/app/domain/identity/service.py`
- Create: `backend/app/core/security.py`
- Create: `backend/app/core/deps.py`
- Create: `backend/app/api/rest/auth.py`
- Modify: `backend/app/main.py`（注册 auth 路由）
- Modify: `backend/pyproject.toml`（加 `passlib[bcrypt]>=1.7`、`python-jose[cryptography]>=3.3`）
- Create: `backend/app/infra/alembic/versions/0002_users_and_roles.py`
- Create: `backend/tests/integration/test_auth.py`

> ⚠️ **安全要点**：
> - 密码哈希用 bcrypt（cost ≥ 12）；登录失败响应不区分"用户不存在"与"密码错误"。
> - JWT secret 不允许默认值在生产环境运行（启动时 `assert settings.app.env != "prod" or jwt.secret != "dev-only-change-me"`）。
> - refresh_token 写入 Redis 白名单，登出时拉黑；access_token 仅签名校验，不查 DB。
> - `users.password_hash` 字段不出现在任何响应 schema 中。
> - 角色字段 `role` 限定 `visitor / admin`，注册默认 `visitor`，admin 通过种子脚本或后台手工设置。

- [ ] **Step 1: 迁移文件**

`backend/app/infra/alembic/versions/0002_users_and_roles.py`:

```python
"""users and roles

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(64), nullable=True),
        sa.Column("role", sa.String(16), nullable=False, server_default="visitor"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_check_constraint("ck_users_role", "users",
                               "role IN ('visitor','admin')")
    op.create_check_constraint("ck_users_status", "users",
                               "status IN ('active','disabled')")

def downgrade() -> None:
    op.drop_table("users")
```

执行迁移：

```
uv run alembic upgrade head
```

- [ ] **Step 2: 写失败测试**

`backend/tests/integration/test_auth.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_register_login_refresh_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/auth/register", json={
            "email": "u1@example.com", "password": "Passw0rd!",
            "display_name": "U1",
        })
        assert r.status_code == 201, r.text

        r = await c.post("/auth/login", json={
            "email": "u1@example.com", "password": "Passw0rd!",
        })
        assert r.status_code == 200
        tokens = r.json()
        assert "access_token" in tokens and "refresh_token" in tokens

        r = await c.get("/auth/me",
                        headers={"Authorization": f"Bearer {tokens['access_token']}"})
        assert r.status_code == 200
        assert r.json()["email"] == "u1@example.com"

        r = await c.post("/auth/refresh",
                         json={"refresh_token": tokens["refresh_token"]})
        assert r.status_code == 200
        assert r.json()["access_token"] != tokens["access_token"]

@pytest.mark.asyncio
async def test_login_fail_does_not_leak_user_existence():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r1 = await c.post("/auth/login", json={"email": "no@x.com", "password": "x"})
        r2 = await c.post("/auth/login", json={"email": "u1@example.com", "password": "wrong"})
        assert r1.status_code == r2.status_code == 401
        assert r1.json()["detail"] == r2.json()["detail"]
```

- [ ] **Step 3: 验证失败**

预期：FAIL。

- [ ] **Step 4: 实现**

`backend/app/domain/identity/models.py`:

```python
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy import BigInteger, String, DateTime, func

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16), default="visitor")
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())
```

`backend/app/domain/identity/schemas.py`:

```python
from pydantic import BaseModel, EmailStr, Field

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = None

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    email: str
    display_name: str | None = None
    role: str
```

`backend/app/core/security.py`:

```python
from datetime import datetime, timedelta, timezone
from typing import Literal
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def hash_password(p: str) -> str: return _pwd.hash(p)
def verify_password(p: str, h: str) -> bool: return _pwd.verify(p, h)

def _now() -> datetime: return datetime.now(timezone.utc)

def issue_token(sub: str, role: str, kind: Literal["access", "refresh"]) -> str:
    s = get_settings().jwt
    ttl = s.access_ttl_seconds if kind == "access" else s.refresh_ttl_seconds
    payload = {
        "sub": sub, "role": role, "kind": kind,
        "iat": int(_now().timestamp()),
        "exp": int((_now() + timedelta(seconds=ttl)).timestamp()),
    }
    return jwt.encode(payload, s.secret, algorithm=s.algorithm)

def decode_token(token: str) -> dict:
    s = get_settings().jwt
    try:
        return jwt.decode(token, s.secret, algorithms=[s.algorithm])
    except JWTError as e:
        raise ValueError("invalid_token") from e
```

`backend/app/domain/identity/repository.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import User

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        return (await self.session.execute(
            select(User).where(User.email == email))).scalar_one_or_none()

    async def get_by_id(self, uid: int) -> User | None:
        return await self.session.get(User, uid)

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user
```

`backend/app/domain/identity/service.py`:

```python
from fastapi import HTTPException, status
from app.core.security import hash_password, verify_password, issue_token, decode_token
from app.infra.redis import get_redis
from .models import User
from .repository import UserRepository
from .schemas import RegisterIn, LoginIn, TokenPair

REFRESH_KEY = "auth:refresh:{token}"

class IdentityService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def register(self, payload: RegisterIn) -> User:
        if await self.repo.get_by_email(payload.email):
            raise HTTPException(status.HTTP_409_CONFLICT, "email_taken")
        u = User(email=payload.email,
                 password_hash=hash_password(payload.password),
                 display_name=payload.display_name)
        return await self.repo.create(u)

    async def login(self, payload: LoginIn) -> TokenPair:
        u = await self.repo.get_by_email(payload.email)
        if not u or not verify_password(payload.password, u.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
        if u.status != "active":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
        return await self._issue_pair(u)

    async def refresh(self, refresh_token: str) -> TokenPair:
        try:
            payload = decode_token(refresh_token)
            assert payload.get("kind") == "refresh"
        except Exception:
            raise HTTPException(401, "invalid_token")
        r = get_redis()
        if not await r.get(REFRESH_KEY.format(token=refresh_token)):
            raise HTTPException(401, "revoked_token")
        u = await self.repo.get_by_id(int(payload["sub"]))
        if not u or u.status != "active":
            raise HTTPException(401, "invalid_token")
        await r.delete(REFRESH_KEY.format(token=refresh_token))
        return await self._issue_pair(u)

    async def _issue_pair(self, u: User) -> TokenPair:
        access = issue_token(str(u.id), u.role, "access")
        refresh = issue_token(str(u.id), u.role, "refresh")
        from app.core.config import get_settings
        await get_redis().set(REFRESH_KEY.format(token=refresh),
                              str(u.id),
                              ex=get_settings().jwt.refresh_ttl_seconds)
        return TokenPair(access_token=access, refresh_token=refresh)
```

`backend/app/core/deps.py`:

```python
from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import decode_token
from app.infra.db import get_session_factory
from app.domain.identity.repository import UserRepository
from app.domain.identity.service import IdentityService
from app.domain.identity.models import User

async def get_db_session() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as s:
        yield s

def get_identity_service(s: AsyncSession = Depends(get_db_session)) -> IdentityService:
    return IdentityService(UserRepository(s))

async def get_current_user(authorization: str = Header(None),
                           svc: IdentityService = Depends(get_identity_service)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing_token")
    try:
        payload = decode_token(authorization.removeprefix("Bearer "))
        assert payload.get("kind") == "access"
    except Exception:
        raise HTTPException(401, "invalid_token")
    u = await svc.repo.get_by_id(int(payload["sub"]))
    if not u or u.status != "active":
        raise HTTPException(401, "invalid_token")
    return u

def require_admin(u: User = Depends(get_current_user)) -> User:
    if u.role != "admin":
        raise HTTPException(403, "forbidden")
    return u
```

`backend/app/api/rest/auth.py`:

```python
from fastapi import APIRouter, Depends, status
from app.core.deps import get_identity_service, get_current_user
from app.domain.identity.service import IdentityService
from app.domain.identity.schemas import RegisterIn, LoginIn, TokenPair, UserOut
from app.domain.identity.models import User
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])

class RefreshIn(BaseModel):
    refresh_token: str

@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut)
async def register(p: RegisterIn, svc: IdentityService = Depends(get_identity_service)):
    u = await svc.register(p)
    return UserOut(id=u.id, email=u.email, display_name=u.display_name, role=u.role)

@router.post("/login", response_model=TokenPair)
async def login(p: LoginIn, svc: IdentityService = Depends(get_identity_service)):
    return await svc.login(p)

@router.post("/refresh", response_model=TokenPair)
async def refresh(p: RefreshIn, svc: IdentityService = Depends(get_identity_service)):
    return await svc.refresh(p.refresh_token)

@router.get("/me", response_model=UserOut)
async def me(u: User = Depends(get_current_user)):
    return UserOut(id=u.id, email=u.email, display_name=u.display_name, role=u.role)
```

修改 `app/main.py` 注册路由：

```python
from app.api.rest import system, auth
...
app.include_router(system.router)
app.include_router(auth.router)
```

加依赖 `passlib[bcrypt]>=1.7`、`python-jose[cryptography]>=3.3` 到 `pyproject.toml` 后 `uv sync --extra dev`。

- [ ] **Step 5: 验证通过**

```
uv run pytest tests/integration/test_auth.py -v
```

预期：2 passed。

- [ ] **Step 6: 提交**

```
git add backend/
git commit -m "feat(auth): users table + jwt dual token + register/login/refresh"
```

> ⚠️ **延伸注意**：
> - 注册接口未做邮箱验证；若上线需走"邮件验证码"或后台审批，列入 Phase 4 的"用户管理"补丁任务。
> - 多次失败登录限频留到 Phase 0 末（如时间紧可挪到 Phase 3 的"对外暴露"前），通过 `slowapi` 中间件实现，键 `email + ip`，5 次/15 分钟。

---

## Task 0.10: 前端 monorepo + ui-shared 初版

**Files:**
- Create: `apps/web-user/package.json`
- Create: `apps/web-user/vite.config.ts`
- Create: `apps/web-user/tsconfig.json`
- Create: `apps/web-user/index.html`
- Create: `apps/web-user/src/main.ts`
- Create: `apps/web-user/src/App.vue`
- Create: `apps/web-user/src/pages/Login.vue`
- Create: `apps/web-user/src/services/http.ts`
- Create: `apps/web-user/src/stores/auth.ts`
- Create: `apps/web-user/tests/login.spec.ts`
- Create: `apps/web-admin/`（与 web-user 同构，仅 baseUrl/路由不同）
- Create: `packages/ui-shared/package.json`
- Create: `packages/ui-shared/src/tokens.css`
- Create: `packages/ui-shared/src/components/GlassCard.vue`
- Create: `packages/ui-shared/src/components/GlassButton.vue`
- Create: `packages/ui-shared/src/components/GlassInput.vue`
- Create: `packages/ui-shared/src/components/GlassModal.vue`
- Create: `packages/ui-shared/src/index.ts`
- Create: `packages/ui-shared/tsconfig.json`

> ⚠️ **设计原则**：本任务仅完成"骨架 + 登录页 + 1 个能跳转受保护页的路由 guard"。详细 UI 风格与 Live2D、聊天页放到 Phase 1。

- [ ] **Step 1: 写失败测试（Vitest 组件渲染）**

`packages/ui-shared/src/components/__tests__/GlassButton.spec.ts`（先建空目录）:

```typescript
import { mount } from "@vue/test-utils"
import { describe, it, expect } from "vitest"
import GlassButton from "../GlassButton.vue"

describe("GlassButton", () => {
  it("emits click", async () => {
    const w = mount(GlassButton, { slots: { default: "OK" } })
    await w.trigger("click")
    expect(w.emitted("click")).toBeTruthy()
    expect(w.text()).toContain("OK")
  })
})
```

`apps/web-user/tests/login.spec.ts`:

```typescript
import { mount } from "@vue/test-utils"
import { describe, it, expect } from "vitest"
import Login from "../src/pages/Login.vue"

describe("Login page", () => {
  it("renders email and password fields", () => {
    const w = mount(Login)
    expect(w.find('input[type="email"]').exists()).toBe(true)
    expect(w.find('input[type="password"]').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: 验证失败**

```
pnpm -r run test
```

预期：FAIL。

- [ ] **Step 3: ui-shared 实现**

`packages/ui-shared/package.json`:

```json
{
  "name": "@eira/ui-shared",
  "version": "0.0.1",
  "type": "module",
  "main": "./src/index.ts",
  "scripts": {
    "test": "vitest run",
    "lint": "eslint src --ext .ts,.vue"
  },
  "peerDependencies": { "vue": "^3.4.0" },
  "devDependencies": {
    "@vue/test-utils": "^2.4.0",
    "vitest": "^1.6.0",
    "typescript": "^5.4.0",
    "happy-dom": "^14.0.0"
  }
}
```

`packages/ui-shared/src/tokens.css`:

```css
:root {
  --eira-glass-bg: rgba(255,255,255,0.55);
  --eira-glass-bg-dark: rgba(20,28,48,0.55);
  --eira-glass-border: rgba(255,255,255,0.35);
  --eira-glass-blur: 18px;
  --eira-radius-sm: 12px;
  --eira-radius-md: 18px;
  --eira-radius-lg: 24px;
  --eira-shadow-soft: 0 6px 24px rgba(20,40,80,0.10);
  --eira-text-primary: #1a2233;
  --eira-text-muted: #5b6478;
  --eira-accent: #4f8cff;
}
```

`packages/ui-shared/src/components/GlassButton.vue`:

```vue
<script setup lang="ts">
defineProps<{ variant?: "primary" | "ghost"; disabled?: boolean }>()
defineEmits<{ click: [Event] }>()
</script>
<template>
  <button class="g-btn" :class="variant" :disabled="disabled" @click="$emit('click', $event)">
    <slot />
  </button>
</template>
<style scoped>
.g-btn {
  padding: 10px 18px;
  border-radius: var(--eira-radius-md);
  border: 1px solid var(--eira-glass-border);
  background: var(--eira-glass-bg);
  backdrop-filter: blur(var(--eira-glass-blur));
  color: var(--eira-text-primary);
  cursor: pointer;
  transition: transform .15s ease, box-shadow .2s ease;
}
.g-btn:hover { transform: translateY(-1px); box-shadow: var(--eira-shadow-soft); }
.g-btn.primary { background: var(--eira-accent); color: #fff; border-color: transparent; }
.g-btn:disabled { opacity: .5; cursor: not-allowed; }
</style>
```

`GlassInput.vue` `GlassCard.vue` `GlassModal.vue` 同风格（详细可在执行阶段按 DESIGN.txt 描述补完）。

`packages/ui-shared/src/index.ts`:

```typescript
export { default as GlassButton } from "./components/GlassButton.vue"
export { default as GlassInput } from "./components/GlassInput.vue"
export { default as GlassCard } from "./components/GlassCard.vue"
export { default as GlassModal } from "./components/GlassModal.vue"
import "./tokens.css"
```

- [ ] **Step 4: web-user 实现**

`apps/web-user/package.json`:

```json
{
  "name": "@eira/web-user",
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "test": "vitest run",
    "lint": "eslint src --ext .ts,.vue"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.0",
    "axios": "^1.7.0",
    "@eira/ui-shared": "workspace:*"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.2.0",
    "vue-tsc": "^2.0.0",
    "typescript": "^5.4.0",
    "@vue/test-utils": "^2.4.0",
    "vitest": "^1.6.0",
    "happy-dom": "^14.0.0"
  }
}
```

`apps/web-user/vite.config.ts`:

```typescript
import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
export default defineConfig({
  plugins: [vue()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
  test: { environment: "happy-dom", globals: true },
})
```

`apps/web-user/src/services/http.ts`:

```typescript
import axios from "axios"
import { useAuthStore } from "../stores/auth"

export const http = axios.create({ baseURL: "/api" })
http.interceptors.request.use((cfg) => {
  const t = useAuthStore().accessToken
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  return cfg
})
```

`apps/web-user/src/stores/auth.ts`:

```typescript
import { defineStore } from "pinia"
import axios from "axios"

export const useAuthStore = defineStore("auth", {
  state: () => ({
    accessToken: localStorage.getItem("eira:at") || "",
    refreshToken: localStorage.getItem("eira:rt") || "",
    user: null as null | { id: number; email: string; role: string },
  }),
  actions: {
    async login(email: string, password: string) {
      const r = await axios.post("/api/auth/login", { email, password })
      this.accessToken = r.data.access_token
      this.refreshToken = r.data.refresh_token
      localStorage.setItem("eira:at", this.accessToken)
      localStorage.setItem("eira:rt", this.refreshToken)
    },
    logout() {
      this.accessToken = ""; this.refreshToken = ""; this.user = null
      localStorage.removeItem("eira:at"); localStorage.removeItem("eira:rt")
    },
  },
})
```

`apps/web-user/src/pages/Login.vue`:

```vue
<script setup lang="ts">
import { ref } from "vue"
import { useRouter } from "vue-router"
import { GlassButton, GlassInput, GlassCard } from "@eira/ui-shared"
import { useAuthStore } from "../stores/auth"

const email = ref(""), password = ref(""), err = ref("")
const auth = useAuthStore(), router = useRouter()

async function submit() {
  try {
    await auth.login(email.value, password.value)
    router.push("/chat")
  } catch (e: any) {
    err.value = "登录失败，请检查账号密码"
  }
}
</script>
<template>
  <div class="login-shell">
    <h1 class="brand">Eira</h1>
    <GlassCard>
      <input type="email" v-model="email" placeholder="邮箱" />
      <input type="password" v-model="password" placeholder="密码" />
      <GlassButton variant="primary" @click="submit">登录</GlassButton>
      <p v-if="err" class="err">{{ err }}</p>
    </GlassCard>
  </div>
</template>
```

`apps/web-user/src/main.ts`:

```typescript
import { createApp } from "vue"
import { createPinia } from "pinia"
import { createRouter, createWebHistory } from "vue-router"
import App from "./App.vue"
import Login from "./pages/Login.vue"
import { useAuthStore } from "./stores/auth"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: Login },
    { path: "/chat", component: () => import("./pages/Chat.vue"),
      meta: { requiresAuth: true } },
    { path: "/", redirect: "/chat" },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.accessToken) return "/login"
})

createApp(App).use(createPinia()).use(router).mount("#app")
```

`apps/web-user/src/pages/Chat.vue`（占位，Phase 1 改写）:

```vue
<template><div>Chat placeholder</div></template>
```

`apps/web-user/src/App.vue`:

```vue
<template><router-view /></template>
```

`apps/web-user/index.html`:

```html
<!doctype html>
<html><head><meta charset="utf-8"/><title>Eira</title></head>
<body><div id="app"></div><script type="module" src="/src/main.ts"></script></body></html>
```

`apps/web-user/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022", "module": "ESNext", "moduleResolution": "Bundler",
    "strict": true, "jsx": "preserve", "types": ["vitest/globals"],
    "lib": ["ES2022", "DOM"], "esModuleInterop": true,
    "skipLibCheck": true, "isolatedModules": true
  },
  "include": ["src/**/*", "tests/**/*"]
}
```

**web-admin 同构**：仅复制 web-user 结构，端口改 5174，`pages/` 替换为后台 placeholder（如 `Dashboard.vue`）。在 Phase 4 才补真实页面。

- [ ] **Step 5: 安装 + 验证**

```
pnpm -w install
pnpm -r run test
pnpm -r run build
```

预期：所有包测试通过、build 成功。

- [ ] **Step 6: 提交**

```
git add apps/ packages/ pnpm-lock.yaml
git commit -m "feat(frontend): bootstrap web-user/web-admin + ui-shared package"
```

---

## Task 0.11: Docker Compose 全栈 + Nginx

**Files:**
- Create: `backend/Dockerfile`
- Create: `apps/web-user/Dockerfile`
- Create: `apps/web-admin/Dockerfile`
- Create: `deploy/docker-compose.yml`（生产用，与 dev 同构）
- Create: `deploy/nginx/nginx.conf`
- Create: `deploy/nginx/conf.d/eira.conf`

> ⚠️ **要点**：
> - 后端镜像分两段（builder + runtime）；非 root 用户运行。
> - 前端用 `nginx:alpine` 作为静态托管；统一由前置 Nginx 路由。
> - 生产 `.env` 通过 Docker Secret 挂载，**不要** `env_file: .env`。

- [ ] **Step 1: backend Dockerfile**

`backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev || uv sync --no-dev

FROM python:3.11-slim AS runtime
RUN useradd -u 10001 -m eira
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --chown=eira:eira . .
ENV PATH=/app/.venv/bin:$PATH
USER eira
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 前端 Dockerfile**

`apps/web-user/Dockerfile`:

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /repo
RUN corepack enable
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY packages ./packages
COPY apps/web-user ./apps/web-user
RUN pnpm install --frozen-lockfile
RUN pnpm --filter @eira/web-user build

FROM nginx:alpine AS runtime
COPY --from=builder /repo/apps/web-user/dist /usr/share/nginx/html
COPY deploy/nginx/spa.conf /etc/nginx/conf.d/default.conf
```

`apps/web-admin/Dockerfile` 同结构，仅替换 filter 名。

`deploy/nginx/spa.conf`（前端容器内）:

```nginx
server {
  listen 80;
  root /usr/share/nginx/html;
  index index.html;
  location / { try_files $uri /index.html; }
}
```

- [ ] **Step 3: 顶层 nginx 反代**

`deploy/nginx/nginx.conf` 用默认；`deploy/nginx/conf.d/eira.conf`:

```nginx
upstream backend { server backend:8000; }
upstream web_user { server web-user:80; }
upstream web_admin { server web-admin:80; }

server {
  listen 80;
  server_name _;
  client_max_body_size 64M;

  location /api/ { proxy_pass http://backend/; proxy_set_header Host $host;
                   proxy_set_header X-Real-IP $remote_addr; }
  location /ws/  { proxy_pass http://backend; proxy_http_version 1.1;
                   proxy_set_header Upgrade $http_upgrade;
                   proxy_set_header Connection "Upgrade";
                   proxy_read_timeout 3600s; }
  location /admin/ { proxy_pass http://web_admin/; }
  location / { proxy_pass http://web_user/; }
}
```

- [ ] **Step 4: docker-compose.yml**

`deploy/docker-compose.yml`:

```yaml
services:
  pg:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-eira}
      POSTGRES_USER: ${POSTGRES_USER:-eira}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-eira}
    volumes: [eira-pg:/var/lib/postgresql/data]
    healthcheck: { test: ["CMD","pg_isready","-U","eira"], interval: 5s }

  redis:
    image: redis:7-alpine
    healthcheck: { test: ["CMD","redis-cli","ping"], interval: 5s }

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-eira}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-eira-secret}
    volumes: [eira-minio:/data]

  backend:
    build: { context: ../backend, dockerfile: Dockerfile }
    env_file: .env
    depends_on: { pg: { condition: service_healthy }, redis: { condition: service_healthy } }
    healthcheck: { test: ["CMD","python","-c","import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz').status==200 else 1)"], interval: 10s }

  web-user:
    build: { context: .., dockerfile: apps/web-user/Dockerfile }

  web-admin:
    build: { context: .., dockerfile: apps/web-admin/Dockerfile }

  nginx:
    image: nginx:alpine
    ports: ["80:80"]
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
    depends_on: [backend, web-user, web-admin]

volumes:
  eira-pg:
  eira-minio:
```

- [ ] **Step 5: 验证**

```
cp deploy/.env.example deploy/.env
cd deploy && docker compose build
docker compose up -d
curl -fsS http://localhost/api/healthz
curl -fsS http://localhost/         # web-user 静态首页
curl -fsS http://localhost/admin/   # web-admin 静态首页
```

预期：3 个 200。

- [ ] **Step 6: 提交**

```
git add deploy/ backend/Dockerfile apps/*/Dockerfile
git commit -m "infra(deploy): full-stack docker compose with nginx reverse proxy"
```

---

## Task 0.12: CI 工作流（lint + test + build）

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/build-images.yml`（仅在 main 分支）

> ⚠️ **要点**：CI 必须以服务容器形式跑 PG/Redis/MinIO，避免依赖外部基础设施。`uv` 在 GitHub Actions 上需要 `astral-sh/setup-uv` action。

- [ ] **Step 1: ci.yml**

`.github/workflows/ci.yml`:

```yaml
name: ci
on:
  pull_request:
  push: { branches: [main] }

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      pg:
        image: pgvector/pgvector:pg16
        env: { POSTGRES_DB: eira, POSTGRES_USER: eira, POSTGRES_PASSWORD: eira }
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U eira"
          --health-interval 5s --health-retries 10
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
      minio:
        image: minio/minio:latest
        env: { MINIO_ROOT_USER: eira, MINIO_ROOT_PASSWORD: eira-secret }
        ports: ["9000:9000"]
        options: >-
          --health-cmd "curl -f http://localhost:9000/minio/health/ready || exit 1"
          --health-interval 10s --health-retries 12
    env:
      EIRA_DB__DSN: postgresql+asyncpg://eira:eira@localhost:5432/eira
      EIRA_REDIS__URL: redis://localhost:6379/0
      EIRA_OSS__ENDPOINT: http://localhost:9000
      EIRA_OSS__KEY: eira
      EIRA_OSS__SECRET: eira-secret
      EIRA_JWT__SECRET: ci-test-secret
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - uses: astral-sh/setup-uv@v3
      - name: install
        working-directory: backend
        run: uv sync --extra dev
      - name: init oss buckets
        working-directory: backend
        run: uv run python ../scripts/init_oss_buckets.py
      - name: alembic upgrade
        working-directory: backend
        run: uv run alembic upgrade head
      - name: ruff
        working-directory: backend
        run: uv run ruff check .
      - name: mypy (limited)
        working-directory: backend
        run: uv run mypy app/domain app/orchestrator app/capabilities || true
      - name: pytest
        working-directory: backend
        run: uv run pytest --cov=app --cov-report=xml --cov-fail-under=70

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: corepack enable
      - run: pnpm install --frozen-lockfile
      - run: pnpm -r run lint
      - run: pnpm -r run test
      - run: pnpm -r run build
```

- [ ] **Step 2: 提交并验证**

```
git add .github/
git commit -m "chore(ci): add backend+frontend pipeline"
git push
```

观察 GitHub Actions：两个 job 全绿。

> ⚠️ **覆盖率门**：`--cov-fail-under=70` 在 Phase 0 较容易满足；Phase 1+ 业务进入后维持 70%，Phase 6 末提升至 80%。如某次 PR 因临时实验掉到 65%，**不允许直接降阈值**，必须补测试。

---

## Task 0.13: pre-commit hooks

**Files:**
- Create: `.pre-commit-config.yaml`
- Create: `.gitleaks.toml`（可选）

- [ ] **Step 1: 配置**

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks: [{id: trailing-whitespace}, {id: end-of-file-fixer},
            {id: check-yaml}, {id: check-merge-conflict}, {id: detect-private-key}]
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks: [{id: ruff, args: ["--fix"]}, {id: ruff-format}]
  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.1.0
    hooks: [{id: prettier, types_or: [vue, ts, tsx, javascript, json, css, markdown]}]
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks: [{id: gitleaks}]
```

- [ ] **Step 2: 验证**

```
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

预期：通过或自动修复后通过。

- [ ] **Step 3: 提交**

```
git add .pre-commit-config.yaml
git commit -m "chore: add pre-commit hooks (ruff/prettier/gitleaks)"
```

---

## 🚦 Validation Gate G-0.1 · 本地全栈一键启动

| 项 | 内容 |
|---|---|
| 指标 | `docker compose up -d` 后所有服务变为 healthy 的时间；`/healthz` 与 `/readyz` 全 200；前端 `/`、`/admin/` 静态页可访问 |
| 阈值 | 启动到全部 healthy ≤ 90s（i7/16G 笔记本基线）；`/readyz` 字段 db/redis/oss 均为 `up`；3 个静态/接口请求 `< 500ms` 平均 |
| 测试方法 | 1) `cp deploy/.env.example deploy/.env`；2) `cd deploy && docker compose down -v && docker compose up -d --build`；3) 等待并轮询 `docker compose ps --format json` 直到所有 `Health=healthy`，记录 wall-clock 耗时；4) `curl -w "%{time_total}\n" -o /dev/null -s http://localhost/api/healthz` 等 5 个 endpoint 各 10 次取平均 |
| 数据源 | `docker compose ps` 输出、curl 时间数据；归档到 `docs/superpowers/validations/G-0.1.md` |
| 通过分支 | 打 tag `gate-G-0.1-passed`；进入 Phase 1 |
| 不通过分支 | 若启动 > 90s 但 ≤ 180s：检查 `pg`/`minio` 健康脚本与初始化是否串行化等待，可调整 `depends_on.condition`；若 > 180s：回到 T0.11 优化（如 minio 用 `mc ready`、PG 加 `shared_preload_libraries=pgvector`）；若 `/readyz` 某项 down：定位日志（`docker compose logs <svc>`）回对应 Task 修；若 nginx 反代失败：回 T0.11 修 `eira.conf` |

---

## 🚦 Validation Gate G-0.2 · 鉴权回路与安全基线

| 项 | 内容 |
|---|---|
| 指标 | (a) register→login→/auth/me→refresh 完整链路 P95 延迟；(b) bcrypt 哈希成本 ≥ 12；(c) 错误登录响应不泄露用户存在性；(d) refresh_token 重放（同一 token 二次使用）失败 |
| 阈值 | (a) P95 < 500ms（不含首次冷启）；(b) 必须 ≥ 12；(c) 错误状态码 / detail 完全一致；(d) 第二次必须 401 |
| 测试方法 | 1) `pytest tests/integration/test_auth.py -v`；2) 写一个 `scripts/load_auth.py` 用 `httpx.AsyncClient` 并发 50 reqs × 20 轮，统计 P50/P95；3) 单元测试断言 `_pwd.bcrypt__rounds`；4) 重放测试已在 `test_auth.py` 中追加 |
| 数据源 | pytest 报告 + 自建脚本输出；归档 `docs/superpowers/validations/G-0.2.md` |
| 通过分支 | 进入 Phase 1 |
| 不通过分支 | (a) > 500ms 但 < 1s：先排查 DB 连接池、bcrypt 成本（成本太低不能放）→ 优化 connection pool size，可降 bcrypt 至 12 但不可 < 12；> 1s：回 T0.9 重构（可能 sessionmaker 未复用）；(c) 不一致：必修，回 T0.9 service.login 统一异常；(d) 重放成功：必修，refresh 必须删除旧 redis key |

---

## 🚦 Validation Gate G-0.3 · CI 全绿基线

| 项 | 内容 |
|---|---|
| 指标 | (a) `ci.yml` 三个 job 全绿耗时；(b) 测试覆盖率（行）；(c) lint/format 零警告 |
| 阈值 | (a) 总耗时 ≤ 8 分钟；(b) ≥ 70%；(c) `ruff check .` 与 `pnpm -r run lint` 零 error |
| 测试方法 | 推 PR 触发 CI；GitHub Actions 工作流页面读取耗时与 coverage 报告 |
| 数据源 | Actions 页面 + `coverage.xml`；归档 `docs/superpowers/validations/G-0.3.md` |
| 通过分支 | 合入 main，打 `gate-G-0.3-passed` |
| 不通过分支 | 时间超：拆分 jobs / 启用缓存（`actions/cache` for uv & pnpm）；覆盖率不足：补测试；lint 失败：修代码不可降配 |

---

## 完成状态

Phase 0 完成 ⇔ G-0.1 / G-0.2 / G-0.3 全部 passed。否则**不允许**启动 Phase 1。

后续 Phase 的所有任务文件均在本仓库 `docs/superpowers/plans/` 下，按编号顺序执行。

