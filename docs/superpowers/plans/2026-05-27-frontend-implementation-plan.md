---
name: eventual-dazzling-treehouse
title: Eira Frontend Implementation Plan
date: 2026-05-27
status: draft
spec: docs/superpowers/specs/2026-05-26-architecture-design.md
---

# Eira Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement plans task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Context:** The goal is to fully implement the frontend architecture for the Eira project as defined in the `2026-05-26-architecture-design.md` and original `DESIGN.txt`. This replaces the previous piecemeal phase plans with a comprehensive, spec-aligned frontend implementation plan encompassing `packages/ui-shared`, `apps/web-user`, and `apps/web-admin`. All logic, layout (glassmorphism, z-indexing, 3-column admin), and interactivity (Live2D drag/zoom, voice integration) described in the spec must be addressed.

## 1. `packages/ui-shared` Restructuring

The `ui-shared` package serves as the core foundational layer for both SPA applications. It provides the exact glassmorphism design tokens specified in DESIGN.txt and shared utility composables.

### Dependencies (`packages/ui-shared/package.json`)
- Add/Ensure `vue`, `axios` (peer/deps), `typescript`, `vite` (devDeps).

### Implementation Steps

- [ ] **Step 1: CSS Design Tokens (`packages/ui-shared/src/tokens.css`)**
  - Implement exact variables from spec: `--glass-bg`, `--glass-border`, `--glass-blur: 24px`, `--radius-card: 24px`, `--radius-pill: 9999px`, `--shadow-soft`, `--color-accent: #6aa2ff`, `--color-text-primary`, `--ease-soft`.
  - Export them for global usage across both SPAs.

- [ ] **Step 2: Atomic Glass Components (`packages/ui-shared/src/components/`)**
  - Implement `GlassCard.vue`, `GlassButton.vue`, `GlassInput.vue`, `GlassModal.vue` utilizing the `tokens.css` variables.
  - Ensure components support proper `pointer-events` toggling for use in layered UI.

- [ ] **Step 3: Shared Composables (`packages/ui-shared/src/composables/`)**
  - `useHttp.ts`: Axios instance configured with JWT access/refresh interceptors.
  - `useAuthStore.ts`: Pinia store for JWT tokens, user role (visitor/admin/superadmin).
  - `useWebSocket.ts`: Reusable WS client handling exponential backoff, ping/pong heartbeats, and parsing the standard envelope.

- [ ] **Step 4: Exports (`packages/ui-shared/src/index.ts`)**
  - Export all components, stores, and composables cleanly.

---

## 2. `apps/web-user` Implementation

The immersive Live2D client.

### Dependencies (`apps/web-user/package.json`)
- Add `pixi.js@^7`, `pixi-live2d-display@^0.4`, `@vueuse/core`, `@vueuse/motion`. 
- Ensure `@eira/ui-shared` is linked.

### Implementation Steps

- [ ] **Step 1: Layout & Canvas Z-Index Architecture (`apps/web-user/src/pages/Chat.vue`)**
  - Implement the 3-layer architecture:
    1. Layer 0: Background (pure color, image, or video).
    2. Layer 1: Full-screen PixiJS canvas for Live2D.
    3. Layer 2: UI Overlay (`pointer-events: none` container with glassmorphic elements set to `pointer-events: auto`).

- [ ] **Step 2: Live2D Controller (`apps/web-user/src/composables/useLive2DController.ts` & `src/live2d/Live2DStage.ts`)**
  - Initialize Pixi application and load Cubism models. Use **local static assets** (`/public/live2d/Hiyori/`) for this initial implementation phase per user preference.
  - Implement canvas drag (retaining 20% bounds) and zoom (0.3x - 3x) via pointer/wheel events.
  - Persist position/scale in `localStorage` keyed by character ID.

- [ ] **Step 3: UI Overlay Components (`apps/web-user/src/components/`)**
  - `TopSettingsButton.vue`: Minimal hollow gear icon (top-left).
  - `CameraMiniWindow.vue`: Translucent rounded rectangle PIP window for front camera (top-right).
  - `CharacterSpeechBubble.vue`: Faded grey-white translucent box below chest level.
  - `QuickQuestionPanel.vue`: Capsule buttons aligned left with input.
  - `ChatInputArea.vue`: Ultra-wide blurred input box at bottom. Inside: left-aligned mic icon, right-aligned '+' and paper-plane send buttons.

- [ ] **Step 4: Audio & WS Integration (`apps/web-user/src/composables/`)**
  - `useVoiceRecorder.ts`: Capture mic via `MediaRecorder`/`AudioWorklet` into chunks.
  - `useTTSPlayer.ts`: Play streaming audio frames from WS, trigger Live2D LipSync.
  - `useChatSession.ts`: Connect WS, manage text/audio stream, handle `agent.thinking`, `agent.text.delta`, and map `agent.action` to `useActionParser.ts` for Live2D motions.

---

## 3. `apps/web-admin` Implementation

The management dashboard.

### Dependencies (`apps/web-admin/package.json`)
- Add `naive-ui`, `echarts`, `vue-echarts`.
- Ensure `@eira/ui-shared` is linked.

### Implementation Steps

- [ ] **Step 1: Admin Shell & Routing (`apps/web-admin/src/layouts/AdminLayout.vue`)**
  - Implement fixed 72px top navigation with tabs (Dashboard, Interaction, Content, System).

- [ ] **Step 2: 3-Column Dashboard Layout (`apps/web-admin/src/pages/Dashboard.vue`)**
  - Use Naive UI Grid to implement the exact spec widths: Left 26%, Middle 38%, Right 36%.
  - Middle: Implement `AdminLive2DPreview.vue` with hover actions.
  - Right: Implement Echarts wrappers (`InteractionChart.vue`, `WordCloudWidget.vue`) rendering mocked `analytics_daily` data structure.

- [ ] **Step 3: Persona & Knowledge Management (`apps/web-admin/src/pages/Content/`)**
  - `Personas.vue`: CRUD view with a form editor matching SillyTavern fields (`name`, `description`, `personality`, `scenario`, `first_mes`).
  - `Knowledge.vue`: Naive UI `NUpload` for documents, table showing vectorization status (pending/processing/indexed), and a "Retrieval Preview" modal.

- [ ] **Step 4: Asset Management (`apps/web-admin/src/pages/Content/Live2D.vue`)**
  - Interface for ZIP uploading Live2D models and backgrounds, updating system settings.

## Verification

1. Run `pnpm install` in root.
2. Run `pnpm dev` to start Vite servers for both `web-user` and `web-admin`.
3. Open `web-user` in browser: Verify Live2D placeholder loads, zooms, drags, and the UI overlay matches the visual layout exactly.
4. Open `web-admin` in browser: Verify the 3-column layout is correct and Naive UI components render properly.