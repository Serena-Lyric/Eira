# Eira Handoff · 2026-06-15 · Live2D 加载问题 ✅ 已解决

> **源会话**: 接续 rootcause-review，完整实施修复 + 实机验证通过
> **状态**: ✅ 两端实机加载成功（user + admin 均正常显示模型）
> **分支**: master
> **前序文档**:
> - `eira-handoff-2026-06-15-live2d-admin-fix.md`（admin 7 轮尝试史）
> - `eira-handoff-2026-06-15-live2d-rootcause-review.md`（三根因诊断）

---

## 0. TL;DR

历经多轮失败循环后本轮**彻底解决**。真正的根不是单一 bug，而是一连串叠加问题，最关键的是上一轮被全部忽略的 **admin/user 两套模型标识体系裂缝**：

| # | 问题 | 修复 |
|:-:|------|------|
| **核心** | admin 按「显示名/文件夹名」标识模型，user 只认「OSS key」，二者共用一份 `persona_config` 却从未对齐 | 统一以 OSS key 存储，admin UI 仍显示名字 |
| A | fallback 守卫只校验用户值，回退源 `default_model_id` 本身是脏显示名时又被赋回 → 502 | 回退源也校验 `startswith("live2d/")`，非法下发 None |
| B | shared loader 的 `installFetchInterceptor` 全局单例，连续加载多模型时后者复用前者拦截器 → 加载错文件 | 改为 `virtualBase→files` 注册表，window.fetch 只 hook 一次 |
| C | 后端进程跑的不是当前磁盘代码（残留进程 / --reload 漏更新） | 新增 `run_clean.sh`：杀净端口树 + 清 pycache + 无 reload 单进程 |
| D | DB 数据：`persona_config.active_model_id = "mao_pro_zh"`（显示名脏值） | 迁移为 `live2d/8767b36fcc6c/mao_pro_zh.zip` |

**关键教训**：前几轮反复在「后端 OSS 下载方式」上打补丁（presigned→httpx→IPv4→307→boto3），但那一层早就是对的。真问题在**前端标识体系 + 数据 + 残留进程**，与 OSS 签名无关。诊断必须靠探针/DB实查/curl 实证，不能靠猜。

---

## 1. 完整根因链（为什么 user 一直 502）

1. admin 在 Dashboard 左栏选模型 → `savePersonaConfig` 写入 `active_model_id = selectedModel`（= 显示名 `mao_pro_zh`）
2. `persona_config` 是 admin/user **共享**的全局配置
3. user 进聊天页 → `getPreferences` 读 `active_model_id`
4. 用户自己的值被清空 → 走 fallback → 读 `persona_config.active_model_id` = `mao_pro_zh`
5. 旧守卫只校验用户值「非法则回退」，但**回退源本身就是非法的 `mao_pro_zh`** → 又赋回去
6. 前端拿 `mao_pro_zh` 请求 `/user/model/file?oss_key=mao_pro_zh`
7. boto3 `get_object(bucket=eira-live2d, key=mao_pro_zh)` → 查无此 key → **502**

admin 侧自洽（`changeModel` 四向匹配能按显示名匹配），所以 admin 自己一直「看起来对」，唯独 user 读不懂。

---

## 2. 改动文件清单（本轮，未 commit）

| 文件 | 改动 |
|------|------|
| `backend/scripts/run_clean.sh` | **新增** — 干净启动脚本（杀端口树 + 清 pycache + 无 reload） |
| `backend/app/api/rest/user.py` | fallback 守卫：回退源 `default_model_id` 也校验 `startswith("live2d/")`，非法下发 None |
| `apps/web-admin/src/pages/Dashboard.vue` | `savePersonaConfig` 写 OSS key（查 `m.ossKey`）；`loadPersonaConfig` 读 OSS key 映射回显示名做 UI 选中态 |
| `apps/shared/live2d/live2dLoader.ts` | fetch 拦截器从单例改为 `virtualBase→files` 注册表，支持多模型并存 |

**前序会话已落地（也未 commit）**：
- `backend/app/infra/oss.py` — `get_object_bytes(bucket, key)`
- `backend/app/api/rest/admin_assets.py` — `/{id}/file` boto3 直读 + `AdminAssetOut.oss_key` 字段
- `backend/app/api/rest/user.py` — `GET /user/model/file?oss_key=`
- `apps/web-user/src/composables/useLive2DModelLoader.ts` — `ossKey` state + 打 `/api/user/model/file`
- `apps/web-user/src/composables/useLive2DController.ts` — 分离 `activeModelOssKey` / `activeModelId`
- `apps/web-user/src/pages/Chat.vue` — PATCH 用 `activeModelOssKey`

**DB 迁移（已授权执行）**：`persona_config.active_model_id`: `mao_pro_zh` → `live2d/8767b36fcc6c/mao_pro_zh.zip`（`active_model_display_name` 保留显示名）

---

## 3. 标识体系约定（务必遵守）

| 字段 | 标准值 | 谁写 | 谁读 |
|------|--------|------|------|
| `persona_config.active_model_id` | **OSS key** `live2d/.../xxx.zip` | admin Dashboard | user + admin |
| `persona_config.active_model_display_name` | 显示名 `mao_pro_zh` | admin | 仅展示 |
| `user_preferences.active_model_id` | **OSS key** 或 null（走默认） | web-user | user |
| admin `availableModels[].id`/`label` | 显示名（asset.name） | — | UI 选中态 |
| admin `availableModels[].ossKey` | OSS key（asset.oss_key） | — | 持久化 / changeModel |
| admin `availableModels[]._ossKey` | asset.id（数字） | — | 下载端点 `/admin/assets/{id}/file` |

**铁律**：任何写入 `active_model_id`（persona_config 或 user_preferences）的地方，值**必须是 OSS key**（`startswith("live2d/")`）。virtualBase（`eira-model://`）和显示名都是脏值。

---

## 4. 验证结果（全部实测通过）

| 项 | 结果 |
|---|---|
| 两端 `pnpm build` | ✅ |
| `run_clean.sh` 单进程启动 | ✅ |
| user/preferences `active_model_id` | ✅ 合法 OSS key |
| persona_config.get | ✅ 合法 OSS key |
| 18 并发请求（12 下载 + 6 prefs） | ✅ 全 200，零 502/500 |
| user `/model/file` 默认 key 下载 | ✅ 200, 77.5MB |
| 守卫拒绝脏默认值（注入 `mao_pro_zh`） | ✅ 返回 None，不下发脏值 |
| **实机：user + admin 两端模型显示** | ✅ 成功 |

---

## 5. ⚠️ 给下一个 agent 的告诫

1. **启动后端一律用 `bash backend/scripts/run_clean.sh`**，不要手动 `--reload`。本问题反复出现的最大干扰就是「残留旧进程跑旧代码」——日志里出现你代码不该产生的值（如 `oss_key=mao_pro_zh`、`eira-model://`）时，第一反应应是「进程没更新」而非改代码。
2. **后端 OSS 下载方式已定稿**：boto3 `get_object_bytes` 直读，两端走 `/admin/assets/{id}/file` 和 `/user/model/file`。不要再碰 presigned URL / Vite proxy / 307 重定向。
3. 改任何涉及 `active_model_id` 的逻辑，先回看 §3 标识体系约定。
4. 实机验证前的四件套：`run_clean.sh` 重启 + 两端 build/硬刷新 + 清浏览器 IndexedDB `eira-live2d-cache` + 重新登录。

---

## 6. 仍待办

- [ ] 本轮所有改动 + 前序会话改动**尚未 commit**（`user.py`、`admin_dashboard.py` 等仍是未跟踪 `??` 状态，是更早遗留）
- [ ] `useLive2DPreview.ts` 的 `resolveModelMeta` 在 `loadModel` 前调用，此时 `m.dir`/`m.fileName` 为空，vtube/动作探测实际是坏的（不影响加载，但预览图/探测动作可能失效）— 低优先级

---

## 7. 服务启动

```bash
docker compose -f deploy/docker-compose.dev.yml up -d   # PG/Redis/MinIO
bash backend/scripts/run_clean.sh                        # 后端（单进程，无 reload）
pnpm --filter @eira/web-user dev                         # 5173
pnpm --filter @eira/web-admin dev                        # 5174
```
**Admin**: admin@eira.dev / admin123 ｜ **默认模型 OSS key**: `live2d/8767b36fcc6c/mao_pro_zh.zip`
