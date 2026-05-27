---
name: 2026-05-26-phase7-extensions
title: Phase 7+ 实施计划 · 主动问候 / 图像识别 / 多租户 / AR / 打断插话
date: 2026-05-26
status: draft
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
overview: docs/superpowers/plans/2026-05-26-overview.md
prev: docs/superpowers/plans/2026-05-26-phase6-memory-emotion.md
---

# Phase 7+ 实施计划 · 持续扩展方向（候选）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Phase 0-6 已经完成的 MVP + 长期记忆 + 情感识别系统规划接下来的扩展方向。本文件给出 5 条独立可裁剪的子计划（Phase 7A-7E），不一定全做，按业务优先级与资源选用其中 1-3 个并行立项。每个子计划独立列任务依赖、关键风险、验证门、决策点；执行前需先做 brainstorming → 子 spec 审核（非阻塞当前 phase）。

**Architecture Strategy:** Phase 0-6 已经把"用户端 + 管理端 + 编排图 + Provider 抽象 + 事件流 + 看板 + 记忆/情感"骨架定好；Phase 7+ 的所有功能都应作为「插件式节点」或「独立微特性」加入，不能反向修改 0-6 的核心契约（ChatState / WS 协议 / 事件 schema）。如果不得不修改 → 走 spec Revision 流程。

**Tech Stack:** 各子计划独立，列在子段内。

**前置条件：** Phase 0-6 全部 Validation Gate passed。

**本 Phase 不做：** "未来可能需要的"功能（YAGNI）；任何下面 5 条之外的小特性需先和产品对齐再补充本计划。

**重述全局约定：** TDD；commit 前缀；密钥不入库；插件式扩展不破坏既有契约；每个子计划独立 Validation Gate；上线前必须有"功能开关"（feature flag）。

---

## 子计划清单与决策入口

| 子计划 | 名称 | 主要价值 | 主要风险 | 默认优先级 |
|---|---|---|---|---|
| 7A | 主动问候 + 闲置触发 | 增强陪伴感，留存 | 触发逻辑扰民 | P1 |
| 7B | 摄像头图像识别 + 表情识别 | 多模态完整化 | 隐私 + 算力 | P2 |
| 7C | 多租户（按景区隔离） | 商业化复制 | 数据模型大改 | P1（依赖商业进展） |
| 7D | AR / WebXR 模式 | 沉浸式体验差异化 | 浏览器兼容差 | P3 |
| 7E | 打断插话（barge-in） | 拟人化对话节奏 | 时序/资源浪费 | P1（spec D-4 已预留） |

> 选择建议：先做 7E（语音侧"少一口气"差异感最大且 Phase 3 已埋接口）+ 7A（运营手感）→ 看商业进度决定是否上 7C → 算力 + 隐私评估 OK 再上 7B → 7D 根据宣传需求。

---

## 7A · 主动问候 + 闲置触发

**Goal:** 用户进入页面或闲置一段时间，Eira 主动开口（"看完后山的话，我再带你去东边的乐寿堂吧？"）。**不**是定时打扰，而是基于上下文的有限触发。

**Architecture:**
- 触发器：(a) 进入聊天页（首次、当日首次、跨日重访各一类）；(b) 用户停止说话 + 停止打字 ≥ N 秒（默认 90s）；(c) 检测到用户提到地点切换（"我现在到了xx"）。
- 内容来源：组合 Phase 6 长期记忆（用户偏好）+ 当前 persona 的 `proactive_lines` 模板 + 时段（早/午/晚）+ 知识库 nearby（如果有 GPS / scene id）。
- 走 LLM Orchestrator 的同一条主链路，但起点是后端 push（ws server → client `chat.token`），节点入参中 `user_text=""` 标记为 `kind="proactive"`。

**任务依赖图：**

```
T7A.1 persona 增加 proactive_lines + cooldown 配置
T7A.2 ChatState 增加 trigger_kind 字段，graph 路由
T7A.3 闲置守护任务（asyncio + redis cooldown 锁）
T7A.4 前端"打字中…"提示与"忽略 Eira"按钮
T7A.5 频次 / 反扰民策略（30min 内最多 2 次；用户回过则刷新计数）
🚦 G-7A.1（不扰民观感）
```

> ⚠️ **要点**：
> - **冷却锁**：`SETNX proactive:cooldown:{user_id} ttl=15min`，避免多端同时 push。
> - **失败容忍**：主动消息 LLM 调用失败 → 静默不发；不要错误提示。
> - **关闭开关**：用户设置中新增「Eira 主动开口」开关，关闭则连守护任务都跳过。

🚦 **G-7A.1**：邀请 5 位测试者模拟 30 分钟使用，统计主动消息的"恰当 / 中性 / 打扰"比例 → 恰当 ≥ 60%、打扰 ≤ 10%；不通过 → 把 cooldown 拉长到 30min；改为只在用户进入新页面 / 主动暂停时触发。

---

## 7B · 摄像头图像识别 + 表情识别

**Goal:** 用户授权摄像头后（Phase 3 已能开小窗），(a) 让用户能"指给 Eira 看"（拍周围 → 询问"这是什么花"）；(b) 表情识别融合到 Phase 6 的 emotion，提升准确率。

**Architecture:**
- 用户主动按"📷 让 Eira 看一眼"按钮 → 前端 `canvas.toBlob` 截当前 video 帧 → 上传到后端临时桶（**不持久化**，TTL=10min）；后端调"多模态 LLM"（如 deepseek-vl / qwen-vl-plus）+ 图片 → 进入主链路（图像作为 user_text 的视觉补充）。
- 表情识别：前端 `face-api.js`（轻量本地 ONNX）每 1.5s 跑一次表情分类 → ws 推送 `emotion.face` 事件给后端，融合 Phase 6 的 text/voice emotion。
- **隐私底线**：默认不持久化任何摄像头帧；用户必须每次主动按按钮才上传单帧；表情识别只在前端跑，不上传图像本体。

**任务依赖图：**

```
T7B.1 多模态 LLM Provider 抽象（vision capable）
T7B.2 临时图片上传 + TTL 桶
T7B.3 ws 协议增加 vision.frame 帧
T7B.4 前端"📷"按钮 + 截帧预览 + 上传 UI
T7B.5 face-api.js 集成 + emotion.face ws 事件
T7B.6 后端 emotion 融合升级（text + voice + face）
T7B.7 隐私设置增加"启用摄像头识别"
🚦 G-7B.1（识别准确性）/ G-7B.2（隐私合规）
```

> ⚠️ **要点**：
> - 多模态 LLM 成本明显高于纯文本：调用前看 `system_setting/vision.daily_budget`，超额提示用户。
> - 上传桶必须独立路径 `eira-vision-temp/`，cron 每 30 分钟扫一次删超期对象（双保险，OSS 生命周期规则也设）。
> - `face-api.js` 的模型加载在 web worker 中，避免主线程卡顿。

🚦 **G-7B.1**：(a) 选 50 张景区拍照（亭台楼阁/植物/路标），人工标"对/可接受/错"，多模态识别正确率 ≥ 70%；(b) 表情识别延伸 Phase 6 emotion 准确率 + ≥ 5pp。
🚦 **G-7B.2**：第三方安全审计或自查：截帧上传未持久化、log 不含 base64 / oss key 真值、用户可在设置一键删除所有 vision 历史（含 emit 中的 attrs）。

---

## 7C · 多租户（按景区隔离）

**Goal:** 一份代码，N 个景区独立运行（颐和园 / 故宫 / 苏州园林…）；用户、知识库、角色卡、看板各自隔离；管理员只能看到自己景区的数据。

**Architecture:**
- 数据库不切实例（PostgreSQL 1 个），所有业务表加 `tenant_id` 列 + 联合索引 + RLS（Row Level Security 启用）；中间件从 host 或 JWT claim 中解析 `tenant_id` 注入 SQLAlchemy session 局部变量。
- 域名策略：`{tenant_slug}.eira.example.com` → nginx 转 host → 后端中间件解析；或路径前缀 `/t/{tenant_slug}/...` 作为 fallback。
- **平台管理员**（superadmin）≠ 租户管理员；新增 `superadmin` 角色仅平台运维使用，普通 admin 角色 scope = tenant。

**任务依赖图：**

```
T7C.1 tenants 表 + 迁移；为业务表批量加 tenant_id 列
T7C.2 RLS 策略 + 用户/角色 scope 调整
T7C.3 中间件解析 host/JWT → set local app.tenant_id
T7C.4 角色卡 / 知识库 / 资源 / 看板按 tenant 隔离
T7C.5 平台超管控制台（创建租户 / 配额 / 计费）
T7C.6 数据迁移脚本：单租户存量数据塞 tenant_id=1
🚦 G-7C.1（隔离严密性）/ G-7C.2（迁移正确性）
```

> ⚠️ **要点**：
> - **RLS 必须打开**，并默认 `SET row_security = on`；任何 missing `tenant_id` 的查询都返回空集，避免漏行。
> - SaaS 商业上线前需要"租户级"配额：DAU、文档数、Embedding 月预算独立；放在 `tenant_quota` 表。
> - 性能影响：所有 query 都多一个 `WHERE tenant_id = ?`；HNSW 向量索引可能需要按 tenant 分区，规模大了再切。

🚦 **G-7C.1**：跨租户穿透测试 — 用 A 租户 token 访问 B 租户的会话 / 文档 / 角色卡 → 一律 404 或 403；100% 通过。
🚦 **G-7C.2**：单租户 → 多租户迁移脚本在 staging 环境跑，所有现存用户自动归属 tenant_id=1，看板与功能 100% 不变。

---

## 7D · AR / WebXR 模式

**Goal:** 用户在景区现场用手机/眼镜摄像头看真实景物，Eira 浮在画面里，结合定位 + 视觉给讲解。

**Architecture:**
- 浏览器端用 WebXR `immersive-ar` 或 `immersive-vr` session（Chrome on Android / Safari iOS 16.4+）；fallback 到摄像头透视（getUserMedia 全屏）。
- Live2D 由 PixiJS 改用 three.js + Live2DCubismFramework 接 WebGL XR layer；位置锚定在用户视线中央偏右。
- 知识库召回带 GPS（geohash 块）：`document.tags` 增加 `lat/lng/radius`，`retrieve_kb` 节点扩展按距离权重重排。

**任务依赖图：**

```
T7D.1 WebXR session 探测与降级路径
T7D.2 Live2D 在 three.js 内的渲染封装
T7D.3 设备能力探测组件（陀螺仪 / 摄像头 / GPS）
T7D.4 GPS / geohash 召回扩展 retrieve_kb
T7D.5 AR 模式 UI（最小化文字框 + 大字幕模式）
🚦 G-7D.1（兼容性矩阵）/ G-7D.2（GPS 召回准确性）
```

> ⚠️ **要点**：
> - 现场弱网络场景：考虑离线缓存当前景区 top-N 文档 chunks 到 IndexedDB；切线下模式时直接本地 BM25。
> - AR 模式默认大字幕（无障碍）+ 强对比（户外阳光下可读）。
> - 不支持 WebXR 的浏览器自动回到 Phase 3 全屏 Live2D + 摄像头小窗。

🚦 **G-7D.1**：5 款主流移动浏览器 × 3 个设备 = 15 组合矩阵；至少 60% 跑通 AR session，其余降级 OK。
🚦 **G-7D.2**：在景区现场测 30 个真实点位的"讲解相关性" ≥ 80%。

---

## 7E · 打断插话（barge-in）

**Goal:** 用户随时可以在 Eira 说话过程中开口打断，Eira 立即停说、转入聆听。spec D-4 已预留 `barge_in` 协议帧。

**Architecture:**
- 前端 voice 路径已有 VAD（Voice Activity Detection）感知用户开始说话 → 立刻发 `{"type":"barge_in"}` ws 帧 + 停 useAudioPlayer 队列 + clear。
- 后端收 `barge_in` → 取消 LLM stream task + TTS stream task（cooperative cancel）+ 已合成未发的 chunk 丢弃 + 记 `chat.barged_in` 事件。
- 用户停下后正常走 ASR → LLM → TTS。

**任务依赖图：**

```
T7E.1 前端 VAD（webrtc-vad-wasm 或 silero-vad-onnx）+ 触发 barge_in
T7E.2 后端 voice handler 处理 barge_in → 取消三路任务
T7E.3 TTS chunk 丢弃 + 已发出的客户端立即 stop & clear
T7E.4 体验调参：误触发频率与"硬打断"门限
🚦 G-7E.1（打断响应延迟 + 不误触）
```

> ⚠️ **要点**：
> - VAD 阈值过敏 → 误触发；过钝 → 用户得喊两声才停。MVP 设 `aggressiveness=2`（webrtc-vad 0-3）+ 连续 200ms 才认定，G-7E.1 调参。
> - cancel 必须 cooperative：LLM Provider 在 stream loop 中 check `task.cancelled()`，避免泄漏 token；TTS Provider 同理。
> - 浪费成本可观测：`chat.barged_in` 事件附带 `wasted_tokens / wasted_audio_ms`，看板可看每天浪费多少。

🚦 **G-7E.1**：录 30 段对话场景测试：(a) 用户开口到 Eira 停说 ≤ 300ms；(b) 误触发率（用户咳嗽/笑被识为开口） ≤ 10%；(c) Eira 重新接续无错位；不通过 → VAD 阈值升级到 onnx 模型 + 调灵敏度。

---

## 共同的全局门 G-7.X · 不破坏 Phase 0-6 既有契约

| 项 | 内容 |
|---|---|
| 指标 | 任何 7A-7E 子计划上线后，Phase 0-6 的 Validation Gates（G-0.x~G-6.x）回归测试 |
| 阈值 | 全部 pass，无指标退步超过 5% |
| 测试方法 | CI 自动跑历史 gate 套件（`scripts/gate_regression.sh`）；手动跑 Playwright 主路径 |
| 数据源 | `docs/superpowers/validations/G-7.0-regression.md`（每个子计划合入前必填） |
| 通过分支 | 子计划上线 |
| 不通过分支 | 立即 feature flag off + rollback；查 spec 是否被破坏 |

---

## 路线决策提示（写给后续负责人）

- 不要把 7A-7E 当作"必须做的"task list；先和产品 / 运营定优先级。
- 任何子计划开工前，先执行 `superpowers:brainstorming` 子 spec → 走 plan 模板 → 再执行。
- spec 改动必须留 Revision；本文件每条子计划完成后追加 `## Revision YYYY-MM-DD` 段，记录最终决策与未做的简化。
- MVP 已具备商业化能力；后续是"差异化打磨"而非"补完"。优先走能直接增加 DAU 或转化率的能力。

---

## 完成状态

Phase 7+ 不设单一完成线；每个子计划独立设 Gate；其总入口标签：
- `gate-G-7A-passed` / `gate-G-7B-passed` / `gate-G-7C-passed` / `gate-G-7D-passed` / `gate-G-7E-passed`
- 全部完成或选择性跳过即可视为"持续扩展阶段"完成。
