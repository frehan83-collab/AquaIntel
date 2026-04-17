# AquaIntelligence / FishIntel Design System Audit Report

**Generated:** 2026-04-14
**Scope:** Full frontend (frontend/src — 63 pages, 48 components, Tailwind + CSS vars)
**Stack:** Next.js 15.5 + React 19.2 + Tailwind 3.x + DM Sans/DM Serif Display/JetBrains Mono
**Total findings:** P0: 17 · P1: 42 · P2: 18 (77 total)

## Executive summary
OpenClaw/FishIntel has substantial design plumbing — a Figma token pipeline, 86 tokens, a dark/light theme, 48 components, an i18n system with ~588 Norwegian/English key pairs — but **four parallel token sources drift**, **145 hex colors and 2,695 arbitrary `text-[...]` sizes** leak outside the system, and **319 raw `.toFixed()` calls** still bypass locale formatting. The `ui/` primitive folder has only `Button`, so every page reinvents Card, Modal, Input, Tabs. All 63 pages share one generic skeleton. Motion is heavily used (545 framer-motion calls) with zero shared duration/easing tokens. There is no density mode. Fix path: consolidate to one token source, stand up `components/ui/`, run three codemods, and lock 20 design decisions in the Figma session. See the final sections for the full plan.

---

## Dimension 1 — Foundation tokens

### Inventory
**Four parallel token sources** detected:
1. `frontend/tailwind.config.ts` — Tailwind scale (ocean 50-950, salmon 50-700, fjord, kelp, ice, data, traffic, chart, surface 0-4)
2. `frontend/src/app/globals.css` — CSS vars (:root + .dark with ~40 vars each)
3. `frontend/src/styles/tokens.css` — auto-generated from Figma pipeline, 86 tokens
4. `frontend/src/lib/design-tokens.ts` — TS export (86 tokens, same as tokens.css)
5. `frontend/src/styles/theme.ts` — JS mirror of tokens.css

Pipeline: `docs/figma-tokens.json` → `scripts/extract-design-tokens.ts` → tokens.css + design-tokens.ts + theme.ts

### Findings
| Severity | Finding | Location | Effort |
|----------|---------|----------|--------|
| P0 | **Token drift — 4+ parallel sources, no canonical**. `globals.css` has `--text-secondary: #94A3B8` (updated Session 38), but `tokens.css` and `design-tokens.ts` still say `#8899AA`. Any page using CSS var gets new value; any page using `colors.text.secondary` from TS gets old. | globals.css:34 vs design-tokens.ts:51, tokens.css (auto-gen) | L |
| P0 | **145 hardcoded hex colors in 33 .tsx files** bypass the token system. Heavy offenders: feed-cost (11), futures (10), market (10), treatment (10), feed-supply-chain (14), leaders (7). | `rg '#[0-9a-fA-F]{6}' frontend/src --type tsx` | L |
| P0 | **273 rgba() calls in 53 .tsx files** — most are opacity overlays that should be tokenized (glass-light, glass-medium, bg-overlay). BioRiskMap (26), ExposureMap (20), Button (17), OceanBarChart (15), RegionalHeatmap (14). | Systemic | L |
| P1 | **161 inline `style={{...}}` occurrences in 58 files** — even when the color is a CSS var, inline style defeats Tailwind's class-based composition and breaks theme toggling visibility in devtools. | Systemic; worst: RegionalHeatmap, SupplyChainSankey, OnboardingWizard | M |
| P1 | **Chart palette duplicated 4 times** — same 8 chart colors in tailwind.config.ts (chart.1-8), globals.css (--chart-1-8), design-tokens.ts (chartPalette), and tokens.css. Changing chart-3 requires 4 edits. | All token files | S |
| P1 | **`tokens.css` is imported nowhere in the app** — globals.css is the one loaded. tokens.css is a dead artifact from the pipeline that can drift indefinitely. | frontend/src/app/layout.tsx | S |
| P2 | **No spacing scale consistency check** — spacing exists in design-tokens.ts (1-20) but Tailwind uses its own default scale; mixing `p-3` (tw default 12px) with `p-[space-3]` (custom, same value) creates two ways to express the same thing. | Tailwind-wide | S |
| P2 | **No elevation/shadow token scale** — `boxShadow` in tailwind.config.ts defines 6 custom shadows (glass, glow, glow-sm/lg, glow-salmon*, panel) but no numeric elevation 1-5 scale. Developers guess which glow to use. | tailwind.config.ts:92 | M |

### Recommendations
1. **Collapse to 1 source of truth**: Figma tokens → extract-design-tokens.ts → generates ONLY `tokens.css`. Delete globals.css color vars, delete theme.ts, delete design-tokens.ts TS mirror (use CSS vars everywhere via `var(--accent)`). Add CI check that fails build if raw hex `#[0-9a-fA-F]{6}` appears outside tokens.css.
2. **Pre-commit lint**: ESLint rule `no-restricted-syntax` to ban hex literals in .tsx (whitelist tokens.css).
3. **Ban inline `style` for colors**: codemod to convert `style={{ color: '#F59E0B' }}` → `className="text-amber-500"` or `className="text-[var(--color-biomass)]"`.
4. **Unify chart palette**: one array `chartPalette` in tokens.css as CSS vars, import via `getComputedStyle(document.documentElement).getPropertyValue('--chart-1')` for charts.
5. **Delete `tokens.css`** (unloaded dead file) OR delete `globals.css` CSS-var block and load tokens.css instead. Pick one.


## Dimension 2 — Typography system

### Inventory
- **3 font families loaded**: DM Sans (sans, body), DM Serif Display (display, hero), JetBrains Mono (mono, numeric)
- **Type scale in tokens**: xs(12) / sm(14) / base(16) / lg(18) / xl(20) / 2xl(24) / 3xl(30) / 4xl(36) — 8 steps
- **Font weights defined**: regular(400) / medium(500) / semibold(600) / bold(700)
- **Tailwind usage**: 1648 `text-{xs..9xl}` occurrences across 104 files
- **font-mono/display/serif usage**: 271 occurrences across 63 files
- **leading-/tracking- usage**: 326 occurrences across 78 files

### Findings

| Severity | Finding | Location | Effort |
|----------|---------|----------|--------|
| P0 | **Arbitrary text sizes bypass the 8-step scale**: 2695 `text-[...]` arbitrary-value occurrences across 103 files. Heavy: satellite (91), signals (76), market (76), exposure (83), treatment (59+). Common offender: `text-[10px]`, `text-[11px]`, `text-[13px]` — sizes that should not exist. | Systemic. Admin page has `text-[10px]` repeated 9x | L |
| P0 | **Only 69 `tabular-nums` usages** but many more numeric displays exist (KPICard, DataTable, prices, deltas, lice counts, FCR). Proportional digits in prices like "1,234 → 1,567" visibly jiggle when counter animates. | `rg tabular-nums frontend/src` — currently 69, should be on every numeric metric | M |
| P1 | **`font-data`-like semantic role missing**: code references `font-data` in admin/page.tsx lines 448, 719, 741 but there is no `font-data` class in tailwind.config.ts — it silently falls back to default font, breaking the intent to use mono for data. | admin/page.tsx (and possibly others), tailwind.config.ts | S |
| P1 | **No line-height tokens defined**: `leading-` classes use Tailwind defaults (1/none/tight/snug/normal/relaxed/loose) — 326 usages scattered with no semantic mapping (body = 1.5, UI = 1.4, display = 1.1). | Systemic | M |
| P1 | **Display font (DM Serif Display) usage is patchy**: only 271 font-mono/display/serif occurrences total across the whole app, but hero sections on Landing, Dashboard, Farmer-Daily DO use the display font. Inconsistent header treatment — some page `<h1>`s use sans-bold, others use display-serif. | Compare landing/page.tsx vs page.tsx headers | M |
| P1 | **Heading hierarchy unclear** — no `.text-h1`, `.text-h2`, etc. utility or component. Each page ad-hoc picks `text-3xl font-bold` vs `text-2xl font-semibold`. Two pages with the same "H1" visual weight use different classes. | Compare `<h1>` across leaders, trader, market | M |
| P2 | **Mono font not applied consistently to code examples**: api-docs page has code blocks (11 font-mono occurrences) but `inline code snippets` in other pages lack it. | api-docs/page.tsx vs all other docs-adjacent pages | S |
| P2 | **No measure (max-width for reading) rules**: long-form text on Privacy, Changelog, API Docs stretches full 1280px when optimal is ~65ch. No `prose`/`max-w-prose` usage. | privacy/page.tsx, changelog/page.tsx, api-docs/page.tsx | S |
| P2 | **Numerals are not right-aligned in numeric tables by default**: DataTable has `font-mono` only on 2 places; price/volume/percentage columns in leaders/disease/benchmark render with default left-aligned proportional numerals. | DataTable.tsx, leaders/page.tsx | M |

### Recommendations
1. **Lock the scale**: add ESLint rule `tailwindcss/no-custom-classname` or a custom regex rule to ban `text-\[` in .tsx files (whitelist exceptions via `// eslint-disable-next-line`). Migrate all `text-[10px]`/`text-[11px]` to either `text-xs` (12px) or add two new tokens `text-[2xs]:10px, text-[3xs]:9px` if truly needed.
2. **Canonical heading components**: create `<PageTitle>`, `<SectionTitle>`, `<CardTitle>`, `<Eyebrow>` in `components/ui/` with fixed size/weight/leading/tracking. Migrate all pages to use them.
3. **Global `tabular-nums`**: add `.font-numeric { font-variant-numeric: tabular-nums slashed-zero; }` in globals.css; apply to DataTable cells, KPICard metric values, and every ticker/counter.
4. **Fix phantom `font-data`**: define `fontFamily.data: var(--font-mono)` in tailwind.config.ts so `font-data` resolves, OR global replace `font-data` → `font-mono`.
5. **Define line-height tokens**: `leading-body: 1.5`, `leading-ui: 1.4`, `leading-display: 1.15`, `leading-tight: 1.1`. Ban raw `leading-[1.2]`.
6. **Reading measure**: add `.prose-measure { max-width: 72ch }` for Privacy, Changelog, API Docs content.


## Dimension 3 — Color system

### Inventory
- **Semantic tokens (correct layer)**: text-[var(--text-primary)], bg-[var(--surface-1)] — **2,301 usages** across 103 files
- **Brand ramps (correct)**: text-ocean-*, bg-salmon-*, bg-fjord-*, text-kelp-* — **1,696 usages** across 98 files
- **Raw Tailwind colors (leakage)**: text-rose-500, bg-emerald-500, border-amber-400 — heavy usage of stock Tailwind palette. Hard to count precisely vs branded, but treatment/page.tsx alone has 113 raw-color classes.
- **`dark:` utilities**: only 128 occurrences in 18 files. Most files rely on CSS-var switching (`var(--text-primary)`), which works but bypasses Tailwind's dark-mode DX.

### Findings

| Severity | Finding | Location | Effort |
|----------|---------|----------|--------|
| P0 | **Three parallel color systems**: (a) CSS vars via `text-[var(--text-primary)]`, (b) branded ramps `text-ocean-400`, (c) raw Tailwind `text-rose-500`. No rule which to use when. Developer picks randomly. | Systemic | L |
| P0 | **Raw Tailwind palette leaks**: `text-rose-500`, `bg-emerald-500/10`, `border-amber-400` used in place of semantic `text-danger`, `bg-success/10`, `border-warning`. treatment/page.tsx has 113 such uses. When brand color changes, these pages don't update. | treatment, market, satellite, feed-cost, futures | L |
| P0 | **Dark-only assumptions**: 128 `dark:` prefixes spread unevenly. Sidebar has 20, SkeletonCard has 20, but most pages have 0 — they rely on `var()` switching. **Dark-mode toggle exists but pages like `design-system`, `landing`, `api-docs` may not fully flip.** | Systemic; test by toggling theme | L |
| P1 | **Semantic names for data colors are correct but rarely used as tokens**: `--color-biomass`, `--color-lice`, `--color-temperature` exist but pages often use `text-amber-500` (biomass), `text-rose-500` (lice), `text-blue-400` (temp) directly — couples presentation to Tailwind palette instead of domain semantics. | Systemic | M |
| P1 | **Glass opacity levels ad-hoc**: `bg-white/[0.04]`, `bg-white/5`, `bg-white/10`, `bg-white/[0.06]`, `bg-white/[0.08]` — at least 5 different "glass" opacities in use. GlassCard has 3 variants but pages ignore them and apply ad-hoc opacities. | Systemic | M |
| P1 | **No single "danger" / "success" / "warning" utility** — app oscillates between `text-rose-400`, `text-red-500`, `text-danger`, `text-[var(--danger)]`, all for the same semantic role. | Systemic | M |
| P2 | **Traffic-light colors duplicated**: `--color-traffic-green` and `traffic.green` and `bg-green-500` and `bg-emerald-500` all used for the same concept. | TrafikklysIndicator.tsx, traffic-light page | S |
| P2 | **Chart colors applied as hex literals in SVG `stroke`/`fill`** instead of via CSS vars — every chart file (Top50Chart, ForecastCone, InteractiveChart, OceanBarChart, market-inline charts) uses `stroke="#00D4C8"` — theme flip won't recolor. | Systemic to charts | M |

### Recommendations
1. **One rule**: "Never use raw Tailwind colors for semantic roles." Enumerate semantic roles (danger, success, warning, info, positive, negative, muted, accent, brand) and create Tailwind utilities that resolve to CSS vars: `text-danger`, `bg-danger/10`, `border-danger/20`.
2. **Deprecate raw color imports for data**: migrate `text-amber-500` → `text-biomass`, `text-rose-500` → `text-lice`, `text-blue-400` → `text-temperature`. Configure Tailwind to provide these as first-class classes.
3. **Collapse glass opacities to a 3-step ladder**: `glass-subtle` (0.04), `glass-base` (0.06), `glass-strong` (0.10). Ban `bg-white/[0.05]` style one-offs.
4. **Chart SVGs consume CSS vars**: replace every hex literal in chart components with `stroke={`var(--chart-${i})`}` — and verify at runtime via `getComputedStyle` fallback.
5. **Dark-mode QA pass**: toggle to light mode, screenshot every page, file issues for any page with visual regressions. Specific suspects: api-docs, design-system, landing, changelog.


## Dimension 4 — Component inventory

### Inventory
- **50 components** in `frontend/src/components/` (48 root + 2 ui + 6 charts)
- **1 primitive in `components/ui/`**: Button (with ripple, loading, success/error states)
- **6 chart primitives** in `components/charts/`: Button, ChartContainer, ForecastCone, OceanAreaChart, OceanBarChart, OceanTooltip, Top50Chart
- **Biggest components** (LOC proxy by bytes): OnboardingWizard (27KB), BioRiskMap (26KB), Sidebar (22KB), TopBar (19KB), SupplyChainSankey (15KB), InteractiveChart (14KB), ExposureMap (14KB), RegionalHeatmap (13KB), BloomMap (12KB), DataTable (12KB)
- **Avg imports per component**: 3.2 (low — good isolation)

### Findings

| Severity | Finding | Location | Effort |
|----------|---------|----------|--------|
| P0 | **Only 1 primitive (`Button`) in `ui/` folder**. No canonical Input, Select, Checkbox, Radio, Modal, Drawer, Tabs, Tooltip, Popover, Dropdown, Badge (there's `StatusBadge` but it's specific), Breadcrumb. Every page reinvents these patterns. | `components/ui/` has only Button + ChartContainer-related | L |
| P0 | **No Card primitive** — `GlassCard` is the de-facto card but pages use raw `<div className="bg-white/[0.04] backdrop-blur ...">` instead 80+ times. | Systemic (every page rebuilds glass surfaces) | L |
| P1 | **Dashboard extraction incomplete**: page.tsx is now 169 lines (good, post-Session 38), but 4 Dashboard* components (HeroAlert, KPIStrip, LiveIntelligence, Production) are dashboard-specific and live in `components/` root, not `components/dashboard/`. Convention drift. | components/Dashboard*.tsx | S |
| P1 | **No `SectionHeader` / `PanelHeader` primitive** — every page has inline `<div className="flex items-center justify-between mb-4"><h2>...</h2><button>Export</button></div>`. | Systemic | M |
| P1 | **Form primitive gap**: login, settings, webhooks, alert-rules have hand-built inputs with inconsistent styling (`border-white/10` vs `border-[var(--border)]`, `rounded-lg` vs `rounded-md`, `px-3 py-2` vs `px-4 py-3`). | login/page.tsx, settings/webhooks/page.tsx | M |
| P1 | **Map components are 3 separate files that don't share a base**: BioRiskMap (26KB), BloomMap (12KB), ExposureMap (14KB), FarmNetworkMap (8KB). Each duplicates MapLibre setup, color scales, tooltip styling. | components/*Map.tsx | L |
| P1 | **Chart primitives under-used**: chart files exist in `components/charts/` but pages often inline their own SVG (market has 600+ lines of inline SVG chart code). Top50Chart and ForecastCone are examples of good reuse, but not followed. | market/page.tsx, feed-cost/page.tsx, futures/page.tsx | L |
| P2 | **No naming convention boundary**: `DataTable.tsx` (data display), `RegionalHeatmap.tsx` (chart), `KPICard.tsx` (display), `Sidebar.tsx` (nav), `Toast.tsx` (feedback) all mixed at root. | components/ | S |
| P2 | **Big components beg to be split**: OnboardingWizard (27KB), BioRiskMap (26KB), Sidebar (22KB), TopBar (19KB). | Large files | M |

### Recommendations
1. **Stand up `components/ui/` properly**: Build (copy from shadcn/ui or Radix + Tailwind) Card, Input, Select, Checkbox, Modal, Drawer, Tabs, Tooltip, Popover, Dropdown, Badge. Set it as the only source for primitives.
2. **Fold `GlassCard` → `<Card variant="glass">`** — keep the glass visual but make it a variant of a canonical Card.
3. **Folder structure**: move Dashboard* → `components/dashboard/`, *Map → `components/maps/`, charts → `components/charts/` (already done). Root `components/` should hold only cross-page primitives.
4. **Build a `MapBase` primitive** with MapLibre setup, tooltip, legend — BioRisk/Bloom/Exposure/FarmNetwork extend it. Target 80% code reduction across maps.
5. **`SectionHeader`** with title/subtitle/actions/badge slots. Ban inline page-section header div patterns.
6. **Form primitive pass**: `Input`, `Label`, `FieldError`, `FormRow` — migrate all 6 form-bearing pages (login, settings, webhooks, alert-rules, billing, compare).


## Dimension 5 — Data display patterns

### Inventory
- **`lib/format.ts`** exists with `formatDate()`, `formatNumber()`, `formatCurrency()` — locale-aware (en/no)
- **Raw `.toFixed()` calls**: 319 occurrences across 55 files — these bypass the locale formatter
- **Correct locale formatters**: 295 `formatNumber/formatCurrency/formatDate` usages in 31 files
- **Raw `.toLocaleDateString`/`toLocaleString`**: 62 occurrences still — should all go through `formatDate`
- **Numeric/currency function calls total**: 647 (spanning formatters + raw)

### Findings

| Severity | Finding | Location | Effort |
|----------|---------|----------|--------|
| P0 | **319 raw `.toFixed()` calls bypass locale formatting** — Norwegian users see `92.50` not `92,50`. Per Session 28 log, 15 pages were migrated, but 40+ pages still have raw toFixed. Worst: satellite (20), market (16), price-outlook (1 but should be more), contracts (16), harvest (21), farmer (11), exposure (17), predictions (15), climate (17), investor (10). | Systemic — migration incomplete | L |
| P0 | **62 raw `toLocaleDateString`/`toLocaleString(...)` calls** — 9 of Session 28c's "migrated" pages still have these. | iceland (7), lice-quota (7), admin (5), etc. | M |
| P0 | **No unit-aware display primitive** — every page reinvents "NOK 89.3/kg" or "1,234 tonnes" or "0.42 lus/fisk". Should be `<Metric value={89.3} unit="NOK/kg" />` with unit ellipsis, tabular-nums, and sign coloring. | Systemic | M |
| P1 | **Deltas inconsistent**: some pages show `+12.4%` in green, others `12.4% ↑`, others just `12.4` with no sign. Arrow-vs-sign is mixed across KPICard (arrow), DashboardHeroAlert (sign), predictions (plain number). | KPICard.tsx, DashboardHeroAlert.tsx, predictions/page.tsx | S |
| P1 | **Missing/NaN handling patchy**: some pages show "—", some show "N/A", some show "0", some show "NaN". No single `DataGap` primitive. | Systemic; format.ts uses "—" but raw toFixed paths don't | S |
| P1 | **No sparkline primitive** — market page and feed-cost page each inline their own SVG sparklines (~50 lines each). Should be `<Sparkline data={...} trend="up|down|flat" />`. | market/page.tsx, feed-cost/page.tsx, trader/page.tsx | M |
| P1 | **Confidence intervals rendered differently per page**: some pages show shaded band (good — ConfidenceBand.tsx), others show upper/lower as text "80-105 NOK/kg", others show p10/p90 markers. | price-outlook, predictions, ml-baselines | M |
| P2 | **Freshness indicator variance**: `FreshnessIndicator.tsx` exists but "Last updated 2m ago" text is hand-rolled in many places. | Sidebar, DashboardKPIStrip, various pages | S |
| P2 | **Data provenance format drift**: `DataQualityBadge` exists (44/63 pages) but 19 pages still hand-roll source/confidence footers. | ~19 pages without DataQualityBadge | S |
| P2 | **No uncertainty legend primitive**: confidence bands assume users know what "80% CI" means — no tooltip/explainer in most places. | price-outlook, predictions | S |

### Recommendations
1. **Codemod `.toFixed()` → `formatNumber()`**: build a jscodeshift transform. `(x).toFixed(2)` → `formatNumber(x, locale, 2)`. Requires locale in scope (most pages have useTranslation already).
2. **Ban raw `toLocaleDateString`**: codemod to `formatDate()`. 62 sites.
3. **`<Metric>` primitive**: props `value`, `unit`, `precision`, `sign` (+/−/auto), `size` (sm/md/lg), `trend` (up/down/flat via color), `emphasis` (default/hero). Renders tabular-nums by default. Migrate KPICard internals to use it.
4. **`<Delta>` primitive**: always shows sign, arrow optional via prop, color from semantic tokens, respects direction-matters semantics (higher-is-better vs lower-is-better).
5. **`<Sparkline>` primitive** (50-line SVG, d3-shape or pure path calc): trend-colored, last-value dot.
6. **`<ConfidenceBand>` is already a primitive — expand adoption** to price-outlook, predictions, ml-baselines.
7. **`<DataGap>` primitive** for missing values: returns "—" with tooltip "No data available for this period".


## Dimension 6 — State coverage

### Inventory
- **63/63 pages have `loading.tsx`** (all use `SkeletonDashboard`)
- **62/63 pages have `error.tsx`** (all use `SegmentError` wrapper)
- **Only 1 `not-found.tsx`** at app root
- **ErrorBoundary / SkeletonCard / EmptyState / PageLoader usage**: 237 occurrences in 85 files (Session 38 sweep took these to 60/63 pages for ErrorBoundary)
- **Loading-state state variables (isLoading, pending, loading prop)**: 148 occurrences in 52 files
- **Canonical empty-state component**: `EmptyState.tsx` exists but used in only ~5 files

### Findings

| Severity | Finding | Location | Effort |
|----------|---------|----------|--------|
| P0 | **All loading.tsx files render the same `SkeletonDashboard`** — a generic KPI-card skeleton that doesn't match page layouts. Tables, maps, charts all show the same 6 card skeletons then hard-snap to their real layout. Poor perceived performance. | 63 loading.tsx files, all identical | L |
| P1 | **No explicit empty-state pass**: pages handle "no data" inconsistently. Some show "No data available" text, some show blank, some show charts with empty arrays that render collapsed. `EmptyState` exists but is used rarely (~5 files of 63). | Systemic | M |
| P1 | **No 404 for sub-routes** — only one `not-found.tsx` at the app root. Invalid `/farmer/invalid-id` paths get the generic 404 instead of contextual "Locality not found" state. | frontend/src/app/not-found.tsx only | M |
| P1 | **Error.tsx are all identical wrappers to `SegmentError`** — no page-specific recovery actions (e.g., treatment page could offer "Return to farm dashboard", market page could offer "Try again in 30s"). Generic error message. | 62 error.tsx files | M |
| P1 | **Partial-failure UX missing**: each page fetches 3-10 APIs. When one fails, most pages show entire page empty instead of "this one section failed". Per-section skeleton/error not modeled. | Systemic; app/page.tsx does this better via sectional try/catch | L |
| P1 | **Loading flicker**: loading.tsx plus per-section isLoading state produces double-skeleton (page-level then section-level). | page.tsx, farmer-daily/page.tsx | S |
| P2 | **No optimistic UI** on mutations (save scenario, log treatment outcome, dismiss alert, mark notification read) — all block until server responds. | scenarios-lab, farmer-daily, notifications | M |
| P2 | **No stale-while-revalidate indicator**: when data is cached and refreshing in background, user has no signal. FreshnessIndicator exists but isn't wired per-section. | Systemic | S |

### Recommendations
1. **Per-shape skeletons**: build `<KPISkeleton>`, `<TableSkeleton rows={N}>`, `<ChartSkeleton>`, `<MapSkeleton>`. Compose into page-specific loading.tsx files (farmer-daily gets KPI + chart + timeline skeleton; market gets KPI + big chart skeleton).
2. **Section-level ErrorBoundary + fallback**: wrap each `<GlassCard>` with a `<SegmentBoundary label="Disease">` that catches errors locally and renders a retry button without taking down the whole page.
3. **`<EmptyState>` adoption pass**: audit all 63 pages for "no data" paths and wire `<EmptyState icon={...} title={...} action={...} />`.
4. **Page-typed 404**: `/farmer/[id]/not-found.tsx`, `/company/[name]/not-found.tsx` — contextual messages.
5. **Optimistic UI**: use React 19 useOptimistic for save/log/mark-read mutations.
6. **SWR/stale indicator**: when cached data is served, show small "Refreshing…" chip in FreshnessIndicator.


## Dimension 7 — Norwegian i18n

### Inventory
- **`lib/i18n.ts`** is 884 lines with **~588 key pairs** (EN/NO) — exceeds the "525 keys" claim in CLAUDE.md
- **`useTranslation`/`t(...)` calls**: 843 occurrences in 67 page files (all 63 pages + 4 components)
- **Norwegian special characters** (ø/æ/å/ô) in i18n.ts: **100 occurrences** — properly encoded
- **Industry terminology matches**: 106 occurrences of biomass/biomasse/fôrfaktor/lusegrense/MTB/merd/lakselus/sjolus across 24 files
- **Locale-aware date/number formatters** wired into both format.ts AND i18n.ts (duplication — see Finding)

### Findings

| Severity | Finding | Location | Effort |
|----------|---------|----------|--------|
| P0 | **Duplicate formatter definitions**: `formatNumber`/`formatCurrency`/`formatDate` exist in BOTH `lib/format.ts` AND `lib/i18n.ts` (lines 10-24). Pages import from either randomly. Code duplication + drift risk. | lib/format.ts vs lib/i18n.ts | S |
| P1 | **Norwegian industry terms used as ENGLISH labels in translations**: `"MTB"` (Maksimalt Tillatt Biomasse) and `"merd"` (pen) are pure Norwegian but appear in English strings too. Unclear whether to translate or keep loanwords. Need style guide. | Systemic; audit 100 term occurrences | S |
| P1 | **26 bare English button labels in `.tsx`**: "Save", "Cancel", "Delete", "Refresh" hardcoded despite translation keys existing. Likely i18n onboarding gaps in newer pages. | satellite (2), insurance (2), and 24 other files | M |
| P1 | **No pluralization rules**: "1 farm" vs "2 farms" — Norwegian "1 anlegg" vs "2 anlegg" (no change) has different grammar than English. No Intl.PluralRules integration. | Systemic | M |
| P1 | **No relative time translations**: "2 hours ago", "just now", "yesterday" mostly hardcoded English. No `formatRelative()` helper. | FreshnessIndicator, dashboard, notifications | M |
| P2 | **No locale-specific number sign placement**: Norwegian writes percentages as "12,5 %" (with space); English as "12.5%". Current formatter doesn't handle this. | Intl has unit format but it's not used | S |
| P2 | **Landing page mostly English-only**: `landing/page.tsx` has only 2 `t()` calls yet extensive English copy. Marketing content is not translated. | landing/page.tsx | M |
| P2 | **Changelog content is English-only** (release notes in prose). No NO version. | changelog/page.tsx | M |
| P2 | **Status labels not always via `t()`**: "Live", "Stale", "Simulated", "Online", "Offline" sometimes hardcoded. | FreshnessIndicator, StatusBadge, TopBar | S |

### Recommendations
1. **Pick one formatter location** — keep `lib/format.ts`, delete the 3 copies in `lib/i18n.ts`. Update imports.
2. **Norwegian style guide addendum** (1-page doc): loanwords kept (MTB, ISA, PD, lakselus, merd, biomasse), translations for UI chrome (Save→Lagre, etc.). Commit to `docs/i18n-style-guide.md`.
3. **Codemod hardcoded chrome**: replace `<button>Save</button>` with `t("common.save")` — scan the 26 offender files.
4. **Add `formatRelative()` to format.ts**: use `Intl.RelativeTimeFormat` with `_localeMap`. Replace hardcoded "2h ago" across FreshnessIndicator, notifications.
5. **Add `formatPercent()` to format.ts**: use `Intl.NumberFormat` with `style: "percent"` — get the " %" spacing right for Norwegian.
6. **Marketing i18n pass**: landing + changelog need Norwegian translations for Norwegian-market credibility.


## Dimension 8 — Accessibility

### Inventory
- **ARIA attributes** (aria-label/labelledby/describedby/live/expanded/hidden/sort/current/invalid/role): 145 occurrences in 35 files
- **Keyboard handlers** (tabIndex / onKeyDown/Up/Press): 22 occurrences in 14 files — mostly the 6 SVG components fixed in Session 38
- **onClick handlers**: 281 occurrences across 82 files (many on buttons, some on div/span)
- **skip-to-content link**: exists in `app/layout.tsx`
- **Focus-visible state**: `globals.css` has `:focus-visible` styles (verify)

### Findings

| Severity | Finding | Location | Effort |
|----------|---------|----------|--------|
| P0 | **Color-only semantics on deltas**: up-arrow/down-arrow in KPICard rely on color alone (green/red) with text sign. Colorblind users miss the signal. Sign character (+/−) + arrow icon both needed. KPICard has screen-reader text (session log note) but many KPI-adjacent inline chips don't. | KPICard.tsx, Dashboard*.tsx, leaders/page.tsx | M |
| P0 | **Charts have no `aria-label` / data table alternative**: InteractiveChart.tsx, Top50Chart.tsx, RadarChart.tsx, OceanBarChart.tsx have minimal ARIA (img role, title) but no `<figcaption>` or hidden-to-visual data table for screen readers. | All chart components | L |
| P1 | **Form inputs without labels**: login form has aria-label=none on some icon-only inputs. Settings/webhooks has inputs where label is a sibling span not `<label htmlFor>`. | login/page.tsx, settings/webhooks/page.tsx | M |
| P1 | **Modal/dialog without focus trap**: ShortcutsHelp, OnboardingWizard, GuidedTour are modal-like but no `role="dialog"` with focus trap / inert rest-of-page / Escape handler. | ShortcutsHelp.tsx, OnboardingWizard.tsx, GuidedTour.tsx | M |
| P1 | **Live regions missing**: Toast/notifications should have `role="status"` or `role="alert"` so screen readers announce; currently relies on visual only. Toast has a generic role, but per-toast variants (error vs info) need distinct politeness. | Toast.tsx | S |
| P1 | **Heading outline skips**: dashboard jumps `<h1>` → `<h3>` skipping h2. Axe/Lighthouse would flag this. | page.tsx and others | S |
| P1 | **Heatmap clickable cells keyboard-invisible in some charts**: ConfidenceBand + RadarChart now have focus handlers (Session 38), but MiniHeatmap, ExposureMap (SVG), BloomMap, BioRiskMap overlays still have mouseover without focus equivalents. | *Map.tsx, MiniHeatmap.tsx | L |
| P2 | **Contrast on disabled/muted text** potentially below 4.5:1: `--text-secondary: #94A3B8` on `--bg-primary: #060F1C` is ~8.6:1 ✅ but secondary on card `#0A1629` is ~8.0:1 ✅; lower-opacity text like `text-[var(--text-secondary)]/60` drops to ~5:1 (borderline AA). | Changelog, login, many muted labels | M |
| P2 | **Reduced-motion not honored**: framer-motion animations don't check `prefers-reduced-motion`. | Systemic | S |
| P2 | **No accessible table headers** on non-DataTable tables: several pages use raw `<table>` without `scope="col"` / `scope="row"`. DataTable correctly sets them. | hand-rolled tables across ~10 pages | M |

### Recommendations
1. **Reduced-motion global**: add to `globals.css`:
   ```css
   @media (prefers-reduced-motion: reduce) {
     *, *::before, *::after { animation-duration: 0.001ms !important; transition-duration: 0.001ms !important; }
   }
   ```
2. **Chart accessibility**: wrap every chart in `<figure role="img" aria-labelledby="...">` with `<figcaption>` summary and a visually-hidden `<table>` with the raw data.
3. **Modal primitive**: build `<Modal>` in `components/ui/` using Radix Dialog (or custom) — role=dialog, aria-modal=true, focus trap, ESC to close, scroll-lock body.
4. **Live-region `<Toast>` variants**: `role="alert"` for errors, `role="status"` for info, aria-live="polite" for success.
5. **Form primitive with `<Label htmlFor>` inside**: make it impossible to ship a field without a label.
6. **Heading outline pass**: lint via eslint-plugin-jsx-a11y `heading-has-content` + rule `jsx-a11y/heading-order` (or lint yourself) to ensure h1→h2→h3.
7. **SVG map ARIA**: wrap svg in `role="application"` with aria-description, add `<desc>`, ensure each region is reachable by keyboard (tabIndex={0}).


## Dimension 9 — Motion and interaction

### Inventory
- **framer-motion usage**: 545 occurrences across 81 files — heavily adopted
- **Custom durations defined in code** (duration: N or duration-N): 114 occurrences in 51 files
- **Magic millisecond values** (`\b\d{2,4}ms\b`): only 2 occurrences (useValueFlash, admin) — good
- **Tailwind transition classes**: 120 occurrences across 57 files
- **Motion tokens**: **NONE defined** in tailwind.config.ts, design-tokens.ts, or globals.css — no duration/easing tokens

### Findings

| Severity | Finding | Location | Effort |
|----------|---------|----------|--------|
| P0 | **No motion tokens**: no `--duration-fast`, `--duration-base`, `--ease-out`, `--ease-in-out`. framer-motion configs are inline — each component picks its own. Session 28 note confirms animations are on every page; consistency is impossible without tokens. | Systemic (tailwind.config.ts, globals.css) | M |
| P1 | **Duration values scattered**: `transition={{ duration: 0.3 }}` in KPICard, `0.4` in GlassCard, `0.5` in DashboardHeroAlert, `0.2` in Button, `0.6` in Toast. No rationale. | 114 files with hand-picked durations | M |
| P1 | **Page-entry animations repeated on every page**: most pages wrap content in `<motion.div initial={{opacity:0, y:16}} animate={{opacity:1, y:0}}>` — this boilerplate should be a `<PageTransition>` wrapper. | Systemic | M |
| P1 | **No spring-vs-tween convention**: some animations use `spring` (drag), others `tween` (fade). Arbitrary. | framer-motion call sites | S |
| P1 | **React Compiler note**: per CLAUDE.md, React Compiler is ON — but framer-motion on every page forces "use client". RSC benefits lost. Not a motion bug but a cost attributable to motion. | All pages | L (architectural) |
| P2 | **Hover-only affordances**: many interactive SVG regions (maps, heatmaps) only reveal data on hover. No focus-visible equivalent in some (partially fixed Session 38). | ExposureMap, BloomMap, BioRiskMap | M |
| P2 | **No consistent "value changed" animation**: `useValueFlash` exists but used only in admin. Numeric counters elsewhere hard-update without any visual cue. | Systemic | S |
| P2 | **Dashboard auto-refresh has no visual confirmation**: every 60s data refreshes silently (useDashboardData). Users miss it. | useDashboardData.ts | S |

### Recommendations
1. **Motion tokens in `:root`**:
   ```css
   --duration-instant: 60ms;
   --duration-fast: 120ms;
   --duration-base: 200ms;
   --duration-slow: 320ms;
   --ease-out: cubic-bezier(0.16,1,0.3,1);
   --ease-in-out: cubic-bezier(0.4,0,0.2,1);
   --ease-spring: spring(1, 80, 10, 0);  /* for framer */
   ```
   Export as JS constants for framer-motion imports.
2. **`<PageTransition>` primitive** wraps page content with standard fade+rise.
3. **Codemod framer transitions to token-based**: `transition={{ duration: 0.3 }}` → `transition={motion.base}`.
4. **`useValueFlash` expansion**: apply to SSB price in TickerStrip, lice counts in KPICard, any polling value.
5. **Visual refresh cue**: FreshnessIndicator fades to green → grey on successful refresh.
6. **Reduced-motion honoring** (already in Dimension 8): framer-motion has `useReducedMotion` hook — apply globally via `<MotionConfig reducedMotion="user">` at layout level.


## Dimension 10 — Responsive and density

### Inventory
- **Responsive prefixes** (`sm: md: lg: xl: 2xl:`): 306 occurrences across 78 files
- **Grid/flex layout classes**: 341 occurrences across 88 files
- **Padding/gap classes** (p-*, gap-*, space-*): 2,951 occurrences across 116 files
- **Viewport/sizing classes** (w-screen, max-w-, min-h-screen, h-screen): 95 occurrences across 52 files
- **Mobile hamburger menu in Sidebar** — confirmed in CLAUDE.md
- **`ResponsiveGrid.tsx` component** exists as helper

### Findings

| Severity | Finding | Location | Effort |
|----------|---------|----------|--------|
| P0 | **No density mode**: only one density ("comfortable"). Bloomberg-style dense mode (smaller padding, tighter rows) absent — critical for trader/analyst personas with multiple dashboards open. | Systemic | L |
| P1 | **Responsive prefix usage is uneven**: landing (20 responsive), design-system (4), admin (5), trader (3), leaders (1). Pages like `leaders` and `trader` likely overflow on mobile since they have heavy tables. | leaders/page.tsx (1 sm/md), trader/page.tsx (3) | M |
| P1 | **Fixed-width layouts without `overflow-x-auto`**: DataTable doesn't set min-width per column, so wide tables cause horizontal body scroll instead of internal scroll. | DataTable.tsx | S |
| P1 | **Sidebar fixed at 240px**: `md:ml-[240px]` — not resizable, not collapsible to icon-only dense mode. Bloomberg users expect collapsible chrome. | Sidebar.tsx, layout.tsx | M |
| P1 | **No grid-area / grid-template-areas for dashboard layout**: page.tsx assembles sections in flow order; moving sections requires editing JSX. For a "customizable dashboard" persona this is a blocker. `DashboardCustomizePanel` exists but doesn't use CSS grid-template-areas. | page.tsx, DashboardCustomizePanel.tsx | M |
| P2 | **Mobile KPI strip overflow**: 4 KPI cards on a 375px screen = 94px each → numbers truncate. Should stack 2×2 or scroll. | DashboardKPIStrip.tsx | S |
| P2 | **Modal/dialog stacking on mobile**: OnboardingWizard, ShortcutsHelp overflow viewport on small screens. | OnboardingWizard, ShortcutsHelp | S |
| P2 | **Map heights fixed in pixels**: BioRiskMap, BloomMap use `h-[600px]` — doesn't adapt to short laptop screens (13" = ~768px total). | *Map.tsx | S |
| P2 | **No container queries usage**: `@container` queries would help components adapt based on their parent, not viewport. None detected. | Systemic | M |

### Recommendations
1. **Density mode toggle**: `data-density="compact|comfortable"` on root. Compact shrinks padding tokens (p-4 → p-2), row heights, KPI font. Persist in localStorage alongside theme.
2. **Responsive sweep**: add `sm:` + `md:` breakpoints to all tables (stack-to-horizontal at md+), hide non-essential columns on mobile via `hidden md:table-cell`.
3. **DataTable `overflow-x-auto`**: wrap table in scroll container with min-width.
4. **Sidebar collapsible**: icon-only mode (60px) with tooltip. Persist.
5. **Dashboard grid-template-areas**: convert `<DashboardKPIStrip />` etc. into grid children with named areas. DashboardCustomizePanel writes area names to localStorage.
6. **Container queries**: convert KPICard + GlassCard to `@container` so they reflow based on their grid cell width, not the viewport.
7. **Map `h-[60vh]` or `aspect-video`**: use viewport- or aspect-based heights.


---

## Final findings tally

- **P0: 17** (blocking — token drift, hardcoded colors, arbitrary type sizes, raw toFixed, single skeleton, unauth'd primitives, etc.)
- **P1: 42** (important — inline styles, tabular-nums, form primitives, partial-failure UX, responsive gaps, motion tokens)
- **P2: 18** (nice-to-have — code cleanup, chart SVG tokenization, relative time i18n, container queries)

---

## Token consolidation plan

### Add (new canonical tokens)
| Token | Purpose | Value example |
|-------|---------|---------------|
| `--text-2xs` / `text-2xs` | 10px type | 0.625rem |
| `--text-3xs` / `text-3xs` | 9px type (charts only) | 0.5625rem |
| `--duration-instant` | 60ms | micro-animations |
| `--duration-fast` | 120ms | button hover |
| `--duration-base` | 200ms | standard fade/rise |
| `--duration-slow` | 320ms | modal enter |
| `--ease-out` | cubic-bezier(0.16,1,0.3,1) | entrance |
| `--ease-in-out` | cubic-bezier(0.4,0,0.2,1) | symmetric |
| `--elevation-1..5` | layered shadows | replace 6 ad-hoc shadow tokens |
| `--glass-subtle`, `--glass-base`, `--glass-strong` | 3-step opacity | replace 5+ ad-hoc opacities |
| `--leading-body` 1.5 / `--leading-ui` 1.4 / `--leading-display` 1.15 | type rhythm | — |

### Rename
| From | To | Reason |
|------|-----|--------|
| `chart-1..8` (duplicated) | single source via CSS vars, imported by `chartPalette.ts` | de-duplicate |
| `data.biomass/lice/temp/mortality/feeding/oxygen` | `domain.biomass` etc. | clarify non-chart semantics |
| `traffic.green/yellow/red` | Keep, but ensure consistent with stock Tailwind `green-500`/etc. | prevent drift |

### Remove / merge
- **Remove** `frontend/src/styles/tokens.css` (unloaded)
- **Remove** `frontend/src/lib/design-tokens.ts` as runtime source (keep only as Figma-sync artifact)
- **Remove** `frontend/src/styles/theme.ts` (unused JS mirror)
- **Keep** `frontend/tailwind.config.ts` + `frontend/src/app/globals.css` as the only two files developers edit. Everything else is generated.

---

## Component refactor list (ordered by impact × pages affected)

| # | Component / primitive | Impact | Pages affected |
|---|----------------------|--------|----------------|
| 1 | `<Card>` (Radix or shadcn-style, replace GlassCard + inline divs) | High | ~60 |
| 2 | `<Metric>` (number + unit + precision + sign + trend) | High | ~40 |
| 3 | `<Input>`, `<Label>`, `<FieldError>`, `<FormRow>` | High | 6 (login, settings, webhooks, compare, scenarios-lab, billing) |
| 4 | `<Modal>` (Dialog w/ focus trap, ESC) | High | 3 modals → all future modals |
| 5 | `<PageTransition>` wrapper | Medium | ~60 |
| 6 | `<SectionHeader>` with title/actions slots | Medium | ~60 |
| 7 | `<Delta>` (sign + arrow + color) | Medium | ~20 |
| 8 | `<Sparkline>` | Medium | ~6 (market, feed-cost, trader, predictions, leaders KPI cells) |
| 9 | `<EmptyState>` adoption | Medium | ~30 pages with data-gap branches |
| 10 | `<MapBase>` shared MapLibre setup | High | 4 (BioRisk, Bloom, Exposure, FarmNetwork) |
| 11 | `<KPISkeleton>`, `<TableSkeleton>`, `<ChartSkeleton>`, `<MapSkeleton>` | Medium | 63 loading.tsx files |
| 12 | `<Tooltip>`, `<Popover>`, `<Dropdown>` (Radix) | Medium | ~20 |
| 13 | `<Tabs>` primitive | Medium | ~8 |
| 14 | Density toggle (data-density) | High | Global |
| 15 | Responsive sweep on DataTable | High | ~10 table-heavy pages |

---

## Figma session input — top 20 design decisions needed

Ordered by blocking-ness. Each decision becomes a Figma component variant or token.

1. **Canonical color ramps**: pick a single brand base (ocean 50-950), single accent (salmon 50-700), and a 3-step neutral for surfaces. Delete the extras.
2. **Type scale**: lock to 8 steps (10 / 12 / 14 / 16 / 18 / 20 / 24 / 30 / 36). Decide whether 10px and 11px both survive.
3. **Typeface pairings**: keep DM Sans + DM Serif Display + JetBrains Mono. Define which H levels use the serif display (H1 only? H1+H2?).
4. **Semantic color roles**: define `danger`, `success`, `warning`, `info`, `positive`, `negative`, `muted`, `accent`, `brand` as the ONLY ways to express intent. Raw Tailwind `rose/emerald/amber` banned.
5. **Motion tokens**: 4 durations (instant/fast/base/slow) + 3 easings (out/in-out/spring). Framer + Tailwind both read from them.
6. **Elevation scale**: 5 levels (ground / raised / overlay / dialog / popover) with paired shadow + blur + background opacity.
7. **Glass opacity ladder**: 3 levels (subtle 4% / base 6% / strong 10%). Delete the 5 ad-hoc opacities.
8. **Density modes**: comfortable vs compact. Padding scale for each.
9. **Card variants**: base / glass / elevated / outlined / muted. Fold GlassCard into `<Card variant="glass">`.
10. **Metric component**: size (sm/md/lg/hero), sign (auto/+/−), unit placement, tabular-nums always on.
11. **Delta pill**: shape, sign+arrow rules, direction-matters (higher-is-better vs lower-is-better).
12. **Heading system**: H1/H2/H3/H4/Eyebrow/Caption as named components.
13. **Form controls**: Input, Select, Checkbox, Radio, Switch, TextArea — sizes (sm/md), states (default/hover/focus/error/disabled).
14. **Button variants**: primary / secondary / ghost / danger / success + 3 sizes. Ensure loading + success + disabled states.
15. **Data states**: define Loading (skeleton shape), Empty (icon + copy + action), Error (icon + message + retry), Stale (freshness chip), Synthetic (badge).
16. **Chart style guide**: axis color, gridline style, tooltip, legend, confidence band appearance, missing-data treatment.
17. **Map style guide**: base tile style, region fill ramps for lice / disease / bloom, tooltip card, legend.
18. **Table patterns**: header style, row density, sort indicators, sticky header, column types (numeric right-align, status chip, company name).
19. **Sidebar dimensions**: expanded 240px vs icon-only 60px. Animation between. Tooltip on hover when collapsed.
20. **Mobile breakpoint behavior**: 3 patterns (stack KPI 2×2 / hide non-essential table columns / hamburger sidebar) documented as a responsive guide.

---

## Executive summary

OpenClaw/FishIntel has substantial design plumbing — a Figma token pipeline, 86 tokens, a dark/light theme, 48 components, an i18n system with ~588 Norwegian/English key pairs — but **four parallel token sources drift**, **145 hex colors and 2,695 arbitrary `text-[...]` sizes** leak outside the system, and **319 raw `.toFixed()` calls** still bypass locale formatting after Session 28's partial migration. The `ui/` primitive folder has only `Button`, so every page reinvents Card, Modal, Input, Tabs. All 63 pages share one generic skeleton, which hard-snaps to very different layouts. Motion is heavily used (545 framer-motion calls) with zero shared duration/easing tokens. There is no density mode, which blocks a real trader persona. These are fixable by consolidating to **one** tokens source (`tokens.css`), standing up `components/ui/` properly, and running three codemods (hex → tokens, `.toFixed` → `formatNumber`, `text-[...]` → scale). The Figma session should lock the 20 decisions listed above; everything downstream is mechanical.

