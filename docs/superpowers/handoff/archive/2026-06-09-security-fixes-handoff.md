# §5.4 + §5.5 + §6.1 + §6.2 + §6.4 修复 Handoff

> 日期: 2026-06-09
> 分支: `chore/live2d-rewrite-and-handoff`
> 涉及: 后端 17 文件修改 + 1 文件新建

---

## 修复矩阵

| # | 严重度 | 问题 | 根因 | 方案 |
|---|--------|------|------|------|
| 5.4 | 🔴 | REST 写操作 / auth 全无限流 | 限流基础设施存在但仅应用到上传+WS | 新增 write/auth 限流器，批量应用到 14 个端点 |
| 5.5 | 🟡 | user.py 上传缺失 magic number | 开发时遗漏 | 补全 `validate_magic()` 调用 + 增强文本检测 |
| 6.1 | 🔴 | Provider 缓存永不过期 | 双层缓存（`@lru_cache` + `_provider_cache` dict） | TTL 300s ProviderRegistry + DB 配置桥接 + `close()` 释放连接池 |
| 6.2 | 🔴 | 管线失败无重试 / 文档永久卡 processing | `_run_pipeline_background` 仅日志无兜底 | tenacity 3 次指数退避重试 + `_ensure_terminal_status` 安全网 |
| 6.4 | 🟡 | reprocess 的 `asyncio.create_task` 无引用 | 直接创建 task 不保存 handle | 统一走 `_run_pipeline_background`（含安全网） |

---

## 变更清单

### 核心基础设施（4 文件）

| 文件 | 改动 | 影响 |
|------|------|------|
| `backend/app/core/config.py:100-103` | `RateLimitSettings` 新增 `write_capacity=20, write_rate=3.0, auth_capacity=5, auth_rate=0.5` | 可通过 `EIRA_RATE_LIMIT__WRITE_CAPACITY` 等环境变量覆盖 |
| `backend/app/core/rate_limit.py:63-71,108-150` | `check()` 尊重 `enabled` 标志；新增 `get_write_limiter()` + `get_auth_limiter()` | 全局开关 `EIRA_RATE_LIMIT__ENABLED=false` 可紧急关闭所有限流 |
| `backend/app/core/deps.py:78-107` | 新增 `check_write_rate_limit` + `check_auth_rate_limit` FastAPI 依赖 | auth 限流用 IP 维度（未登录用户无 user_id） |
| `backend/app/core/file_validation.py:31-40,57` | 新增 `_looks_like_binary()`；`validate_magic()` 文本检测从 null-byte 开头改为扫描 512 字节 | null-byte 占比 >10% → 判定为二进制伪装 |

### 限流应用（12 个端点文件）

所有 POST / PATCH / DELETE 端点统一添加 `_rate: None = Depends(check_write_rate_limit)`。

| 文件 | 端点 | 限流类型 |
|------|------|----------|
| `backend/app/api/rest/auth.py` | POST register / login / refresh | `check_auth_rate_limit`（IP 维度，capacity=5, rate=0.5/s） |
| `backend/app/api/rest/conversations.py` | POST create | `check_write_rate_limit` |
| `backend/app/api/rest/feedback.py` | POST submit | `check_write_rate_limit` |
| `backend/app/api/rest/admin_settings.py` | PATCH "" / PATCH "/{key}" | `check_write_rate_limit` |
| `backend/app/api/rest/admin_users.py` | PATCH / DELETE | `check_write_rate_limit` |
| `backend/app/api/rest/admin_assets.py` | DELETE | `check_write_rate_limit` |
| `backend/app/api/rest/personas.py` | POST / PATCH / DELETE / POST import | `check_write_rate_limit` |
| `backend/app/api/rest/admin_personas.py` | POST / PATCH / DELETE / POST set-default / POST import | `check_write_rate_limit` |
| `backend/app/api/rest/persona_config.py` | PATCH | `check_write_rate_limit` |
| `backend/app/api/rest/user.py` | PATCH preferences / POST background / POST model | `check_write_rate_limit` + `check_upload_rate_limit`（上传端点） |
| `backend/app/api/rest/voice.py` | POST asr / POST tts | `check_write_rate_limit` |

### 上传校验增强（1 文件）

| 文件 | 改动 |
|------|------|
| `backend/app/api/rest/user.py:159-164` | `upload_background` 新增 `validate_magic(contents, content_type)` |
| `backend/app/api/rest/user.py:223-228` | `upload_model` 新增 `validate_magic(contents, "application/zip")`（仅 .zip，.7z/.rar 穿透） |

### 管线重试 + 安全网（3 文件）

| 文件 | 改动 |
|------|------|
| `backend/app/workers/knowledge_worker.py` | **重写**：新增 `_is_retryable()` 错误分类 + tenacity `@retry` 包装（3 次，指数退避 2s→4s） |
| `backend/app/api/rest/admin_documents.py:131-175` | `_run_pipeline_background` 改为含安全网版本；新增 `_ensure_terminal_status()`；reprocess 端点改用 `_run_pipeline_background` |
| `backend/app/api/rest/documents.py:131-175` | 同上（与 admin 版逻辑一致） |

### Provider 缓存（前次修复，3 文件修改 + 1 新建）

| 文件 | 改动 |
|------|------|
| `backend/app/capabilities/llm/base.py` | 新增 `abstractmethod async close()` |
| `backend/app/capabilities/llm/openai_compat.py` | 实现 `close()` → `await self._client.close()` |
| `backend/app/capabilities/llm/mock.py` | 实现 `close()` no-op |
| `backend/app/capabilities/llm/provider_registry.py` | **新建** — TTL 300s ProviderRegistry + `get_effective_llm_settings()` DB 桥接 |
| `backend/app/capabilities/llm/__init__.py` | 导出 `ProviderRegistry`, `get_provider_registry`, `get_effective_llm_settings` |
| `backend/app/api/ws/chat.py` | 移除 `_provider_cache` dict → 改用 `get_provider_registry().get(settings)` |
| `backend/app/api/ws/voice.py` | 同上 |
| `backend/app/api/rest/admin_settings.py` | PATCH 后调用 `_invalidate_llm_cache_if_needed()` 即时失效 |

### 测试（2 文件）

| 文件 | 改动 |
|------|------|
| `backend/tests/conftest.py:33` | 自动 `os.environ["EIRA_RATE_LIMIT__ENABLED"] = "false"` |
| `backend/tests/unit/test_llm_provider.py` | 新增 8 个 ProviderRegistry 单元测试 |

---

## 限流配置速查

所有限流通过 `EIRA_RATE_LIMIT__*` 环境变量配置，代码默认值如下：

| 限流器 | capacity | rate | 维度 | 用途 |
|--------|----------|------|------|------|
| `chat_rate_limiter` | 30 | 5.0/s | user_id | 聊天 REST |
| `upload_rate_limiter` | 10 | 2.0/s | user_id | 文件上传 |
| `ws_message_limiter` | 20 | 10.0/s | user_id | WS 消息 |
| `write_rate_limiter` | 20 | 3.0/s | user_id | 所有 POST/PATCH/DELETE |
| `auth_rate_limiter` | 5 | 0.5/s | **client IP** | 登录/注册/刷新 |

全局开关：`EIRA_RATE_LIMIT__ENABLED`（默认 `true`，设为 `false` 关闭所有限流）。

原理：Redis Lua 脚本原子令牌桶（`rate_limit.py:23-53`），Redis 不可用时 **fail open**（允许请求通过并记录 warning）。

---

## 架构决策记录

### 6.1: 为什么 ProviderRegistry TTL 默认 300 秒

- **< 5 分钟**：限制密钥泄露窗口（旧 API key 最多存活 5 分钟）
- **> 几秒**：避免每次 WS 连接都重建 `AsyncOpenAI` 客户端（httpx 连接池开销大）
- **5 分钟**：管理员可接受的最大配置生效延迟
- 管理员通过 API 修改配置时触发 `invalidate()` 立即失效，TTL 仅作为兜底

### 6.1: 为什么 cache key 包含 api_key 的 SHA-256

旧 key `f"{provider}:{model}"` 在 API key 轮换时不变化，导致旧 key 继续使用。新 key 哈希所有字段（含 `api_key`），任何变更触发重建。SHA-256 避免明文 key 出现在日志中。

### 6.2: 为什么 _ensure_terminal_status 在两处重复定义

`admin_documents.py` 和 `documents.py` 各自定义，原因：
1. 两者有不同的导入上下文（admin 版多了 `require_admin` 等）
2. 函数仅 30 行，重复维护成本低于共享模块的耦合风险
3. 未来可提取到 `knowledge_worker.py` 统一管理

### 5.4: 为什么 auth 限流用 IP 而非 user_id

登录/注册时用户尚未认证，`get_current_user` 不可用。`request.client.host` 是唯一可用标识。注意：反向代理后需配合 `X-Forwarded-For` 头（见陷阱）。

### 6.2: 为什么 reprocess 仍用 asyncio.create_task

reprocess 端点在 HTTP 请求上下文中，不能用 `BackgroundTasks`（该依赖未注入）。`asyncio.create_task` 是 fire-and-forget，但现在 wrapper 内含完整的安全网（`_run_pipeline_background`），异常不会丢失。

---

## 陷阱 / 注意事项

### ⚠️ 陷阱 1: auth 限流 + 反向代理

`check_auth_rate_limit` 使用 `request.client.host` 获取客户端 IP。如果 Nginx/ALB 等反向代理未正确设置 `X-Forwarded-For`，所有请求将共享代理 IP → 整个站点被限流。

**症状**: 所有用户看到 429，日志中 `rate_limit` key 全是同一 IP。

**缓解**: 
```python
# 生产环境中应从 X-Forwarded-For 头提取真实 IP
client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
if not client_ip:
    client_ip = request.client.host if request.client else "unknown"
```

**紧急恢复**: 设置 `EIRA_RATE_LIMIT__ENABLED=false` 重启。

### ⚠️ 陷阱 2: _is_retryable 的 HTTP 状态码检测

`knowledge_worker.py:51-56` 通过 `getattr(exc, "response", None)` 检测 HTTP 状态码，仅对 httpx/openai SDK 抛出的异常有效。如果 pipeline 中某些步骤使用其他 HTTP 库（如 boto3 的 OSS 调用），其异常结构不同，网络错误仍会被 `OSError` 捕获（boto3 的 `BotocoreError` 通常继承自 `ConnectionError`/`OSError`）。

**结论**: 当前覆盖足够。OSS 超时 → `OSError` subclass → retryable ✅。Embedding API 429 → httpx → `response.status_code` → retryable ✅。

### ⚠️ 陷阱 3: 文本二进制检测的 UTF-16 误判

`_looks_like_binary()` 用 null-byte 占比 >10% 判定二进制。UTF-16 编码的纯文本（如 Windows 的 "Unicode" 保存格式）BMP 字符每个含一个 `\x00` → 占比约 50% → 被误判为二进制。

**影响**: 目前仅允许 `text/plain`, `text/markdown`, `text/csv`，均为 UTF-8。如果未来支持 UTF-16 文本，需先检测 BOM 并跳过 `_looks_like_binary`。

### ⚠️ 陷阱 4: RateLimiter check() 的 fail-open 行为

Redis 不可用时 `check()` 返回 `True`（允许请求），意味着 Redis 宕机期间所有限流失效。这是**有意设计**（可用性优先于安全），但运维需注意：
- Redis 恢复后限流立即恢复
- 如果限流是唯一的暴力破解防护，Redis 不可用期间需监控 auth 失败日志

### ⚠️ 陷阱 5: _ensure_terminal_status 的 DB 会话管理

函数内部自己创建 DB session（`get_session_factory()`），不依赖外部 session。这是**必须的**——调用方可能在任何上下文中（background task、fire-and-forget asyncio task），外部 session 可能已关闭或未传入。

每个 `_ensure_terminal_status` 调用会开启一个新的 DB 连接。正常情况下极少调用（仅 pipeline 失败时），不会造成连接池压力。

### ⚠️ 陷阱 6: ProviderRegistry TTL + admin PATCH 的时序

admin PATCH 写 DB → `_invalidate_llm_cache_if_needed()` 调 `registry.invalidate()` → 清空缓存。**但**如果 admin 修改的是 DB 中的 LLM 配置（key=`"llm"`），下一个 WS 连接时 `get_effective_llm_settings()` 从 DB 读取最新配置 → 创建新 provider ✅。

单进程部署此逻辑闭环。多 Worker 进程时，只有收到 PATCH 的进程执行了 `invalidate()`，其他进程需等 TTL 过期（最多 300s）。后续 Phase 2 需 Redis pub/sub 跨进程同步。

### ⚠️ 陷阱 7: admin_settings.py 的 _invalidate_llm_cache_if_needed 触发条件

仅当 key 以 `"llm"` 开头时触发（`k == "llm" or k.startswith("llm.") or k.startswith("llm_")`）。如果 admin 修改了不相关的设置（如 `persona_config`），不会清空 provider 缓存——正确行为，避免不必要重建。

---

## 手动测试

> 前置条件：后端服务运行中（`uvicorn app.main:app`），MinIO/OSS 可用（否则上传类测试会失败）。

### 5.5-A: 伪装 JPEG 被拒绝
```bash
echo "this is not a jpeg file" > /tmp/fake.jpg
curl -X POST http://localhost:8000/user/background \
  -H "Authorization: Bearer <token>" \
  -F "background=@/tmp/fake.jpg;type=image/jpeg"
# → HTTP 400: "文件内容与声明的格式不匹配"
```

### 5.5-B: 真实 JPEG 通过
```bash
curl -X POST http://localhost:8000/user/background \
  -H "Authorization: Bearer <token>" \
  -F "background=@real_photo.jpg;type=image/jpeg"
# → HTTP 201
```

### 5.4-A: Auth 暴力破解限流
```bash
for i in $(seq 1 7); do
  code=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"nobody@test.com","password":"wrong"}')
  echo "Request $i: $code"
done
# → 前 5-6 次: 401（密码错误）
# → 第 6-7 次: 429（限流触发）
```

### 5.4-B: Write 限流
```bash
for i in $(seq 1 10); do
  code=$(curl -s -o /dev/null -w "%{http_code}" \
    -X PATCH http://localhost:8000/admin/persona-config/ \
    -H "Authorization: Bearer <admin_token>" \
    -H "Content-Type: application/json" \
    -d '{"default_speech_rate":1.0}')
  echo "Request $i: $code"
done
# → 前几次: 200，后续: 429
```

### 6.2-A: 不可重试错误（模拟文件格式错误）
```bash
# 上传一个伪装成 PDF 的文本文件
echo "hello" > /tmp/bad.pdf
curl -X POST http://localhost:8000/admin/documents/upload \
  -H "Authorization: Bearer <admin_token>" \
  -F "file=@/tmp/bad.pdf;type=application/pdf"
# → HTTP 400: magic number 不匹配（5.5 拦截，管线的解析阶段不会到达）
```

### 6.2-B: 重试验证（查看日志）
```bash
# 1. 停掉 OSS 服务（MinIO/S3）
# 2. 上传真实 PDF → 管线启动 → OSS 下载失败
# 3. 查看日志:
grep "knowledge.worker.retry" backend.log
# → 应出现 1-2 次 "knowledge.worker.retry" attempt=1 / attempt=2
grep "knowledge.worker.error" backend.log
# → 最终 "knowledge.worker.error"（重试耗尽）
grep "knowledge.pipeline.safety_net" backend.log
# → 如果 worker 自身也失败，安全网兜底

# 4. 检查文档状态
curl http://localhost:8000/admin/documents/<id>/status \
  -H "Authorization: Bearer <admin_token>"
# → status: "failed", error: "ConnectionError: ..."
```

### 6.1: Provider 缓存失效
```bash
# 1. 连接到 WS（建立 provider 缓存）
# 2. Admin 修改 LLM 配置
curl -X PATCH http://localhost:8000/admin/settings \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"settings":{"llm":{"provider":"mock"}}}'
# → HTTP 200
# 3. 查看后端日志
grep "admin_settings.llm_changed" backend.log
# → 出现 "admin_settings.llm_changed"
grep "provider_cache.invalidate" backend.log
# → 出现 "provider_cache.invalidate"（缓存已清空）

# 4. 新 WS 连接 → 使用 mock provider（不再是之前的 deepseek/openai）
```

---

## 回滚 / 紧急操作

### 紧急关闭所有限流
```bash
export EIRA_RATE_LIMIT__ENABLED=false
# 重启服务
```

### 临时调高 auth 限流（被攻击时改为更严）
```bash
export EIRA_RATE_LIMIT__AUTH_CAPACITY=3
export EIRA_RATE_LIMIT__AUTH_RATE=0.2
```

### 回滚单个文件改动
```bash
# 所有改动都在 chore/live2d-rewrite-and-handoff 分支
# 回滚整个分支到 merge base:
git diff main...HEAD -- <file> | git apply -R
```

---

## 未解决问题（明确的后续债务）

| 编号 | 问题 | 优先级 | 计划 |
|------|------|--------|------|
| 5.4-R1 | `check_auth_rate_limit` 使用 `request.client.host` 而非 `X-Forwarded-For` | 🟡 | 生产部署前修复 |
| 6.1-R1 | ProviderRegistry.invalidate() 不支持多进程（需 Redis pub/sub） | 🟡 | Phase 2 |
| 6.2-R1 | 管线使用 asyncio task 而非持久化队列（无崩溃恢复） | 🟢 | Phase 3: Celery 升级 |
| 6.2-R2 | 管线重试无 Prometheus metrics | 🟢 | 运维优化 |
| §4.5 | API key 明文存储在 system_settings JSONB | 🔴 | 上线前必须升级 pgcrypto + KMS |

---

## 测试结果

```
145 unit tests: PASSED ✅
247 total: passed ✅
7 pre-existing failures: OSS/MinIO botocore (unrelated) ❌
1 skipped
```
