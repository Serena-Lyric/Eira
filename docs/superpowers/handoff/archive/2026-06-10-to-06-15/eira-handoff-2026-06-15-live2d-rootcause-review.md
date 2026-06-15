# Eira Handoff · 2026-06-15 · Live2D 加载问题系统性根因审查

> **源会话**: 接续 `eira-handoff-2026-06-15-live2d-admin-fix.md`（7 轮尝试未解决）的系统性审查
> **状态**: 🔬 诊断完成（三个独立根因全部实证定位）· ⏳ 修复待实施
> **分支**: master
> **前序文档**: docs/superpowers/handoff/eira-handoff-2026-06-15-live2d-admin-fix.md（同日，记录 web-user 修复 + admin 7 轮尝试 + 方向 A/B/C/D）

---

## 0. TL;DR

实机仍两端加载不出模型。系统性审查（探针 + DB 实查 + 干净后端 curl 复现）发现这**不是一个问题，而是三个独立问题**，前序 7 轮尝试只在 P3 的表象上打转，从未触及 P1/P2：

| # | 端 | 根因 | 实证手段 |
|:-:|----|------|---------|
| **P1** | web-user | DB 里 `active_model_id` 被前端写成**虚拟前缀** `eira-model://mao_pro_zh/runtime/`，当 oss_key 传给后端 → boto3 查无此 key → 502 | DB 实查 user 69 |
| **P2** | web-admin | `AdminAssetOut` schema **缺 `oss_key` 字段**，前端 `a.oss_key`=undefined → `changeModel` 匹配失败 → `Unknown model` | 读 admin_assets.py:36-44 |
| **P3** | 运维 | 用户 cmd 后端报 `SignatureDoesNotMatch`，但干净重启后端并发请求**全 200**。是**残留旧进程 / 旧前端构建 / 浏览器旧缓存** | 探针 + 干净后端复现 |

**核心纠偏**：前序文档"方向 A/C/D"都假设 boto3 或 MinIO 网络有问题。**实测证明 boto3 直读完全正常**（128/133/134 并发全成功）。真正没修的是 P1（前端逻辑）和 P2（schema），与 OSS 签名毫无关系。

---

## 1. P1 — web-user：active_model_id 被污染成虚拟前缀

**现象**（用户 cmd + console）：
```
GET /user/model/file?oss_key=eira-model%3A%2F%2Fmao_pro_zh%2Fruntime%2F  → 502
[Live2D] Model load failed: 下载模型失败: HTTP 502
```

**DB 实证**（`user_preferences`，user_id=69，updated_at=2026-06-14 23:59:29）：
```json
"active_model_id": "eira-model://mao_pro_zh/runtime/"
                    ↑ 应为 "live2d/8767b36fcc6c/mao_pro_zh.zip"
```

**根因链**：
1. `useLive2DController.ts:278` — 加载成功后 `activeModelId.value = baseUrl`，`baseUrl` 是共享 loader 的 **virtualBase**（`eira-model://...`），非 OSS key。
2. `Chat.vue:159` — debounced PATCH 把 `active_model_id: activeModelId.value` 写进 DB。
3. 重进页面 `resolveModelId()` 读回脏值 → `loadModel(key)` 请求 `/user/model/file?oss_key=eira-model://...`。
4. 后端 `user.py` fallback 判断 `"/" not in current_model` —— `eira-model://...` **含 `/`**，躲过 fallback，被当合法 key。
5. boto3 `get_object(bucket="eira-live2d", key="eira-model://...")` 查无此 key → 502。

**设计层缺陷**：`activeModelId`（virtualBase，用于 `restoreView` 缓存键）与 `active_model_id`（OSS key，用于下载）**语义被混用为同一个值**。

---

## 2. P2 — web-admin：列表 API 不返回 oss_key

**现象**：
```
[Live2D Admin] Unknown model: live2d/8767b36fcc6c/mao_pro_zh.zip
```

**根因**（`backend/app/api/rest/admin_assets.py`）：
- `AdminAssetOut`（line 36-44）字段无 `oss_key`。
- list SQL（line 131）查了 `oss_key`（r[7]）但仅用于算 `is_default`，未放入返回对象。
- 前端 `useLive2DPreview.ts:148` `ossKey: a.oss_key || ''` → 恒为 `''`。
- `changeModel`（line 455-460）四向匹配中 `m.ossKey === modelId` 恒 false。persona 默认用 `active_model_id="live2d/.../mao_pro_zh.zip"` 切换时匹配不到 → `Unknown model`。

---

## 3. P3 — 残留进程 / 旧构建（非代码问题）

**现象**：用户 cmd 后端对 asset 133(`haru.zip`)/134(`MaidCyrene...zip`) 报 `SignatureDoesNotMatch`，但 128(`mao_pro_zh.zip`) 成功。

**实证排除代码问题**：
- **探针**：全新 boto3 client，对 128/133/134，auto/path 寻址，单测 + 4 线程并发 ×3 轮 → **全部成功**（virtual 寻址因 `eira-live2d.localhost` DNS 失败，与签名无关）。
- **干净后端复现**：杀净 8000 端口后重启，并发 curl `128/133/134/129` 的 `/admin/assets/{id}/file` → **全部 HTTP 200**，零 SignatureDoesNotMatch。

**判定为残留进程的依据**：
- 用户日志时间戳 `2026-06-14T23:59:42`，今天是 **2026-06-15** → 旧进程。
- user 请求携带 `eira-model://...`（P1 脏数据），说明前端是旧构建 / DB 未清。
- 与 phase5-6 handoff §5.1"4 个残留 PID 杀不掉、旧代码仍处理请求"完全吻合。

---

## 4. 本会话已落地的后端改动（未 commit · 方向正确但只解决基础设施层）

接续前序"方向 C：回归 boto3 直读"，本会话已实现并 curl 实测可用：

| 文件 | 改动 |
|------|------|
| `backend/app/infra/oss.py` | 新增 `get_object_bytes(bucket, key) -> (bytes, content_type)` |
| `backend/app/api/rest/admin_assets.py` | `/{asset_id}/file` 删 307 重定向 → boto3 直读 + `Response` |
| `backend/app/api/rest/user.py` | 新增 `GET /user/model/file?oss_key=` boto3 直读 |
| `apps/web-user/.../useLive2DModelLoader.ts` | 改打 `/api/user/model/file` + Authorization header |

**实测**（干净后端 + curl）：两端端点 401 鉴权正确、授权后 200 + 合法 zip（magic `PK\x03\x04`；128=77.5MB / 133=15.7MB / 134=36.6MB）。**端点本身已就绪**——但 P1/P2 未修，实机仍失败。

---

## 5. 待实施修复

### P1（web-user）— 分离 virtualBase 与 oss_key
- `useLive2DModelLoader` 暴露当前加载的**真实 oss_key**（resolveModelId 的返回值），存独立 state。
- `useLive2DController.ts:278` 勿将 `baseUrl` 赋给 `activeModelId`；持久化用真实 oss_key。`restoreView`/缓存键可继续用 baseUrl，但**禁止进 PATCH**。
- `Chat.vue:159` PATCH 的 `active_model_id` 必须是真实 oss_key 或 `undefined`（让后端走 persona 默认）。
- **后端兜底**：`user.py` fallback 从 `"/" not in current_model` 改为更严格判定，如 `current_model.startswith("eira-model://")` 或不以 `live2d/` 开头即回退默认。
- **清脏数据**：`UPDATE user_preferences` 把 user 69 的 `eira-model://...` 改回 `live2d/8767b36fcc6c/mao_pro_zh.zip`（或删该键走默认）。

### P2（web-admin）— 列表返回 oss_key
- `AdminAssetOut` 加 `oss_key: str | None = None`。
- items 构造（line 158）加 `oss_key=r[7]`。

### P3（运维）— 干净重启四件套
1. 杀净 8000 端口全部进程（`taskkill /F /PID <parent> /T`，注意 `--reload` 父子进程）。
2. 两端前端重新 build / dev server **硬刷新**。
3. **清浏览器 IndexedDB** `eira-live2d-cache`（否则旧脏模型缓存仍在）。
4. 重启后 curl 实测端点返回 zip 再声称完成。

---

## 6. 验证清单（修复后必做）

- [ ] DB：user 69 `active_model_id` = 合法 OSS key（`live2d/` 前缀 + `.zip`/`.rar` 后缀）
- [ ] 后端：`GET /admin/assets` 每个 item 含 `oss_key`
- [ ] curl：`/user/model/file?oss_key=live2d/8767.../mao_pro_zh.zip` → 200 + PK zip
- [ ] curl：并发 4× `/admin/assets/{id}/file` → 全 200
- [ ] web-user 实机：无 502，`[Live2D] Successfully loaded`，纹理显示
- [ ] web-admin 实机：无 `Unknown model`、无 502，纹理显示 + 热切换
- [ ] 清 IndexedDB 后重载仍正常

---

## 7. ⚠️ 给下一个 agent 的告诫

1. **不要再盲改后端下载方式**。boto3 直读已实证可用（128/133/134 并发全 200）。P3 是残留进程，不是代码。前序 7 轮（方向 A/C/D）都误判于此。
2. **真正没修的是 P1（前端写脏 active_model_id）+ P2（schema 缺 oss_key）**，纯前端/schema 问题，与 OSS 签名无关。
3. 改完务必执行 §5 的「干净重启四件套」+ §6 验证，缺一不可。
4. 相关记忆：`live2d-oss-download-backend-stream.md`。

---

## 8. 服务启动

```bash
docker compose -f deploy/docker-compose.dev.yml up -d   # PG/Redis/MinIO

cd backend && EIRA_DB_DSN=postgresql+asyncpg://eira:eira@localhost:5432/eira \
EIRA_REDIS_URL=redis://localhost:6379/0 EIRA_OSS_ENDPOINT=http://localhost:9000 \
EIRA_OSS__SECRET=eira-secret EIRA_JWT__SECRET=dev-secret \
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pnpm --filter @eira/web-user dev    # 5173
pnpm --filter @eira/web-admin dev   # 5174
```
**Admin**: admin@eira.dev / admin123 ｜ **OSS 默认模型**: `live2d/8767b36fcc6c/mao_pro_zh.zip`
