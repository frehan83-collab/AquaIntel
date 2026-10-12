# FishIntel Tech Stack & Graphics Report

> Session 40 research (inline; agents backend unavailable). Versions verified
> against official sources Oct 2026; unverified claims are marked.

## Verdict in one line
The stack is fundamentally right (FastAPI async + Next 15/React 19 + deck.gl/MapLibre);
the gaps are **framework currency** (Next 15.3 → 16.4, Tailwind 3.4 → 4, MapLibre 5 → 6)
and **data-path discipline** (generated API types, query caching, big-series charts).

## 1. Backend

| Area | Current | Recommendation | Effort | Notes |
|---|---|---|---|---|
| Framework | FastAPI (Pydantic v2) | **Keep** | — | Right choice; response_model coverage & pagination are the open work (Phase 1) |
| Deps/packaging | pip + requirements.txt | Adopt **uv** (lockfile, 10-100x installs) | 2 h | CI step: `uv sync`; keep requirements.txt export for Docker compatibility |
| Lint/format | none pinned | **ruff** (lint+format, single tool) | 2 h | 1.1k .py files; ruff replaces flake8/isort/black |
| Background jobs | 12 asyncio agents in-process + gunicorn workers | Keep for now; move heavy ML jobs to **arq+Redis** only when workers >2 | 1 d | Current: separate `fishintel-agents` compose service already exists — good enough until ML queues contend |
| Analytics accel | SQLite aggregates per request | **DuckDB** read-path for 186k-row lice table + FRED joins | 4 h | `ATTACH` the SQLite file read-only; no migration risk |
| Observability | structlog + request-id + Prometheus | Add **OpenTelemetry** FastAPI instrumentation (free) + **Sentry** free tier (5k errors/mo) | 4 h | Trace 320 routes; Sentry MCP exists for triage (see MCP_SETUP.md) |
| LLM chat | context-stuffing in `chat_agent` | Evaluate **pgvector** only when moving to PG | 1 d | Not needed on SQLite dev; keep stuffing for <50 docs |

## 2. Frontend — framework currency (the big item)

| Package | Current | Latest (verified) | Action |
|---|---|---|---|
| **Next.js** | 15.3 | **16.4** ([blog](https://nextjs.org/blog/next-16-4)) | Upgrade wave; 16.4 introduces **Cache Components** (default in 17). Our installed skill `next-cache-components-optimizer` (Vercel, 16.8K) guides this exactly. Also unlocks the official Next skills from the ecosystem install. |
| **React** | 19.1 | 19.x (compatible) | Ship with Next 16 |
| **Tailwind** | 3.4 | **4.3** ✅ migrated `f6abbcc` | DONE (visual-baseline gated): v4 + `@config` compat, class-token renames verified 4/4 vs baselines. Figma token pipeline audit still open. |
| **MapLibre GL JS** | 5.21 | **6.14** ([docs](https://maplibre.org/maplibre-gl-js/docs/)) | Major bump: globe projection mature; pair with deck.gl MapboxOverlay |
| **deck.gl** | 9.2 | **9.4** (Sep 2026, [whats-new](https://deck.gl/docs/whats-new)) | Low-risk minor; MapLibre interop documented |
| **Recharts** | 3.8 | keep for simple charts | See §3 |
| TanStack Query | not used | **v5** adopt for the 60+ data hooks | 1 d; dedupe/retry/cache replaces hand-rolled `useDashboardData` patterns |
| Generated API types | hand-written `api.ts` + 59 interfaces | **openapi-typescript** (`npm run gen:api`) + check-in `generated.ts`; add CI drift check | Phase 1.6 (planned) |

## 3. Graphics & data viz

| Need | Recommendation | Why |
|---|---|---|
| 10k+ point time series (lice history, FRED) | **Apache ECharts 6** ([v6 release](https://echarts.apache.org/handbook/en/basics/release-note/v6-feature/)) | Canvas perf + built-in zoom/dataZoom; Recharts struggles >5k points. Keep Recharts for KPI sparklines/donuts. |
| Maps (farm sites, currents) | MapLibre 6 + deck.gl 9.4 | Animated current particles via deck.gl `TripsLayer`/custom layer |
| 3D digital twin | react-three-fiber feasibility check when twin UI is rebuilt | SSR caveats manageable; not a phase-1 item |
| Motion | framer-motion 12 (current) | Fine |
| Visual QA | Playwright screenshot baselines | See `visual-regression` skill (created this session) |
| Bundles | `@next/bundle-analyzer` already wired | Add size budget check in CI (e.g. fail >250 kB first-load on dashboard) |

## 4. Cross-cutting

- **Ecosystem skills installed this session** (user-level): `firecrawl`, `next-cache-components-optimizer` (Vercel), `building-components` (Vercel), `playwright-interactive` (OpenAI). Use them for the Next 16 and component work.
- **CI**: workflows fixed to run on `master` (Session 40). Next: add `tsc --noEmit` job (exists in frontend.yml), OpenAPI drift check, and the route-typing ratchet test (Phase 1.5).
- **Windows/Linux parity**: `.gitattributes` enforces LF for source/scripts; keep using `python -m pip`, `cmd /c` capture pattern (see run-tests skill).

## 5. Top-10 Adoption List (next 30 days)

| # | Item | Effort | Payoff |
|---|---|---|---|
| 1 | Generated API types + CI drift check | 4 h | Kills an entire drift-bug class |
| 2 | Next 15.3 → **16.4** upgrade via `next-cache-components-optimizer` skill | 1 d | Currency + perf + matches "latest tech" promise |
| 3 | TanStack Query v5 for the data hooks | 1 d | Fewer duplicate fetches, real caching UX |
| 4 | ECharts 6 for the 2-3 heavy charts | 4 h | Dashboards stay interactive at 10k+ points |
| 5 | MapLibre 6 + deck.gl 9.4 bump | 4 h | Globe view + particles on live currents |
| 6 | Tailwind 4 migration (post visual-baseline) | 1 d | ✅ DONE Session 41 (`f6abbcc`) — OC engine, 4/4 visual baselines green |
| 7 | ruff + uv in CI | 4 h | ✅ ruff DONE Session 41c (E9/F821/F811/F401 gate; sweep found dead chat branches + 2 dead engines). uv still open |
| 8 | OpenTelemetry + Sentry free tier | 4 h | Production traceability |
| 9 | Bundle size budget in CI | 3 h | Prevents frontend bloat regressions |
| 10 | DuckDB read path for lice analytics | 4 h | Removes 186k-row aggregate pressure |

Sources captured during research: Tailwind upgrade guide, Next.js 16.4 blog,
ECharts v6 release notes, deck.gl What's New (v9.4), MapLibre v6 docs,
2026 chart-library comparisons (Strapi/Querio).
