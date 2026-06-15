# Eira 项目 Handoff · 2026-06-14

> **源会话**: 全量 API 审查 + P0-P2 修复 + Admin 开关审计 + 存疑项决议
> **测试基线**: 260 passed, 1 skipped, 0 failed
> **分支**: master

---

## 1. 会话摘要

本次会话完成了对 Eira 项目（FastAPI 后端 + web-user + web-admin）的全量审查与修复，共四轮：

| 轮次 | 内容 | 成果 |
|------|------|:--:|
| 第一轮 | 全量 API 审计（18 REST + 5 WS + 前端两套） | 发现 20 待修复 + 5 存疑 + 7 正常 |
| 第二轮 | P0-P1 修复 + 存疑决议 | 修复 14 项，存疑 5/5 决议 |
| 第三轮 | 上传/Ux/角色卡修复 | MIME 标准化、set-default、CSS 溢出、v-show |
| 第四轮 | Admin 开关全面审计 | 发现 11/11 API 配置无效，修复 LLM 路径 + Dashboard |

---

## 2. 已修复问题清单

### 后端 (10 文件)

| 文件 | 修复内容 |
|------|---------|
| `backend/app/api/rest/assets.py` | C1 OSS_BUCKET NameError；Q2 admin 权限分离；normalize_mime |
| `backend/app/api/rest/admin_assets.py` | C3 POST 上传端点 + set-default 支持两种类型 + is_default 列 + 清理端点 |
| `backend/app/api/ws/chat.py` | H1 加载真实 User；H4 DoneOut 使用持久化 message_id |
| `backend/app/api/ws/voice.py` | H2 voice.start 创建真实 DB session |
| `backend/app/orchestrator/nodes/persist.py` | H4 从空壳改为真实 DB 写入 |
| `backend/app/api/rest/persona_config.py` | M1 require_admin + default_background_oss_key/url |
| `backend/app/api/rest/user.py` | H3 存储 OSS key；get_preferences persona_config fallback；normalize_mime |
| `backend/app/core/file_validation.py` | normalize_mime() + WebP 精确校验 |
| `backend/app/capabilities/llm/provider_registry.py` | 兼容 admin 面板扁平 key |
| `backend/app/domain/knowledge/schemas.py` | DocumentOut 增加 progress 字段 |

### 前端 (4 文件)

| 文件 | 修复内容 |
|------|---------|
| `apps/web-admin/src/services/api.ts` | C3 端点路径修正；personaApi.list 返回 data.items；去掉 ?? 防御代码 |
| `apps/web-admin/src/services/types.ts` | KnowledgeDocument 对齐 DocumentOut；PersonaConfig 增加字段 |
| `apps/web-admin/src/pages/Dashboard.vue` | CSS 溢出 + v-if→v-show + handleBgUpload 接入 API + bgUrl 更新 + 日期动态化 + 死按钮标记 + 错误信息 |
| `apps/web-user/src/composables/useChatSession.ts` | 复用最近会话 + 加载历史消息 |
| `apps/web-user/src/services/api.ts` | 删除 fileApi 死代码 |
| `apps/web-user/src/pages/Chat.vue` | 蓝色占位背景 #0078D7 |
| `apps/web-user/src/assets/bg-default.jpg` | 已删除 |

---

## 3. 当前已知待处理问题

### 高优先级
| # | 问题 | 位置 |
|---|------|------|
| 1 | TTS/ASR/Embedding/Search factory 仅读 env var，不读 DB（API 配置页面下拉无效） | `backend/app/capabilities/{tts,asr,embedding,search}/factory.py` |
| 2 | Set Default for Live2D 模型的 active_model_id 可能不匹配前端硬编码 MODEL_REGISTRY | `backend/app/api/rest/admin_assets.py` + `useLive2DPreview.ts` |
| 3 | C2 硬编码 API 密钥需要轮换（用户暂时搁置） | `backend/app/core/config.py` |

### 中优先级
| # | 问题 | 位置 |
|---|------|------|
| 4 | Dashboard 用户名硬编码 '管理员' (L3) | Dashboard.vue:747 |
| 5 | 离线待机动作仅保存不驱动 Live2D | Dashboard.vue:127-131 |
| 6 | savePersonaConfig 现在输出 console.error 但用户不可见 | Dashboard.vue:152 |
| 7 | API Key Status 显示假数据（无后端验证） | useAppConfig.ts + admin_settings.py |
| 8 | voice_persistence / user_doc_quota 死 key | System Settings 页面 |

### 低优先级 / 技术债务
| # | 问题 |
|---|------|
| 9 | L1 代码重复（documents.py 和 admin_documents.py 的 pipeline 函数） |
| 10 | L5 web-user 7 个废弃组件未删除 |
| 11 | L6 Voice WS URL 字符串替换推导 |
| 12 | L7/L8 Live2D MODEL_REGISTRY / motionMap 硬编码 |
| 13 | L9 UserPreferences 枚举校验 |
| 14 | Dashboard 指标/热问/趋势/词云/情感全部 mock 数据（Phase 5） |

---

## 4. 关键架构决策

### 背景系统：全局默认 + 用户覆盖
```
优先级: 用户自定义 > Admin 全局默认 (persona_config.default_background_oss_key) > CSS 蓝色 #0078D7
```
- Admin 通过 `POST /admin/assets/backgrounds` → `POST /admin/assets/{id}/set-default` 设置
- web-user 通过 `GET /user/preferences` 自动回退

### Admin 面板视图切换：v-show 非 v-if
6 个主视图全部使用 `v-show`，DOM 持久保留，Live2D canvas 不再销毁重建。

### LLM 配置读取：嵌套 + 扁平 key 双兼容
`get_effective_llm_settings()` 先查 key `"llm"`（嵌套 dict），再查扁平 key（`llm_provider` 等）。

---

## 5. 服务启动

```bash
# Docker 基础设施
docker compose -f deploy/docker-compose.dev.yml up -d

# 后端 (port 8000)
cd backend
EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
EIRA_REDIS_URL=redis://localhost:6379/0 \
EIRA_OSS_ENDPOINT=http://localhost:9000 \
EIRA_OSS__SECRET=eira-secret \
EIRA_JWT__SECRET=dev-secret \
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端
pnpm --filter @eira/web-user dev      # port 5173
pnpm --filter @eira/web-admin dev     # port 5174

# 测试
cd backend
EIRA_JWT__SECRET=test-secret EIRA_OSS__SECRET=eira-secret \
EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
EIRA_REDIS_URL=redis://localhost:6379/0 \
EIRA_OSS_ENDPOINT=http://localhost:9000 \
python -m pytest tests/ -v --tb=short
```

### Admin 凭据
- Email: admin@eira.dev
- Password: admin123

---

## 6. 计划文件

完整审查报告和修复计划：`docs/superpowers/specs/../plans/api-mock-api-mighty-pond.md`（项目内）
实际路径：`C:\Users\Serena Lyric\.claude\plans\api-mock-api-mighty-pond.md`

---

## 7. Suggested Skills

新 agent 建议按顺序调用以下 skill：

1. **`using-superpowers`** — 了解可用技能
2. **`systematic-debugging`** — 处理任何 bug 报告前
3. **`verification-before-completion`** — 修改后先跑测试再声称完成
4. **`requesting-code-review`** — 完成重大修改后审查
5. **`brainstorming`** — 新增功能前先确认设计
