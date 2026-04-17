# Figma Sync — OpenClaw Design System

**Last updated:** 2026-04-14 (Session 39)
**Status:** Ready for Figma designer handoff

This document is the operating manual for the OpenClaw design token pipeline. It explains how code and Figma stay in sync.

---

## 1. The single source of truth

**`docs/figma-tokens-studio.json`** is the canonical token definition. Every other file is generated from it or hand-mirrored for runtime.

```
docs/figma-tokens-studio.json   ◄─── canonical (hand-edited OR pulled from Figma)
      │
      ├── scripts/extract-design-tokens.ts (pipeline)
      │        │
      │        ├── frontend/src/styles/tokens.css           (Figma-round-trip backup)
      │        ├── frontend/src/styles/tailwind.tokens.js   (Figma-round-trip backup)
      │        ├── frontend/src/styles/theme.ts             (Figma-round-trip backup)
      │        └── docs/figma-variables-payload.json        (REST API body)
      │
      └── frontend/src/app/globals.css                       (RUNTIME source — hand-authored)
               │
               └── frontend/tailwind.config.ts                (RUNTIME Tailwind config — hand-authored)
```

**Why two tracks?** The runtime `globals.css` is hand-authored so we can tune values quickly. The pipeline track exists so we can round-trip through Figma without losing design intent. Both should match; CI could verify this.

---

## 2. Token categories (120 tokens total, Session 39)

| Category | Count | Examples | Source |
|----------|-------|----------|--------|
| Color (global) | 42 | chart.1..8, data.biomass, traffic.green, salmon, danger | `figma-tokens-studio.json#global` |
| Color (light) | 17 | bg.primary, text.primary, accent, surface.0..4, glass.base | `figma-tokens-studio.json#light` |
| Color (dark) | 17 | Dark-mode equivalents of light | `figma-tokens-studio.json#dark` |
| Typography | 19 | fontFamily × 4, fontSize × 10, lineHeight × 5 | `figma-tokens-studio.json#global.typography` |
| Spacing | 11 | spacing.1..20 | `figma-tokens-studio.json#global.spacing` |
| Border radius | 6 | sm/md/lg/xl/2xl/full | `figma-tokens-studio.json#global.borderRadius` |
| Motion | 9 | duration × 5, easing × 4 | **Session 39** |
| Elevation | 6 | 0..5 paired shadow+blur | **Session 39** |
| Density | 8 | comfortable × 4, compact × 4 | **Session 39** |
| Font weight | 4 | regular/medium/semibold/bold | — |

---

## 3. Three operating modes

### 3a. Offline (default — no Figma access needed)

```bash
cd frontend
npx tsx scripts/extract-design-tokens.ts
```

Reads `docs/figma-tokens-studio.json`, regenerates the 4 output files. Use this after hand-editing the JSON.

### 3b. Pull from Figma (requires personal access token)

```bash
FIGMA_ACCESS_TOKEN=xxx FIGMA_FILE_KEY=yyy npx tsx scripts/extract-design-tokens.ts --pull
```

Fetches Figma Variables via the REST API and merges them over `figma-tokens-studio.json`. Use when the designer has updated tokens in Figma and we want them in code.

**Output:** `docs/figma-pulled.json` (raw response for inspection).

### 3c. Push to Figma (requires personal access token)

```bash
FIGMA_ACCESS_TOKEN=xxx FIGMA_FILE_KEY=yyy npx tsx scripts/extract-design-tokens.ts --push
```

Uploads `docs/figma-variables-payload.json` (generated during `offline`) to Figma as Variables. Use when code is ahead of Figma (e.g. after adding new motion tokens).

**Output:** `docs/figma-push-result.json` (temp-ID → real-ID mapping).

### 3d. Dry run

```bash
npx tsx scripts/extract-design-tokens.ts --dry-run
```

Prints output sizes without writing anything. Useful for CI.

---

## 4. Getting a Figma access token

1. Visit https://www.figma.com/developers/api#access-tokens
2. Click **Generate new token** (scope: Read + Write variables)
3. Copy the token (it looks like `figd_...`)
4. Export into your shell or put in a `.env.local`:
   ```bash
   export FIGMA_ACCESS_TOKEN=figd_xxx
   export FIGMA_FILE_KEY=aBcDeF123456789
   ```
5. File key is the string after `/file/` in the Figma URL: `https://www.figma.com/file/aBcDeF123456789/...`

**Rate limit:** 200 GET/minute. The `FigmaClient` (`src/lib/figma/client.ts`) auto-throttles at 190/min.

---

## 5. Figma Tokens Studio plugin (for designers)

The designer workflow is:

1. Install **Tokens Studio for Figma** plugin (free)
2. In plugin settings: **Sync → GitHub** → point at `docs/figma-tokens-studio.json` in this repo
3. Changes in Figma → "Push to GitHub" → opens a PR
4. Developers merge the PR → run `npx tsx scripts/extract-design-tokens.ts` → commit generated outputs

This is the preferred workflow — no REST API credentials needed.

---

## 6. When to push vs pull

| Situation | Action |
|-----------|--------|
| Designer changed a color in Figma | Designer pushes via Tokens Studio → GitHub PR → dev merges + regenerates |
| Dev added motion tokens in code (Session 39) | Dev runs `--push` OR commits figma-tokens-studio.json → designer pulls via plugin |
| Unsure who is ahead | Run `--pull` to a clean branch, diff against HEAD. The winner is whoever has the richer, more recent values. |

---

## 7. What's in the REST payload

`docs/figma-variables-payload.json` (42 KB, generated) contains everything needed to create the OpenClaw token collection in a brand-new Figma file:

- 1 variable collection: "OpenClaw / Session 39"
- 2 modes: "Light", "Dark"
- ~120 variables (auto-derived from `figma-tokens-studio.json`)
- Per-variable scopes (e.g. color variables scoped to `ALL_FILLS` + `STROKE_COLOR`)
- `codeSyntax.WEB` = the CSS `var(...)` reference, so Dev Mode in Figma shows the exact runtime name

**To use:** POST this file body to `/v1/files/:key/variables` (the pipeline does this for you in `--push` mode).

---

## 8. Drift detection (CI recipe)

Add to `.github/workflows/test.yml`:

```yaml
- name: Token drift check
  run: |
    cd frontend
    npx tsx scripts/extract-design-tokens.ts
    if ! git diff --quiet src/styles/ ../docs/figma-variables-payload.json; then
      echo "Token drift detected. Run 'npx tsx scripts/extract-design-tokens.ts' locally and commit."
      exit 1
    fi
```

---

## 9. Known limitations

- **Pull mode is a stub.** The REST→Tokens-Studio merger is not yet written; pull currently saves the raw Figma JSON to `docs/figma-pulled.json` for manual inspection. Implement when we actually have a populated Figma file.
- **Alias resolution is not implemented.** Tokens Studio supports `{color.accent}` refs; our pipeline treats them as literal strings. Add when needed.
- **Only color, fontSize, spacing, borderRadius, and typography are pushed to Figma.** Motion / elevation / density tokens are CSS-only; Figma's Variables API doesn't natively understand easing functions, so these stay as `STRING` variables.

---

## 10. Quick reference

```bash
# Regenerate after hand-editing figma-tokens-studio.json
cd frontend && npx tsx scripts/extract-design-tokens.ts

# Preview sizes
npx tsx scripts/extract-design-tokens.ts --dry-run

# Pull latest from Figma
FIGMA_ACCESS_TOKEN=xxx FIGMA_FILE_KEY=yyy npx tsx scripts/extract-design-tokens.ts --pull

# Push code tokens to Figma
FIGMA_ACCESS_TOKEN=xxx FIGMA_FILE_KEY=yyy npx tsx scripts/extract-design-tokens.ts --push
```

---

**Session 39 addition:** Added 36 new tokens (motion, elevation, glass ladder, line-heights, density, 2xs/3xs font-size). Total grew from 86 to 120. All are in both the Figma sync file and the runtime globals.css.
