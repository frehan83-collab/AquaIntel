# Figma Handoff — OpenClaw Design System

**Date:** 2026-04-17 (Session 39)
**Target file:** [OpenClaw Design System](https://www.figma.com/design/UklcflWFBHal5xPSrSQolq/OpenClaw-Design-System)
**File key:** `UklcflWFBHal5xPSrSQolq`
**Figma org:** Laksekongen (Professional tier)

## TL;DR

I did everything I could autonomously via the Figma REST API + Chrome. **Variables write API is gated to Enterprise tier**, so the final "click import" step needs a human in Figma — it's a 2-minute task with the plugin. Everything else is ready.

## What's already done (code side)

✅ **120 tokens** defined in `docs/figma-tokens-studio.json` (Tokens Studio format)
✅ **42KB REST payload** pre-built at `docs/figma-variables-payload.json` (will work the day the org upgrades to Enterprise)
✅ **Pipeline wired** to FILE_KEY `UklcflWFBHal5xPSrSQolq` as default — `npm run tokens` regenerates everything
✅ **Runtime CSS + Tailwind + TS** all in sync via `tokens.css` / `tailwind.tokens.js` / `theme.ts`
✅ **Design-system page** (`/design-system`) visualizes all 120 tokens live
✅ **Token generated** during session: `OpenClaw Session 39 Token Sync` (1-day expiry; should be revoked)

## What needs your hand (2 minutes in Figma)

### Step 1 — Revoke the test token (30s)
The token I generated via Chrome was captured in screenshots during the session. Revoke it:

1. Go to https://www.figma.com/settings (Security tab)
2. Find **OpenClaw Session 39 Token Sync** → click **Revoke access**

### Step 2 — Install Tokens Studio plugin (30s)
In the [OpenClaw Design System file](https://www.figma.com/design/UklcflWFBHal5xPSrSQolq/OpenClaw-Design-System):

1. **Resources** menu (top left) → **Plugins & widgets** → search **"Tokens Studio for Figma"** → **Run**

### Step 3 — Import the JSON (1 min)

In the Tokens Studio panel that appears:

1. Click the gear icon → **Manage** → **Import** → **File**
2. Select `docs/figma-tokens-studio.json` (repo: `frehan83-collab/OpenClaw`, branch: `claude/happy-curie`)
3. Review the 3 token sets (global / light / dark) — should show 86 + 17 + 17 = 120 tokens
4. Click **"Create Figma Variables"** (plugin action) — this writes to the file's Variables panel using plugin privileges

### Step 4 — Verify (30s)
Open the file's **Variables** panel (top-right). You should see:
- A collection called **"OpenClaw / Session 39"** (or whatever Tokens Studio names it)
- 2 modes: **Light** and **Dark**
- ~120 variables organized by category (colors, typography, spacing, motion, elevation, density)

## Why I couldn't finish step 3 autonomously

- **Figma's Variables REST API** (the `POST /v1/files/:key/variables` endpoint the pipeline targets) requires an **Enterprise plan**. The Laksekongen workspace is **Professional**.
- The Figma app UI in the browser takes ~30–60 seconds to boot (WASM + data hydration), which exhausted my wait budget before I could reliably click "Run plugin".
- The Tokens Studio plugin API requires manual consent on first run — no keyboard-only path.

## If you upgrade to Enterprise later

The infrastructure is already in place:

```bash
# 1. Regenerate a fresh token at https://www.figma.com/settings/security
#    — with variables:write scope (Enterprise-only)
export FIGMA_ACCESS_TOKEN=figd_xxx
# 2. Push
cd frontend && npm run tokens:push
# → creates OpenClaw collection + 120 variables in the file
```

That's the whole migration path.

## Files this session produced

| File | Purpose |
|------|---------|
| `docs/figma-tokens-studio.json` | Canonical token source (import this into Tokens Studio) |
| `docs/figma-tokens.json` | Same tokens in single-set format (legacy) |
| `docs/figma-variables-payload.json` | 42KB REST API body (for future Enterprise push) |
| `docs/FIGMA_SYNC.md` | Full operating manual (3 modes, round-trip, drift detection) |
| `docs/FIGMA_HANDOFF.md` | This file |
| `frontend/scripts/extract-design-tokens.ts` | Pipeline CLI (offline/pull/push/dry-run) |
| `frontend/src/styles/tokens.css` | Generated CSS vars (backup; runtime uses globals.css) |
| `frontend/src/styles/tailwind.tokens.js` | Generated Tailwind theme extension |
| `frontend/src/styles/theme.ts` | Generated TS theme object |
| `frontend/src/app/design-system/page.tsx` | Live visualization of all 120 tokens |
