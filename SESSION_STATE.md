CURRENT: WS-28a + WS-30–34 shipped (2026-10-18) — see docs/HANDOVER.md §5
LAST_UPDATED: 2026-10-18
SESSIONS: 38+ (15 commits pushed; WS-29 and the WS-28a/30–34 round pending commit)
REPOSITORY: https://github.com/frehan83-collab/AquaIntel (public)
HANDOVER: docs/HANDOVER.md — verified state, gate commands, workstream backlog WS-1..WS-34b, trap list (23 traps)
VERSION: 2.6.0 · 348 paths · 1334 tests collected · 21 migrations (head 021)

## WS-28a + WS-30–34 (2026-10-18) — fix before add

Research (satellite/HAB prices, data licences, decision-grade HAB science) + a
three-lens council. The council rejected a new finer-grained satellite product and
ordered: remove fabrication, fix the bloom surface, license the FX, then add dated
context.

- **WS-32** satellite honesty: seeded-RNG simulator deleted, no scene = no reading
  (`n_readings_verified`, `scene_dates`, `missing_reason`), `is_live` from verified
  scenes, NDVI relabelled surface scum, catalogue drops the fabricated products,
  provenance on all `/api/satellite/*`. 8 tests.
- **WS-33** bloom truth: `/bloom` crash fixed, freshness from the newest observation
  (196 days → degraded with age), dead self-compared trend fixed + **Alembic 021**
  (nulls 123 045 rows, relabels 842 undeliverable alerts `legacy_unknown`), alert
  delivery statuses, real Mattilsynet disease count, brief counts distinct localities.
  17 tests + migration test.
- **WS-34** bloom context: `/api/bloom/context` — dated IMR Algestatus link (no API),
  three sourced mortality events, five stated limits.
- **WS-28a** one gate (`equity_signals.may_persist_directional`) stops four agents
  writing trade directions on listed shares. 14 tests.
- **WS-30** ROI calculator: claim inputs default to zero, break-even reported
  (`benefit_needed_nok`) instead of a 228x/1 693x multiple. 17 tests.
- **WS-31** FX from official Norges Bank rates (Yahoo FX removed, licence), fallbacks
  recorded, attribution footer + FRED notice. Open: Yahoo equity/commodity quotes.
- Docs: `docs/DATA_SOURCES_COST.md` (prices and licences, the answer to "what does
  satellite/algae data cost"). Open: WS-31b, WS-29b, the remaining WS-22 numbers.

## WS-29 (2026-10-18) — the weekly margin bridge
`core/market/margin_bridge.py` (method 1.0.0) + `GET /api/margin/bridge[/{locality_no}]`
+ `MarginBridgePanel` on `/feed-cost`: price leg minus four grouped cost legs per kg,
what moved (price week on week, feed month on month), break-even with the feed cut or
FCR that closes it, five levers with formulas, an assumption register, reconciliation
against the feed engine's total, and a validation check against the audited 2024 feed
cost. Honest state: `margin.quality` is `modelled` by default; the FRED feed basket's
newest point is 2026-07 (degraded, month named) and the level calibration is open as
WS-29b. Also fixed: `/feed-cost` stamped the *fetch* time as the price date, the
decision card valued lost biomass at a hardcoded 95.0 NOK/kg instead of the live SSB
spot, and live FRED ingredient rows were labelled "EST". Read `docs/MARGIN.md`.

## SESSIONS 38+ — COMMERCIAL HARDENING (see docs/HANDOVER.md §3 for the per-area docs)

Commits: `5bd843a` entitlements SSOT (one plan table; paywall enforced; 402 + upgrade
payload) · `9ebb03d` money path proven end to end (catalog → checkout → webhook →
entitlement → previously-blocked route now passes; mock mode; schema-drift fix) ·
`7ef15e6` AI-STI + AI-LPI (method v1.0.0) + Bio→Price Weekly + immutable history ·
`83097c7` Accuracy & Method as a tracked artifact store (refuses demo-only data) ·
`d38f441` production truth: agents as a real service, deploy-gating verifier (found +
fixed an empty `alembic_version`), 12-source freshness dashboard, migration-016 `%s`
bug fixed · `03aecb9` design partners (pilots as real entitlements) · `914875a` legal:
licence register (0 of 8 cleared, stated), advice boundary, AI Act, DPA scaffold,
deferred perf fee · `eec190e` provenance register + ratchet + 5 routes ·
`92cefdb` GTM kit + ROI calculator + roles · `54114ee` ratchet anchored to the frozen
contract · `fd5ca49` first REAL accuracy artifact (MAPE 13.42%, coverage 92.1%, n=208)
+ `W42` parser fix · `f04e79a` index lineage guard (stopped a false `is_live` claim on
unverifiable lice rows).


## SESSION 33 — QUALITY ELEVATION + DESIGN COMPONENTS

### Commit: 108e611
- Fix /api/market/price-outlook 500 → 4-phase graceful degradation
- 50 new tests (conftest.py, 10 engine suites, price-outlook resilience)
- Dynamic imports on 8 chart-heavy pages
- Design tokens wired into 13 components
- 5 new Figma-inspired components: ProgressRing, TickerStrip, BentoGrid, AnimatedGauge, MiniHeatmap
- Mobile polish (DataTable scroll, touch targets, responsive grids)
- Deployment prep (GHCR, Playwright CI, health checks, staging compose)

## SESSION 34 — SECURITY + COMMERCIAL + ACCESSIBILITY

### Commits: 74534c0, 088b7d8
- Auth rate limiting: /register 5/min, /login 10/min
- 26 bare except:pass → structlog warnings
- DB indexes on Signal/Order/Subscription (Alembic 014)
- US tariff impact banner, EUDR countdown, trade flow shifts
- ProgressRing on welfare + ASC, TickerStrip on dashboard
- WCAG aria-labels on 6 pages
- DataQualityBadge on 24/65 pages (was 9)

## SESSION 35 — DESIGN EXCELLENCE + FIGMA PIPELINE

### Commits: 28001a4, e14ba33, 3c68d76
- Figma API build pipeline: sync_figma_tokens.py, npm scripts, CI verification
- Dashboard hero KPI (2fr spot price, asymmetric grid)
- Micro-interactions: flash-update, card-hover, alert-critical-pulse CSS
- useValueFlash hook wired into KPICard
- Content-shaped skeleton loaders (4 variants + shimmer animation)
- EmptyState component (5 variants with ocean SVG illustrations)
- Market page: TickerStrip + professional country code badges (replaced emoji flags)
- Farmer Daily: AnimatedGauge for lice level danger signal

## SESSION 36 — WIRE UNUSED API ENDPOINTS

### Commit: 8c1cbe4
- Supply Forecast: smoltForecast + cohortTimeline wired
- Global Supply: biomassNational wired (standing biomass KPIs)
- Climate: marineHeatwaveRisk wired (PA-level status cards)
- Signals: anomalyAlerts wired (Early Warning section)
- Canada: canadaLice wired (national lice trends)

## SESSION 37 — DATA SOURCE EXPANSION (7 NEW CLIENTS)

### Commits: 9c2d4fe, aa330e1
- MUR SST client: NASA JPL 1km daily SST (1981-present, 3-tier fallback)
- NorKyst v3 client: 800m Norwegian coastal currents (replaces broken CMEMS)
- NASA PACE client: HAB species detection (hyperspectral phytoplankton ID)
- SEPA Scotland client: water quality near salmon farms
- Sernapesca Chile client: 23-year production/disease/export archive
- EUMOFA trade client: European salmon trade flows (imports/exports)
- BarentsWatch updated: 3 new methods for April 2025 API changes
- Historical data fetchers: SSB 26yr, FRED 35yr, Fish Pool 18yr
- 18 new API endpoints across misc/country/market routers
- Missing i18n key fixed (EUDR countdown)

## METRICS (End of Session 37)
- Tests: 447 (0 failures, 14 xfailed, 21 xpassed)
- Engines: ~75 (was 69)
- API endpoints: ~340 (was ~313)
- Frontend pages: 63 (68 compiled routes)
- Components: 43+ (was 38)
- Alembic migrations: 14
- i18n keys: ~600
- TypeScript errors: 0
- Design tokens: 86 (Figma pipeline active)
- DataQualityBadge pages: 24/65
- Data source clients: 45+ (was ~38)
- Historical data coverage: SSB 26yr, FRED 35yr, MUR SST 44yr

## RESUME INSTRUCTIONS
1. Backend: cd C:/Users/freha/FishIntel && python main.py
2. Frontend: cd C:/Users/freha/FishIntel/frontend && npx next dev
3. Tests: python -m pytest tests/ -v --tb=short
4. Figma sync: npm run tokens:sync (requires FIGMA_ACCESS_TOKEN)
5. Historical data: python scripts/fetch_all_historical.py
6. Push: git push origin master
