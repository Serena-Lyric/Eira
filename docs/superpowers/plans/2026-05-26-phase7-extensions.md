---
name: 2026-05-26-phase7-extensions
title: Phase 7+ 实施计划 · 持续扩展方向（候选）
date: 2026-05-26
status: draft
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
overview: docs/superpowers/plans/2026-05-26-overview.md
prev: docs/superpowers/plans/2026-05-26-phase6-memory-emotion.md
revision: 2026-06-02 — 无重大变更，前端摄像头/设置面板 UI 已就位
---

# Phase 7+ 实施计划 · 持续扩展方向（候选）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Phase 0-6 已经完成的 MVP + 长期记忆 + 情感识别系统规划接下来的扩展方向。本文件给出 5 条独立可裁剪的子计划（Phase 7A-7E），按业务优先级与资源选用。每个子计划独立列任务依赖、关键风险、验证门、决策点；执行前需先做 brainstorming → 子 spec 审核。

## 🔒 前端 UI 状态

- 7B 所需的摄像头小窗 UI 已在 Chat.vue 中完成（CameraMiniWindow 组件，`getUserMedia` 注释待启用）。
- 7E 所需的打断交互已预留 WS 协议帧 `barge_in`，前端 VAD 可在 useMicRecorder 中启用。
- 其余子计划（7A/7C/7D）可能涉及新 UI 元素，开工前需单独评估。

**Architecture Strategy:** Phase 0-6 已经把核心骨架定好；Phase 7+ 的所有功能都应作为「插件式节点」或「独立微特性」加入，不能反向修改 0-6 的核心契约（ChatState / WS 协议 / 事件 schema）。如果不得不修改 → 走 spec Revision 流程。

---

## 子计划清单与决策入口

| 子计划 | 名称 | 主要价值 | 主要风险 | 默认优先级 |
|---|---|---|---|---|
| 7A | 主动问候 + 闲置触发 | 增强陪伴感，留存 | 触发逻辑扰民 | P1 |
| 7B | 摄像头图像识别 + 表情识别 | 多模态完整化 | 隐私 + 算力 | P2 |
| 7C | 多租户（按景区隔离） | 商业化复制 | 数据模型大改 | P1（依赖商业进展） |
| 7D | AR / WebXR 模式 | 沉浸式体验差异化 | 浏览器兼容差 | P3 |
| 7E | 打断插话（barge-in） | 拟人化对话节奏 | 时序/资源浪费 | P1（spec D-4 已预留） |

> 选择建议：先做 7E（spec D-4 已预留协议帧）+ 7A（运营手感）→ 看商业进度决定 7C → 算力+隐私评估 OK 再上 7B → 7D 根据宣传需求。

---

## 7A · 主动问候 + 闲置触发

**Goal:** 用户进入页面或闲置一段时间，Eira 主动开口。基于上下文的有限触发，不是定时打扰。

**关键任务：**
- T7A.1 persona 增加 proactive_lines + cooldown 配置
- T7A.2 ChatState 增加 trigger_kind 字段
- T7A.3 闲置守护任务（asyncio + Redis cooldown 锁 `SETNX proactive:cooldown:{user_id} ttl=15min`）
- T7A.4 前端"打字中…"提示与"忽略 Eira"按钮（可能需要新增 UI 元素，开工前评估）
- T7A.5 频次/反扰民策略（30min 内最多 2 次）

🚦 **G-7A.1**：5 位测试者 30 分钟使用 → 恰当 ≥ 60%、打扰 ≤ 10%。

---

## 7B · 摄像头图像识别 + 表情识别

**Goal:** 用户授权摄像头后（Phase 3 已能开小窗），让用户"指给 Eira 看" + 表情识别融合到 emotion。

**关键任务：**
- T7B.1 多模态 LLM Provider 抽象（vision capable）
- T7B.2 临时图片上传 + TTL 桶（不持久化）
- T7B.3 WS 协议增加 vision.frame 帧
- T7B.4 前端"📷"按钮（Chat.vue 中已有附件按钮 UI，可扩展复用）
- T7B.5 face-api.js 集成 + emotion.face WS 事件
- T7B.6 后端 emotion 融合升级（text + voice + face）
- T7B.7 隐私设置增加"启用摄像头识别"

🚦 **G-7B.1**：50 张景区拍照识别正确率 ≥ 70%。
🚦 **G-7B.2**：第三方安全审计 — 截帧上传未持久化、log 不含 base64/oss key、用户可一键删除。

---

## 7C · 多租户（按景区隔离）

**Goal:** 一份代码，N 个景区独立运行。用户、知识库、角色卡、看板各自隔离。

**关键任务：**
- T7C.1 tenants 表 + 所有业务表加 tenant_id 列
- T7C.2 RLS 策略 + 用户/角色 scope 调整
- T7C.3 中间件解析 host/JWT → set local app.tenant_id
- T7C.4 角色卡/知识库/资源/看板按 tenant 隔离
- T7C.5 平台超管控制台（创建租户/配额/计费）
- T7C.6 数据迁移脚本

🚦 **G-7C.1**：跨租户穿透测试 100% 返回 404/403。
🚦 **G-7C.2**：迁移脚本在 staging 跑，存量数据 100% 不变。

---

## 7D · AR / WebXR 模式

**Goal:** 用户在景区现场用手机看真实景物，Eira 浮在画面里结合定位+视觉讲解。

**关键任务：**
- T7D.1 WebXR session 探测与降级路径
- T7D.2 Live2D 在 three.js 内的渲染封装
- T7D.3 设备能力探测组件（陀螺仪/摄像头/GPS）
- T7D.4 GPS/geohash 召回扩展 retrieve_kb
- T7D.5 AR 模式 UI（最小化文字框 + 大字幕模式，需新增 UI，开工前单独设计）

🚦 **G-7D.1**：5 款浏览器 × 3 个设备 = 15 组合，至少 60% 跑通 AR session。
🚦 **G-7D.2**：景区现场 30 个点位讲解相关性 ≥ 80%。

---

## 7E · 打断插话（barge-in）

**Goal:** 用户随时可以在 Eira 说话过程中开口打断，Eira 立即停说、转入聆听。

**关键任务：**
- T7E.1 前端 VAD（webrtc-vad-wasm 或 silero-vad-onnx）+ 触发 barge_in（可在 useMicRecorder 中启用）
- T7E.2 后端 voice handler 处理 barge_in → 取消三路任务（LLM/TTS/audio pump）
- T7E.3 TTS chunk 丢弃 + 客户端立即 stop & clear
- T7E.4 体验调参：误触发频率与"硬打断"门限

🚦 **G-7E.1**：(a) 开口到 Eira 停说 ≤ 300ms；(b) 误触发 ≤ 10%；(c) 重新接续无错位。

---

## 共同的全局门 G-7.X · 不破坏 Phase 0-6 既有契约

任何 7A-7E 子计划上线后，Phase 0-6 的 Validation Gates 回归测试必须全部 pass，无指标退步超过 5%。

---

## 路线决策提示

- 不要把 7A-7E 当作"必须做的"task list；先和产品/运营定优先级。
- 任何子计划开工前，先执行 brainstorming → 子 spec → plan 模板 → 再执行。
- spec 改动必须留 Revision；每条子计划完成后追加 `## Revision YYYY-MM-DD` 段。
- MVP 已具备商业化能力；后续是"差异化打磨"而非"补完"。

---

## 完成状态

Phase 7+ 不设单一完成线；每个子计划独立设 Gate。

## Revision 2026-06-02

- 无重大变更。7B 摄像头小窗 UI 和 7E 打断协议帧在 Phase 3 前端中已预留，开工时可直接启用。
- 各子计划中涉及新增 UI 的步骤（7A.4/7D.5 等）标注了"开工前需单独评估"。
- 其余内容保持原样。
