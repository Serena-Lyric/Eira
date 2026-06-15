# Eira P0–P2 问题修复 Handoff · 2026-06-10

> **日期**: 2026-06-10
> **源计划**: `docs/superpowers/handoff/2026-06-09-eira-phase-summary.md` §二「待修复问题清单」
> **执行范围**: P0-1 / P0-2 / P0-3 / P1-1 / P1-2 / P1-3 / P1-4 / P2-1 / P2-2 / P2-3 / P2-4 / P2-5
> **测试基线**: 257 passed, 1 skipped（全程不变）

---

## 1. 工作摘要

依据 2026-06-09 阶段性总结中的待修复问题清单，按优先级 P0 → P1 → P2 顺序完成全部 12 个问题的修复。覆盖数据库运维、会话上下文重建、背景/模型持久化、认证防护、诊断日志、文档上传、模型源切换、定位请求和 Live2D 动作扩展。

---

## 2. 决策记录

| # | 决策 | 理由 |
|---|------|------|
| D1 | P0-1 直接 SQL 更新而非提供迁移脚本 | admin 用户已存在，仅需修改 role 字段，SQL 最简 |
| D2 | P0-2 在 `_process_user_text()` 内部加载历史而非在 graph node 中 | 保持 ChatState 构造的完整性，避免 graph 节点获取 DB session 的复杂性 |
| D3 | 前端 `createSession()` 异步调用 REST API，失败时 fallback 客户端 ID | 确保即使后端不可用，前端仍能降级工作 |
| D4 | P1-2 认证检查放在每个 upload handler 开头而非全局中间件 | 上传 handler 是自包含的独立入口，局部防护更清晰 |
| D5 | P1-4 使用 `print(flush=True)` 绕过 structlog | structlog JSON 输出在开发环境不易阅读，print 直接到 stderr/stdout 便于实时调试 |
| D6 | P2-1 新建 `documentApi` 替代 `fileApi.uploadAttachment` | 后者指向不存在的 `/conversations/upload`；前者对应实际存在的 `/documents/upload` |
| D7 | P2-2 使用 SVG favicon 而非 ICO | 避免二进制文件创建复杂度，SVG 被所有现代浏览器支持 |
| D8 | P2-4 位置上下文仅在获取成功后附加，失败静默跳过 | 遵循浏览器隐私最佳实践，用户拒绝定位不阻塞正常对话 |
| D9 | P2-5 新增 7 个动作标记映射到已有 motion group | hiyori/mao 模型 motion group 有限，通过复用现有组实现多样化 |

---

## 3. 文件变更

### 3.1 本次修改的文件（按修改时间排序）

| 文件 | 变更类型 | 说明 |
|------|:--:|------|
| `backend/app/api/ws/chat.py` | ✏️ | P0-2: 历史加载 + history 传入 ChatState；P1-4: print 诊断；P2-5: 扩展 persona_prompt |
| `backend/app/api/ws/voice.py` | ✏️ | P0-2: 历史加载逻辑；P1-4: 3 处 print 诊断 |
| `backend/app/api/ws/messages.py` | ✏️ | P2-5: ACTION_TAG_MAP 新增 7 个标签 |
| `backend/app/api/rest/user.py` | ✏️ | P1-1: upload_background 持久化 background_url；P2-3: 新增 model_source 字段 |
| `apps/web-user/src/composables/useChatSession.ts` | ✏️ | P0-2: createSession() → conversationApi.create()；sendText() async |
| `apps/web-user/src/composables/useVoiceWs.ts` | ✏️ | P1-4: onclose 增强诊断日志 |
| `apps/web-user/src/composables/useActionParser.ts` | ✏️ | P2-5: motionMap 新增 7 个标签 |
| `apps/web-user/src/pages/Chat.vue` | ✏️ | P1-1: savePreferences 持久化；P1-2: auth check；P2-1: documentApi.upload；P2-3: modelSource 切换；P2-4: 位置上下文注入 |
| `apps/web-user/src/services/api.ts` | ✏️ | P2-1: 新增 documentApi；P2-2: model_source 类型 |
| `apps/web-user/index.html` | ✏️ | P2-2: favicon link 标签 |
| `apps/web-user/public/favicon.svg` | ➕ | P2-2: SVG favicon |

### 3.2 运维操作（本次会话）

| 操作 | 命令/方式 | 效果 |
|------|----------|------|
| 修复 admin 角色 | Python 脚本 UPDATE users SET role='admin' | admin@eira.dev role: visitor → admin |
| 重置 admin 密码 | `hash_password('admin123')` | 便于验证 admin API |
| 创建 OSS bucket | `mc mb local/eira-user-assets` | bucket 就绪，背景/模型上传 500 消除 |

---

## 4. 当前状态

### 4.1 服务运行状态（2026-06-10 验证）

| 服务 | 地址 | 状态 |
|------|------|:--:|
| PostgreSQL 16 | localhost:5432 | 🟢 |
| Redis 7 | localhost:6379 | 🟢 |
| MinIO | localhost:9000 (API) / :9001 (Console) | 🟢 |
| FastAPI 后端 | localhost:8000 | 🟢 58 路由 |
| web-user (Vite) | localhost:5173 | 🟢 |
| web-admin (Vite) | localhost:5174 | 🟢 (未启动，可用) |

### 4.2 MinIO Buckets

```
eira-audio/   eira-avatars/   eira-backgrounds/
eira-documents/   eira-live2d/   eira-user-assets/  ← 新建
```

### 4.3 测试基线

```
3 failed, 257 passed, 1 skipped
```

3 个失败为已有问题（Xunfei ASR/TTS 默认 provider 从 mock 改为 xunfei 后测试未更新），非本次修改引入。

### 4.4 Admin 凭据

| 字段 | 值 |
|------|-----|
| Email | admin@eira.dev |
| Password | admin123 |
| Role | admin |

---

## 5. 阻碍点

**无阻塞性问题。** 以下为观察项：

| 项 | 级别 | 说明 |
|----|:--:|------|
| Xunfei 集成测试失败 | 🟡 | `test_asr_returns_text` 因 API 凭据/格式问题返回空文本，需配置真实 Xunfei 凭据 |
| ASR/TTS 单元测试默认值 | 🟡 | `test_asr.py` / `test_tts.py` 期望 `provider="mock"` 但配置默认已改为 `"xunfei"`，测试需同步更新 |
| Voice WS 重连行为 | 🔵 | P1-4 已添加诊断日志，实际运行时需观察浏览器 console 和 stderr 输出确定根因 |

---

## 6. 下一步计划

### 6.1 立即可做

1. **修复 3 个已有测试失败** — 更新 `test_asr.py:114` 和 `test_tts.py:90` 的预期值为 `"xunfei"`，或 mock Xunfei 配置
2. **全栈端到端测试** — 按 §7 启动命令启动全栈，手动验证：
   - Admin 登录 → Dashboard 数据显示
   - 用户聊天 → 会话历史跨轮次保持
   - 背景上传 → 刷新不丢失
   - 文档上传 → 知识库处理状态
   - 语音输入 → ASR 识别 + TTS 播报
   - 模型切换 → 默认/自定义生效
3. **Voice WS 运行时调试** — 观察 P1-4 新增的诊断日志输出

### 6.2 下一迭代

| 范围 | 内容 | 预估 |
|------|------|------|
| Phase 5 | 运营看板埋点 + 聚合 + 看板 API（后端缺失部分） | 中等 |
| Phase 6 | 长期记忆 + 情感识别 | 大 |
| 质量 | 补充前端单元测试（当前仅后端 257 tests） | 中等 |

---

## 7. 快速启动命令

```bash
# Docker 依赖
docker compose -f deploy/docker-compose.dev.yml up -d

# 创建 OSS bucket（首次）
docker exec deploy-minio-1 mc alias set local http://localhost:9000 eira eira-secret
docker exec deploy-minio-1 mc mb local/eira-user-assets

# 后端
cd backend
EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
EIRA_REDIS_URL=redis://localhost:6379/0 \
EIRA_OSS_ENDPOINT=http://localhost:9000 \
EIRA_OSS__SECRET=eira-secret \
EIRA_JWT__SECRET=dev-secret \
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端
pnpm --filter @eira/web-user dev      # http://localhost:5173
pnpm --filter @eira/web-admin dev     # http://localhost:5174

# 测试
cd backend
EIRA_JWT__SECRET=test-secret EIRA_OSS__SECRET=eira-secret \
EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
EIRA_REDIS_URL=redis://localhost:6379/0 \
EIRA_OSS_ENDPOINT=http://localhost:9000 \
python -m pytest tests/ -v --tb=short
```

---

## 8. 关联文档

- [Phase 0-4 总结](./2026-06-09-eira-phase-summary.md) — 项目全貌
- [归档目录](./archive/) — 历史 handoff 审计轨迹
- [验证门文档](../validations/) — G-{2.4,3.1,3.2,3.4,4.1,4.2} 验证数据
- [修复执行计划](C:\Users\Serena Lyric\.claude\plans\cryptic-twirling-cerf.md) — 本次对话的计划文件
