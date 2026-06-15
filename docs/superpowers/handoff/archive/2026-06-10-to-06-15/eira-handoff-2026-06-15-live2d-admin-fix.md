# Eira 项目 Handoff · 2026-06-15 · Live2D Admin 模型加载修复

> **源会话**: web-user + web-admin Live2D 模型加载失败诊断与修复（7 轮迭代）
> **当前状态**: web-user ✅ 已修复 · web-admin ❌ 仍未解决
> **分支**: master

---

## 1. 会话摘要

本次会话从 web-user 和 web-admin 的 Live2D 模型加载失败出发，完成了：

- **web-user 修复（✅ 成功）**：纹理加载的 `Image.src` 绕过 `window.fetch` 拦截器导致 `ERR_UNKNOWN_URL_SCHEME`。通过共享模块 `textureViaFetch()` 将纹理路由经 fetch 拦截器 → blob URL → `Image.src`，模型正常显示。
- **共享模块抽取**：新建 `apps/shared/live2d/live2dLoader.ts`，统一 zip 下载/JSZip 解压/fetch 拦截/IndexedDB 缓存逻辑，消除 web-user 和 web-admin 两端 ~400 行重复代码。
- **web-admin 修复（❌ 未解决）**：经过 7 轮迭代尝试了 4 种不同方案，模型仍无法加载。

---

## 2. web-user 修复详情（已完成）

### 2.1 共享模块（新增）

**文件**: `apps/shared/live2d/live2dLoader.ts` (~285 行)

纯 TypeScript 工具模块，提供：
- `downloadAndExtract(url, cacheKey, options?)` — zip 下载 + JSZip 解压 + 可选 IndexedDB 缓存
- `createBlobBase(files, model3Path)` — 创建虚拟 URL + 文件名
- `installFetchInterceptor()` / `uninstallFetchInterceptor()` — 劫持 `window.fetch`
- `textureViaFetch(url)` — **核心修复**：通过 fetch（进拦截器）→ blob → `URL.createObjectURL` → `Image.src`，解决 PNG 纹理绕过拦截器的问题

### 2.2 纹理修复（核心 bug）

**文件**: `apps/web-user/src/live2d/lapptexturemanager.ts`
**文件**: `apps/web-admin/src/live2d/lapptexturemanager.ts`

Cubism SDK 通过 `img.src = fileName` 加载 PNG 纹理，此方式**不经过 `window.fetch`**。当 `fileName` 是 `eira-model://` 自定义协议 URL 时，浏览器直接抛出 `ERR_UNKNOWN_URL_SCHEME`。

修复：两处 `img.src = fileName` 改为 `_textureLoader.textureViaFetch(fileName).then(img => { ... })`。

### 2.3 Composables 精简

**文件**: `apps/web-user/src/composables/useLive2DModelLoader.ts` — 从 ~300 行精简为 ~100 行
**文件**: `apps/web-admin/src/composables/useLive2DPreview.ts` — 删除内联 zip/拦截器逻辑，委托给共享模块
**文件**: `apps/web-user/src/composables/useLive2DController.ts` — 新增 `onUnmounted` 中的 `modelLoader.cleanup()` 调用

### 2.4 其他修改

- **Vite configs**: 两个 `vite.config.ts` 新增 `@shared/live2d` alias 和 `jszip` resolve alias
- **tsconfig**: 两个 `tsconfig.json` 新增 `@shared/*` 和 `jszip` path aliases
- **模型匹配修复**: `useLive2DPreview.ts` 的 `changeModel` 扩展为四向匹配（id / _ossKey / _ossKeyStr / ossKey）
- **Auth header**: `useLive2DPreview.ts` 从 `useAuthStore` 获取 token 并传入 downloadAndExtract

### 2.5 提交列表

```
98003f1 fix: use 307 redirect to Vite proxy for admin Live2D download
7eab8d8 fix: use direct boto3 get_object() — same pattern as knowledge/service.py
ccc1c43 fix: force IPv4 for presigned URL fetch to avoid localhost/IPv6 signature mismatch
81e754a fix: use presigned URL + httpx stream to avoid boto3 get_object SignatureDoesNotMatch
3bd826e fix: add httpx timeout + HEAD probe before streaming to prevent hanging
e8d5221 fix: add auth headers to admin Live2D download request
89d42bb refactor: simplify useLive2DPreview — delegate to shared loader + fix model matching
289941f fix: route PNG textures through fetch interceptor in web-admin
f927cef refactor: simplify useLive2DModelLoader — delegate to shared loader module + add cleanup on unmount
5a1dba7 fix: route PNG textures through fetch interceptor in web-user
8446cf6 feat: add GET /admin/assets/{id}/file streaming download endpoint
eb70ae0 chore: add @shared/live2d alias in both vite configs
3a56dce feat: add shared Live2D loader module
```

---

## 3. web-admin 7 轮尝试记录

### 架构背景

- **MinIO**: Docker 容器，端口 9000，凭据 `eira / eira-secret`
- **后端**: 宿主机 Python uvicorn，端口 8000，通过 boto3 连接 MinIO
- **前端**: Vite dev server，端口 5174，`/oss` 代理到 `localhost:9000`
- **已确认**: web-user 的 presigned URL → `/oss/` Vite proxy → MinIO 路径**正常工作**

### 尝试 1: `get_object()` 直接读取

**修改**: `backend/app/api/rest/admin_assets.py` — `download_asset_file` 端点

```python
s3_response = get_oss_client().get_object(Bucket=bucket, Key=oss_key)
return StreamingResponse(s3_response["Body"].iter_chunks(), ...)
```

**结果**: ❌ `SignatureDoesNotMatch`

### 尝试 2: presigned URL + httpx 流式传输

**修改**: 生成 presigned URL → 后端 httpx 流式下载 → `StreamingResponse` 返回

```python
presigned = presign_get(bucket, oss_key, expires=60)
async with httpx.AsyncClient() as client:
    async with client.stream("GET", presigned) as resp:
        ...
```

**结果**: ❌ 请求挂起（无超时）

### 尝试 3: httpx 超时 + HEAD 探测

**修改**: 添加 `httpx.Timeout(30.0)` 和 HEAD 预检请求

**结果**: ❌ HEAD 返回 403 Forbidden

### 尝试 4: 强制 IPv4 + 显式 Host 头

**修改**: 将 URL 中 `localhost` 替换为 `127.0.0.1`，显式设置 `Host: localhost:9000`

```python
parsed = urlparse(presigned)
ipv4_url = urlunparse(parsed._replace(netloc=f"127.0.0.1:{parsed.port}"))
request_headers = {"Host": f"{original_host}:{parsed.port}"}
```

**结果**: ❌ 仍然 403 Forbidden

### 尝试 5: 回归 `get_object()`（怀疑凭据问题已修复）

**修改**: 删除所有 httpx 代码，回归最简单的 `get_object()` 方案

**结果**: ❌ 仍然 `SignatureDoesNotMatch`

**关键发现**: `knowledge/service.py:100-103` 使用完全相同的 `get_oss_client().get_object()` 模式。但该代码可能从未在生产中真正运行过（仅用于文档处理）。

### 尝试 6: 307 重定向

**修改**: 端点返回 `307 Temporary Redirect`，将 presigned URL 改写为 `/oss/...` 路径

```python
presigned = presign_get(bucket, oss_key, expires=60)
proxy_url = presigned.replace("http://localhost:9000/", "/oss/")
return RedirectResponse(url=proxy_url, status_code=307)
```

**结果**: ❌ 用户反馈"不行"（未提供具体错误详情）

### 尝试 7: 当前状态

**分析**: 
- web-user 的 presigned URL → Vite proxy 路径已验证可用
- 307 重定向本质上应该等价于 web-user 的流程（browser → `/oss/` → Vite proxy → MinIO）
- 可能的问题：`fetch()` 在 follow 307 重定向时携带了 Authorization header，干扰了 presigned URL 的签名验证
- 或者 presigned URL 签名在重定向过程中被破坏

---

## 4. 关键文件索引

| 文件 | 说明 |
|------|------|
| `apps/shared/live2d/live2dLoader.ts` | 共享加载模块（新增） |
| `apps/web-user/src/live2d/lapptexturemanager.ts` | 纹理加载修复（✅） |
| `apps/web-admin/src/live2d/lapptexturemanager.ts` | 纹理加载修复（✅） |
| `apps/web-user/src/composables/useLive2DModelLoader.ts` | 精简后的 user composable |
| `apps/web-admin/src/composables/useLive2DPreview.ts` | 精简后的 admin composable |
| `backend/app/api/rest/admin_assets.py` | admin 下载端点（7 次修改） |
| `backend/app/infra/oss.py` | boto3 OSS 客户端（`@lru_cache`） |
| `backend/app/core/config.py:22-27` | OssSettings 默认值（`secret=""`） |
| `deploy/docker-compose.dev.yml:27-28` | MinIO 凭据 `eira / eira-secret` |
| `docs/superpowers/specs/2026-06-14-live2d-fix-design.md` | 原始设计文档 |
| `docs/superpowers/plans/2026-06-14-live2d-fix-plan.md` | 原始实现计划 |

---

## 5. 已知未解决问题

1. **boto3 `get_object()` SignatureDoesNotMatch**: 凭据正确（web-user 的 presigned URL 能通过 MinIO 验证），但 boto3 直接调用 `get_object()` 始终签名不匹配。可能与 Docker Desktop Windows 的网络层有关。

2. **后端通过 httpx 访问 MinIO 失败**: 无论是 presigned URL 还是直接连接，后端 Python 进程都无法成功访问 MinIO（403 / 挂起）。浏览器通过 Vite proxy 则正常。

3. **307 重定向未生效**: 理论上应等价于 web-user 的流程，但实际未成功。需进一步排查 fetch 的 redirect 行为。

4. **`OssSettings.secret` 默认为空字符串** (`config.py:27`): 如果忘记设 `EIRA_OSS__SECRET` 环境变量，签名会错误。建议改进：dev 模式下从 `deploy/.env.example` 自动读取或使用更显式的配置。

---

## 6. 建议的下一步修复方向

### 方向 A: 修复 307 重定向

排查 `fetch()` 在 307 重定向时的行为：
- 是否携带了 Authorization header 到 `/oss/` URL？
- 是否可以通过 `redirect: 'manual'` 手动处理重定向，去掉 Authorization header 后重新 fetch？

### 方向 B: 放弃后端端点，前端直接处理

删除 `/admin/assets/{id}/file` 端点，让 admin 前端使用与 web-user 完全相同的流程：
1. 调用 `GET /admin/assets/{id}/download`（已存在的端点）获取 presigned URL
2. 将 `http://localhost:9000/` 替换为 `/oss/`
3. 通过 Vite proxy fetch

注意：这是 admin 最初使用的流程，当时的错误（`ERR_INVALID_HTTP_RESPONSE`、`ERR_CONTENT_LENGTH_MISMATCH`）可能与凭据问题有关，现在凭据正确后可能已修复。

### 方向 C: 修复 boto3 客户端配置

在 `_opts()` 中添加 `s3={"addressing_style": "path"}` 配置：
```python
"config": Config(
    signature_version="s3v4",
    s3={"addressing_style": "path"},
),
```

### 方向 D: MinIO 网络诊断

直接测试后端 Python 进程能否连接 MinIO：
```python
python -c "import boto3; c=boto3.client('s3', endpoint_url='http://127.0.0.1:9000', aws_access_key_id='eira', aws_secret_access_key='eira-secret', region_name='us-east-1', config=boto3.session.Config(signature_version='s3v4', s3={'addressing_style': 'path'})); print(c.list_buckets())"
```

---

## 7. 服务启动命令

```powershell
# Docker 基础设施
docker compose -f deploy/docker-compose.dev.yml up -d

# 后端
cd D:\Application\ClaudeCode\repository\Eira\backend
$env:EIRA_JWT__SECRET = "dev-secret"
$env:EIRA_OSS__SECRET = "eira-secret"
$env:EIRA_DB_DSN = "postgresql+asyncpg://eira:eira@localhost:5432/eira"
$env:EIRA_REDIS_URL = "redis://localhost:6379/0"
$env:EIRA_OSS_ENDPOINT = "http://localhost:9000"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端
pnpm --filter @eira/web-user dev      # http://localhost:5173
pnpm --filter @eira/web-admin dev     # http://localhost:5174

# 测试
cd backend
python -m pytest tests/ -v --tb=short
```

**Admin 凭据**: admin@eira.dev / admin123

---

## 8. Suggested Skills

新 agent 建议按顺序调用：

1. **`systematic-debugging`** — 优先处理 MinIO 网络连接诊断（方向 D）
2. **`brainstorming`** — 如方向 A-C 均失败，需重新设计 admin Live2D 加载架构
3. **`verification-before-completion`** — 任何修改后先验证再声称完成
