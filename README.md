# Eira

> AI 语音导游助手 — Vue 3 前端 + FastAPI 后端 + Live2D 角色渲染

## 项目结构

```
Eira/
├── apps/
│   ├── shared/live2d/      # 共享 Live2D 加载模块（JSZip + fetch 拦截器 + IndexedDB 缓存）
│   ├── web-user/           # 用户端 (Vue 3 + Vite) — http://localhost:5173
│   └── web-admin/          # 管理后台 (Vue 3 + Vite) — http://localhost:5174
├── backend/                # FastAPI 后端 — http://localhost:8000
│   ├── app/
│   │   ├── api/rest/       # REST 路由模块
│   │   ├── api/ws/         # /ws/chat + /ws/voice
│   │   ├── capabilities/   # LLM / ASR / TTS / Embedding / Search Provider
│   │   ├── core/           # 配置 / 安全 / 限流 / 文件校验 / 审计
│   │   ├── domain/         # identity / conversation / knowledge / persona / system
│   │   ├── infra/          # DB / Redis / OSS / Alembic
│   │   ├── orchestrator/   # LangGraph 图 + 8 节点 + 句切引擎
│   │   └── workers/        # 知识库异步管线
│   ├── scripts/
│   │   ├── run_clean.sh    # 干净启动脚本（杀端口 + 清 pycache + 无 reload）
│   │   └── seed_models.py  # 一次性上传模型到 OSS
│   └── tests/              # 按功能模块组织（infra/identity/persona/conversation/knowledge/voice/llm）
├── packages/               # 共享包 (@eira/ui-shared)
├── deploy/                 # Docker Compose 编排文件
└── docs/                   # 文档、验证门、Handoff
```

## 前置依赖

| 工具 | 版本要求 | 用途 |
|------|----------|------|
| Python | 3.12+ | 后端运行时 |
| Node.js | 20+ | 前端运行时 |
| pnpm | 9+ | 前端包管理器（monorepo） |
| Docker Desktop | 最新 | PostgreSQL / Redis / MinIO 容器 |

## 快速启动（完整流程）

### 第一步：启动基础设施（Docker）

打开 **PowerShell** 或 **CMD**，进入项目目录：

```powershell
cd D:\Application\ClaudeCode\repository\Eira

# 启动 PostgreSQL + Redis + MinIO
docker compose -f deploy\docker-compose.dev.yml up -d
```

等待容器就绪（约 15 秒）。验证：

```powershell
docker ps --format "table {{.Names}}\t{{.Status}}"
# 预期输出：
# deploy-pg-1      Up X seconds (healthy)
# deploy-redis-1   Up X seconds (healthy)
# deploy-minio-1   Up X seconds
```

> **注意**：首次启动 MinIO 需创建 bucket。如果后端日志出现 OSS 错误，执行：
> ```powershell
> docker exec deploy-minio-1 mc alias set local http://localhost:9000 eira eira-secret
> docker exec deploy-minio-1 mc mb local/eira-user-assets
> ```

### 第二步：安装前端依赖

```powershell
# 在项目根目录
pnpm install
```

### 第三步：启动后端

**推荐方式 — 干净启动（Git Bash）**：

```bash
# 自动杀净 8000 端口残留进程 + 清 __pycache__ + 无 reload 单进程启动
bash backend/scripts/run_clean.sh
```

**手动方式（PowerShell）**：

打开 **新的** PowerShell 窗口：

```powershell
cd D:\Application\ClaudeCode\repository\Eira\backend

# 设置环境变量并启动（PowerShell 语法）
$env:EIRA_JWT__SECRET = "dev-secret"
$env:EIRA_OSS__SECRET = "eira-secret"
$env:EIRA_DB_DSN = "postgresql+asyncpg://eira:eira@localhost:5432/eira"
$env:EIRA_REDIS_URL = "redis://localhost:6379/0"
$env:EIRA_OSS_ENDPOINT = "http://localhost:9000"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

验证：浏览器打开 `http://localhost:8000/`，应返回 `{"service":"eira-backend","version":"0.1.0"}`。

### 第四步：启动前端

打开 **另一个** PowerShell 窗口：

```powershell
cd D:\Application\ClaudeCode\repository\Eira

# 用户端 (开发模式)
pnpm --filter @eira/web-user dev
```

浏览器打开 `http://localhost:5173` 即可使用。

> **管理后台**（可选）：
> ```powershell
> pnpm --filter @eira/web-admin dev
> # 浏览器打开 http://localhost:5174
> ```

---

## Live2D 架构

### 模型加载全链路

```
MinIO OSS (live2d-models/{model_id}.zip)
  ↓ boto3 get_object_bytes() 直读
Backend: /user/model/file?oss_key=  +  /admin/assets/{id}/file
  ↓ HTTP 200 + application/zip
共享模块: apps/shared/live2d/live2dLoader.ts
  ↓ downloadAndExtract(): fetch → JSZip 解压 → IndexedDB 缓存
  ↓ installFetchInterceptor(): 劫持 window.fetch → 虚拟 URL → Blob
  ↓ textureViaFetch(): PNG 纹理经 fetch 拦截器 → blob URL → Image.src
Cubism SDK for Web 5 Framework
  ↓ 自管 WebGL 渲染
<canvas>
```

### ⚠️ 标识体系约定

任何写入 `active_model_id` 的字段**必须是 OSS key**（格式：`live2d/.../xxx.zip`）。

| 字段 | 标准值 | 说明 |
|------|--------|------|
| `persona_config.active_model_id` | `live2d/8767b36fcc6c/mao_pro_zh.zip` | admin 设置，user 默认回退源 |
| `user_preferences.active_model_id` | 同上格式 或 null（走默认） | user 个人偏好 |

**脏值黑名单**：`eira-model://` (虚拟前缀)、显示名 (`mao_pro_zh`)、文件夹名。这些值传入会导致 502。

### 当前模型

| 名称 | OSS Key |
|------|---------|
| mao_pro_zh (默认) | `live2d/8767b36fcc6c/mao_pro_zh.zip` |
| hiyori_pro_zh | `live2d/1bd1c6347b0e/hiyori_pro_zh.zip` |
| akari_vts | `live2d/1672aa665401/akari_vts.rar` |
| hiyori_vts | `live2d/7c028e0d654d/hiyori_vts.rar` |
| PinkHair | `live2d/bdd4212ef2f3/PinkHair_workshop_2802653785.rar` |
| haru | `live2d/d39eb5b06545/haru.zip` |
| MaidCyrene | `live2d/6b8ee25433ee/MaidCyrene20251105_....zip` |

---

## 语音功能（Voice WS）

语音功能需要真实讯飞 ASR/TTS 凭证。开发测试时可使用 mock 模式：

```powershell
# 在后端启动命令中添加：
$env:EIRA_ASR__PROVIDER = "mock"
$env:EIRA_TTS__PROVIDER = "mock"
```

使用真实凭证时，需要设置以下环境变量：
- `EIRA_ASR__PROVIDER=xunfei` + `EIRA_ASR__API_KEY` + `EIRA_ASR__API_SECRET` + `EIRA_ASR__APP_ID`
- `EIRA_TTS__PROVIDER=xunfei` + `EIRA_TTS__API_KEY` + `EIRA_TTS__API_SECRET` + `EIRA_TTS__APP_ID`

### 语音调试

打开浏览器 F12 → Console，观察以下日志：
- `[Voice] WebM blob: X KB` — 录音数据量
- `[AudioProcessor] Source: ... peak=XdBFS` — 音频质量（峰值低于 -40dBFS 说明麦克风增益太低）
- `[Voice] Error no_speech` — 讯飞未检测到语音（检查麦克风或音频格式）
- `[Voice] Error asr_error` — ASR 管线错误（查看详情定位根因）
- `[Voice] Error rate_limited` — 发送过于频繁（正常语音不应触发）

---

## 运行测试

```powershell
cd D:\Application\ClaudeCode\repository\Eira\backend

# 设置环境变量后运行
$env:EIRA_JWT__SECRET = "test-secret"
$env:EIRA_OSS__SECRET = "eira-secret"
$env:EIRA_DB_DSN = "postgresql+asyncpg://eira:eira@localhost:5432/eira"
$env:EIRA_REDIS_URL = "redis://localhost:6379/0"
$env:EIRA_OSS_ENDPOINT = "http://localhost:9000"

python -m pytest tests/ -v --tb=short
```

测试按功能模块组织：`infra/` `identity/` `persona/` `conversation/` `knowledge/` `voice/` `llm/`

> **注意**：测试在开发库中运行，中断测试（Ctrl+C）会残留测试数据。

---

## 测试账号

| 地址 | 邮箱 | 密码 |
|------|------|------|
| http://localhost:5173/login | `admin@eira.dev` | `admin123` |
| http://localhost:5174/login | `admin@eira.dev` | `admin123` |

---

## 常见问题

| 现象 | 原因 | 解决 |
|------|------|------|
| `[Errno 10048]` 端口占用 | 已有后端进程在运行 | `taskkill /F /IM python.exe` 或使用 `bash backend/scripts/run_clean.sh` |
| 后端日志出现不该产生的旧值 | **残留旧进程跑旧代码** | 使用 `run_clean.sh` 重启，不要手动 `--reload` |
| Live2D 加载 502 | `active_model_id` 被污染为非 OSS key | 检查 DB 中 `persona_config.active_model_id` 是否以 `live2d/` 开头 |
| 模型切换后显示异常 | IndexedDB 缓存的旧模型 | 清浏览器 IndexedDB `eira-live2d-cache` + 硬刷新 |
| `ERR_UNKNOWN_URL_SCHEME` | 纹理 URL 未经过 fetch 拦截器 | 确保使用最新 `lapptexturemanager.ts`（走 `textureViaFetch`） |
| Docker 端口绑定失败 | Windows NAT 保留端口 | `net stop winnat && net start winnat` |
| 前端构建 `phase` 错误 | 变量名不一致 | 已修复（`phase` → `wsPhase`） |
| MinIO `SignatureDoesNotMatch` | bucket 未创建 | `docker exec deploy-minio-1 mc mb local/eira-user-assets` |
| 语音无反应 | 麦克风增益太低 | 检查 Windows 麦克风设置，确认 PCM 峰值 > -40dBFS |

## 文档

完整项目文档见 `docs/superpowers/handoff/`：
- [Phase 0-5 总结](docs/superpowers/handoff/2026-06-15-eira-phase-summary.md) — 项目全貌
- [Live2D 修复结论](docs/superpowers/handoff/eira-handoff-2026-06-15-live2d-resolved.md) — 标识体系 + 验证结果
- [Handoff 索引](docs/superpowers/handoff/README.md) — 全部文档导航
