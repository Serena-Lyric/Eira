# Eira 项目 Handoff · 2026-06-14 最终

> **源会话**: 测试重组 + 6 个 bug 修复 + 满意度图表优化
> **测试基线**: 249 passed, 1 skipped, 0 errors
> **分支**: master

---

## 1. 会话摘要

本次会话从 `eira-handoff-2026-06-14-phase5-6.md` 的 5 个遗留问题出发，完成了一系列修复和优化：

- **测试重组**：目录从 unit/integration 重组织为 6 功能模块，修复 9 个失效测试，添加 session-scoped 数据清理 fixture
- **6 个 bug 修复**：Live2D 加载（user 路径错位 + admin 签名验证）、双重气泡、NaN JSON、hit test 崩溃
- **角色卡方案变更**：软删除 → 硬删除
- **满意度趋势优化**：week/month 分离数据源、Y 轴修正、hover tooltip
- **数据清理**：历史地理位置消息、知识库测试残留

---

## 2. 关键架构变更

### 2.1 测试重组

```
tests/
├── conftest.py          ← session-scoped _cleanup_test_data (autouse)
├── pytest.ini           ← asyncio_mode=auto
├── infra/       (7)     ← DB/Redis/OSS/health/config/logging/system
├── identity/    (4)     ← auth/admin_users/admin_settings/audit
├── persona/     (4)     ← personas/silly_import/assets/admin_assets
├── conversation/(5)     ← conversation/ws_chat/ws_messages/safety/orchestrator_smoke
├── knowledge/   (10)    ← documents_api/knowledge_*/chunker/parsers/retrieve_kb/embedding/search
├── voice/       (7)     ← asr/tts/voice/ws_voice/ws_voice_e2e/ws_stream_pacing/sentence_splitter
└── llm/         (2)     ← llm_provider/llm_logging
```

- validation/ 已删除（5 个旧验收测试）
- `_cleanup_test_data`：session-scoped，测试结束后清理所有 @example.com 用户及相关数据，恢复真实默认角色卡
- `_test_transaction`：实验性 per-test 事务 fixture（已禁用，与 asyncpg 冲突）
- `import_v2`：当导入数据无 system_prompt 时自动生成默认值

### 2.2 角色卡硬删除

| 文件 | 变更 |
|------|------|
| `repository.py` | `soft_delete` → `hard_delete`（DELETE FROM） |
| `service.py` | `delete_persona` 先清理 `chat_session.persona_id` 悬空引用，再硬删除 |
| `Dashboard.vue` | 移除"已禁用"状态列、Re-enable 按钮 |

### 2.3 满意度趋势 week/month

- **后端** `admin_dashboard.py`：`_generate_date_series()` + zero-filling，无数据的日期 score=0
- **前端** `useDashboard.ts`：卡片请求 `range=week`，展开请求 `range=month`（独立数据源）
- **前端** `Dashboard.vue`：Y 轴 0/25/50/75/100% 对齐，X 轴月图每 5 天显示，hover tooltip

---

## 3. 已修改文件清单

| 文件 | 变更类型 |
|------|------|
| `backend/tests/conftest.py` | 重写 — session cleanup fixture |
| `backend/tests/` (40+ 文件) | 目录重组 |
| `backend/pytest.ini` | 新建 |
| `backend/app/domain/persona/repository.py` | soft_delete → hard_delete |
| `backend/app/domain/persona/service.py` | 硬删除 + import_v2 默认 system_prompt |
| `backend/app/domain/persona/resolver.py` | 无变化（仅确认 disabled 过滤） |
| `backend/app/api/rest/admin_personas.py` | 文档字符串更新 |
| `backend/app/api/rest/admin_dashboard.py` | 满意度 zero-filling + 词云地理位置过滤 |
| `backend/app/orchestrator/nodes/persist.py` | 正则移除 [用户位置] |
| `backend/app/orchestrator/nodes/retrieve_kb.py` | NaN 守卫 |
| `backend/app/infra/alembic/versions/0012_persona_default_unique.py` | 新建 — 角色卡默认唯一索引 |
| `apps/web-admin/vite.config.ts` | /oss 代理 + changeOrigin |
| `apps/web-admin/src/services/api.ts` | assetApi.getDownloadUrl |
| `apps/web-admin/src/composables/useLive2DPreview.ts` | 两步下载 |
| `apps/web-admin/src/composables/useDashboard.ts` | week/month 分离数据源 |
| `apps/web-admin/src/pages/Dashboard.vue` | 满意度图表 Y/X 轴修正、hover tooltip、硬删除 UI |
| `apps/web-user/vite.config.ts` | /oss 代理 + changeOrigin |
| `apps/web-user/src/composables/useLive2DModelLoader.ts` | fileMap key re-base + URL 改写 |
| `apps/web-user/src/composables/useChatSession.ts` | connect() 前 disconnect() |
| `apps/web-user/src/live2d/lappmodel.ts` | hitTest null 守卫 |

---

## 4. 当前服务状态

| 服务 | 端口 | 启动命令 |
|------|:--:|------|
| PostgreSQL | 5432 | `docker compose -f deploy/docker-compose.dev.yml up -d` |
| Redis | 6379 | 同上 |
| MinIO | 9000 | 同上 |
| Backend | 8000 | `cd backend && EIRA_DB_DSN=... uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` |
| Web-admin | 5174 | `pnpm --filter @eira/web-admin dev` |
| Web-user | 5173 | `pnpm --filter @eira/web-user dev` |

**Admin 凭据**: admin@eira.dev / admin123

---

## 5. 数据库状态

| 表 | 数量 | 说明 |
|------|:--:|------|
| personas | 1 | 灵山胜境导游 (id=229, is_default=True) |
| assets (live2d) | 7 | mao_pro_zh 等 7 个模型 |
| documents | 2 | 灵山胜境文档 |
| chat_messages | — | 已清理 [用户位置] 前缀 |

---

## 6. ⚠️ 已知注意事项

1. **端口清理**：杀 uvicorn 需杀整个进程树（`taskkill /F /PID <parent> /T`），否则 `--reload` 子进程会残留
2. **_cleanup_test_data**：session-scoped，仅在 pytest 完全退出时执行。如果中途 Ctrl+C 中断，数据不会清理——需手动运行测试收尾
3. **_test_transaction**：已禁用（autouse=False），per-test 事务与 asyncpg 单连接限制冲突
4. **测试会漏数据到开发库**：_cleanup_test_data 只在整个 test session 结束后清理。在 session 内部，测试数据会短暂存在于开发库中
5. **Persona 测试数据**：`conftest.py` 的 `admin_session`/`user_session` fixture 创建的用户不会被自动清理（它们不使用 `@example.com`），需确认 _cleanup_test_data 覆盖了所有测试用户

---

## 7. Suggested Skills

新 agent 建议按顺序调用：

1. **`using-superpowers`** — 了解可用技能
2. **`systematic-debugging`** — 如有新 bug 需要排查
3. **`verification-before-completion`** — 修改后先跑测试再声称完成
4. **`brainstorming`** — 如需设计新功能或重构
