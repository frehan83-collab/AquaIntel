# AquaIntel — Long Autonomous Run Plan (RUN-1)

> Self-contained brief for a **long, unattended agent run** on AquaIntel.
> Read together with `AGENTS.md` (authoritative rules) and `STATUS.md` (live
> log). One agent at a time on `master`; small commits; CI-proof workstreams.

- Repository: `C:\Users\freha\AquaIntel` · Branch: `master`
- Baseline commit: `919855c` (all three CI workflows green)
- Version: `2.2.0` (`core/version.py`) · Tests: 674 (651 pass / 13 xfail / 10 xpass)
- Active plan file: this document · Log: `STATUS.md` session log + `CHANGELOG.md`
- Duration model: **4 sprints ≈ 8–12 agent-hours**, each sprint ends with a green
  pushed commit or documented evidence.

---

## 1. Charter — what this run must achieve

1. **Stabilize further**: clear the known warning/dead-code backlog and audit the
   API-type contracts so the terminal has zero self-inflicted noise.
2. **Re-attempt performance with evidence**: DuckDB P0-2 is re-measurable on
   **Linux (Docker/CI)** — decide ship-or-close with numbers, never vibes.
3. **Ship the flagship product gap**: upgrade the thin supply–demand endpoint
   into the roadmap's "Holy Grail" integrated supply–demand → 2–20 week price
   forecast with uncertainty bands, honest provenance and fallback.
4. **Release**: version bump + changelog + GitHub release if Sprint 3 shipped.

**Success criteria (run complete):** every workstream below is `DONE` or
`BLOCKED-with-evidence`; full pytest + tsc + lint + ruff + smoke_security green;
CI green on the final commit; docs (`STATUS.md`, `CHANGELOG.md`, this doc)
updated; working tree clean and `origin/master` == local.

## 2. Ground rules (non-negotiable, from AGENTS.md)

- **Honesty layer**: fallback/synthetic data must surface as degraded/synthetic —
  never label SSB-synthetic as Fish Pool live, never render invented numbers
  (no `$0.00` fallbacks), report `models_used` vs `models_fallback` truthfully.
- **Security**: admin-only routes stay admin-only; token-based ownership (no
  IDOR); `validate_webhook_url()` at create AND dispatch.
- **Surgical diffs**: delta changes only; follow the singleton-engine +
  `@cached` + `DataProvenance` + `structlog` pattern; **frozen modules**:
  `pairs_engine.py`, `regime_detector.py`, `satellite_engine.py`,
  `self_evolve.py` — do not extend.
- **One agent, one lane**: no parallel pushes to master, no rebases, no force
  pushes. Commit after every green gate, not at the end of the day.
- **Evidence over effort**: if a workstream cannot reach its gate in budget,
  close it `BLOCKED` with the measurements you did get (the P0-2 precedent).
- **Leave the tree clean**: end every session with either a pushed commit or
  `git stash` + a note in `STATUS.md`. Never commit `.coverage`, `*.docx`,
  log files, or scratch scripts.

## 3. Already done — do NOT redo

- P0-1 backend-backed e2e in CI · P0-3 instant-nav lock ×11 · P0-4 uv/3.12 pin
- P1-5 test hygiene · P1-6 agents service/parity · P1-7 Tier-1 audit
- P2-8 Tier-2 audit (contracts, treatment optimizer, investor scenarios, global
  supply all exist end-to-end) · P2-9 honesty/security audit (clean)
- Follow-up sweep `9bf6760`: /market seasonal + futures bindings, macro series
  names (`nok_usd`/`brent_crude`/`soybeans`), WTI→Brent relabels, typed
  `FuturesForwardCurve`, frontend.yml path filters extended.
- Already shipped from the roadmaps: feed margin stack + alerts, ocean-forecast
  → lice decision wiring, ESG scores, AIS harvest intelligence, Nasdaq Salmon
  Index scraper (`core/market/salmon_price.py`), MET.no/NorKyst/CMEMS clients.

## 4. Workstream pool (prioritized)

### Sprint 1 — Hygiene & contract hardening (≤ 2 h)
| ID | Work | Anchor evidence |
|----|------|-----------------|
| R1 | Remove dead Fish Pool code on /market (`FishPoolChart`, `FishPoolPoint`, `fishPool` state, `latestFP` KPI rows) or repoint honestly; fix the `/futures` `<title>` children-array React warning; root-cause the `/market` hydration warning (fix if cheap, else document). | `frontend/src/app/market/page.tsx` (FishPoolChart ~L41, state ~L262, KPIs ~L460/506); `frontend/src/app/futures/page.tsx`; STATUS.md P0-1 notes |
| R2 | API-contract audit: every typed interface in `frontend/src/types/api.ts` vs the real route returns (the `FuturesForwardCurve` staleness is the proven pattern; `FuturesBasis` L272 is suspect). Fix or delete stale types. | `frontend/src/types/api.ts`, `frontend/src/lib/api.ts`, `core/routers/*.py` |
| R3 | i18n: move the sweep's hardcoded strings to en/no keys — "Seasonal data unavailable", "SSB synthetic", "FRED series unavailable", "Brent Crude" — and verify key parity. | `frontend/src/lib/i18n.ts`, `frontend/src/app/market/page.tsx`, `frontend/src/app/investor/page.tsx` |
| R4 | Same-class binding sweep elsewhere: for each `api.ts` method, curl the endpoint and compare the fields pages consume (`.data` vs `.history` vs `.curve` vs name-mismatch class). Fix or file evidence. | `frontend/src/app/**`, `core/routers/**` |

### Sprint 2 — Performance with evidence (≤ 2.5 h)
| ID | Work | Anchor evidence |
|----|------|-----------------|
| R5 | **DuckDB P0-2 on Linux.** Write `scripts/bench_lice_read.py` (3 candidates: current SQLAlchemy path, DuckDB sqlite_scanner ATTACH, extension-free row-load) and run it inside the **Linux Docker image** (`docker run --rm -v ${PWD}:/app -w /app <image> python scripts/bench_lice_read.py`) or a `workflow_dispatch`-only scratch CI job. **Gate:** ship DuckDB behind a config flag only if ≥ 1.5× faster than the 47 ms baseline with the extension; otherwise close `BLOCKED` with the Linux numbers. | `docs/NEXT_STEPS_PLAN.md` P0-2 (220 ms vs 47 ms evidence, app-control policy on Windows only) |
| R6 | Latency sweep: profile slow routes (e2e noted Scotland snapshot ~25 s), find N+1 / missing indexes, add Alembic migration **015** only with `EXPLAIN QUERY PLAN` evidence. | `core/`, `alembic/versions/`, `tests/test_migrations.py` |

### Sprint 3 — Flagship: Holy Grail supply–demand (≤ 4 h)
| ID | Work | Anchor evidence |
|----|------|-----------------|
| R7 | Upgrade `/api/supply/demand-balance` (today just `smolt_model.get_demand_balance()`, consumed as one KPI on /trader) into the integrated model: supply = Norwegian biomass PA 1–13 + Chile/Scotland/Faroe, minus lice-driven harvest delays and treatment mortality; demand = EU/Asia/US with seasonality; output = 2–20 week price forecast + uncertainty bands. Build a new singleton engine `core/market/supply_demand_engine.py` composing existing engines (`biomass_tracker`, `smolt_model`, lice stats, `euronext_futures`, `price_engine`); extend the route **additively** (never remove fields; `API_SCHEMA_VERSION` policy); wire a /market or /supply-forecast card with `DataQualityBadge` + synthetic notice; add tests + backtest evidence via `scripts/run_backtest.py` (MAPE only from real artifacts). | `core/routers/supply_routes.py` L112, `core/valuechain/smolt_model.py`, `frontend/src/app/trader/page.tsx` L186, `docs/strategic_roadmap.md` §Holy Grail |
| R8 | (If budget remains) Lice-to-price direction signal (roadmap Phase 1 #3): lice spike → accelerated harvest → glut then shortage → 2–6 week price direction. Build on the existing causal/regime modules; honest fallback; tests. | `core/routers/causal_routes.py`, `docs/strategic_roadmap.md` §3 |

### Sprint 4 — Release & polish (≤ 2 h)
| ID | Work | Anchor evidence |
|----|------|-----------------|
| R9 | Release: bump `core/version.py` (2.2.0 → 2.3.0 if R7 shipped), move `CHANGELOG.md` [Unreleased] → versioned, create GitHub release via `gh release create`, verify `/api/health` version + OpenAPI drift (`scripts/freeze_openapi.py`). | `core/version.py`, `CHANGELOG.md`, `docs/openapi.frozen.json` |
| R10 | Accessibility/quality coverage: extend `DataQualityBadge` + WCAG aria-labels to remaining pages; keep tsc/lint at 0 errors. | `frontend/src/components/DataQualityBadge.tsx`, page inventory |

---

## 5. The delta loop — the exact protocol for EVERY change

Apply this 11-step loop to every commit-sized change in any sprint. It is the
"step by step" contract for the agent; deviations are allowed only where a
step is provably irrelevant (say so in the commit body).

1. **Orient**: skim `AGENTS.md` → `STATUS.md` → this plan. Confirm the tree is
   clean and `origin/master` is in sync (`git status -sb`, `git fetch origin`).
2. **Reproduce/measure** the problem first. Write evidence down: URLs, error
   text, timings (`Start-Process` + poll for anything > 30 s), response shapes
   (`Invoke-WebRequest` + `ConvertFrom-Json`).
3. **Design the surgical diff**: backend = singleton engine + `@cached` +
   `DataProvenance` + `structlog`; frontend = typed `api.ts` method + page
   binding + honest empty state. Never touch frozen modules. Additive contract
   changes only for existing routes.
4. **Implement** in small deltas; keep each commit ≤ ~1 workstream item.
5. **Verify local (fast)**: import the touched Python module; restart uvicorn;
   curl the endpoint(s); run touched pytest files, then
   `python -m pytest tests/test_critical_engines.py -q` (fast smoke). Frontend:
   `npx tsc --noEmit` + `npm run lint` (0 errors; warnings tolerated).
6. **Live UI proof** (any UI change): uvicorn on :8000 + `npx next dev -p 3001`,
   then a headless-chromium scratch script (not committed) asserting the
   touched page: content present, labels honest, **0 console errors / 0 failed
   requests**. Kill servers + delete scratch files afterwards.
7. **Full gates before commit**: `python -m pytest tests/ -q` (background +
   poll; expect ~4 min), `scripts/smoke_security.py` if security-adjacent,
   `ruff check` (ratchet must stay intact).
8. **Independent review**: spawn a review subagent with the `git diff`; apply
   CRITICAL/HIGH and, where cheap, MEDIUM/LOW before committing. Record the
   verdict in the commit body.
9. **Commit**: stage ONLY the files you touched; descriptive subject + body
   (what/why/evidence). No `.coverage`, `*.docx`, logs, scratch scripts.
10. **Push & watch CI**: `git push origin master`, then `gh run list` / a
    background `gh run watch <id> --exit-status` until Backend Tests, Docker
    Build and Frontend Build are all green. If visual regression fails on an
    intentional UI change: dispatch `visual-baselines.yml` with `update=true`,
    download the artifact, commit the new Linux baselines, re-watch.
11. **Log**: update `STATUS.md` (workstream row + session log entry) and
    `CHANGELOG.md` in the same or a follow-up commit; update `AGENTS.md` /
    `CLAUDE.md` only for structural changes (new routes/engines/conventions).

## 6. Sprint-by-sprint step-by-step

**Sprint 0 — Orientation (30 min, no commits expected)**
- 0.1 `git fetch origin` + `git status -sb` — verify a clean tree at `919855c`.
- 0.2 Boot check: `python -m uvicorn core.api:app` (expect 327 routes,
  `/api/health` 200); `python -m pytest tests/test_critical_engines.py -q`
  green; re-read the Python 3.14 / uv-3.12 split in STATUS.md before touching
  any dependency.
- 0.3 Start the STATUS.md session log: "RUN-1 started, baseline 919855c".

**Sprint 1 — Hygiene (R1 → R2 → R3 → R4; commit after each R)**
- 1.1 R1: remove the Fish Pool remnants on /market (keep the `Promise.resolve`
  stub semantics honest — label or drop the KPIs); fix the /futures title
  warning; investigate the /market hydration warning in the dev console; fix
  if cheap, else document. Verify per delta-loop steps 5–6; visual baselines
  must stay green (changed cards are below the fold; if CI disagrees, use the
  baseline regen flow, never Windows-generated screenshots).
- 1.2 R2: audit every interface in `types/api.ts` against live curls; fix
  stale types (`FuturesBasis` first), delete unused ones; re-run `tsc`.
- 1.3 R3: move the four sweep strings into en/no keys; update both pages;
  `tsc` + render check.
- 1.4 R4: sweep page bindings against curl evidence; fix findings or file an
  "R4 evidence" section in STATUS.md. Check the sweep notes first so nothing
  gets fixed twice.

**Sprint 2 — Performance (R5 → R6)**
- 2.1 R5: write the bench script; run it in the Linux Docker image (`docker
  build` once from the uv-based Dockerfile, then `docker run` the bench) or a
  scratch dispatch-only workflow. Record the three numbers; decide ship/close
  strictly by the 1.5× gate; commit the script + evidence either way.
- 2.2 R6: time the slow routes (uvicorn access-log timings), `EXPLAIN QUERY
  PLAN` the hot queries, add migration 015 only with measured wins; run
  `tests/test_migrations.py` + the full suite.

**Sprint 3 — Flagship (R7, then R8 only if budget remains)**
- 3.1 R7: read `smolt_model.get_demand_balance()` output + the roadmap §Holy
  Grail equation; map each input to an existing engine; build
  `supply_demand_engine.py` with honest provenance (degraded whenever an input
  fell back); extend the route additively; wire the frontend card.
- 3.2 Backtest before claiming accuracy: `scripts/run_backtest.py` on the
  historical window; surface MAPE ONLY from the produced artifact; honest
  fallback for missing inputs.
- 3.3 Verify live (curl the new contract, render-check the card), full gates,
  independent review, commit, push, watch CI.
- 3.4 R8 only if R7 shipped and budget remains.

**Sprint 4 — Release (R9 → R10)**
- 4.1 R9: version bump + changelog versioning + `gh release create` + OpenAPI
  drift check; verify `/api/health` reports the new version.
- 4.2 R10: extend badges/aria-labels; keep gates green; log the final state.

## 7. Stop conditions & escalation

- **No green commit for 2 h** → stop; write what was tried + evidence to
  STATUS.md; mark the workstream BLOCKED; do not burn the budget.
- **CI red twice on the same change** → `git revert` the change, push the
  revert, document; investigate separately; never leave master red.
- **Environment blocker** (policy, network, missing dep) → 2 attempts max,
  then BLOCKED-with-evidence (the P0-2 precedent is the gold standard).
- **Session end** → tree clean (commit or stash + note). STATUS.md must tell
  the next agent exactly where to resume.

## 8. Run-complete checklist (agent verifies before declaring done)

- [ ] Every workstream DONE or BLOCKED-with-evidence in STATUS.md
- [ ] `python -m pytest tests/ -q` green locally; tsc + lint 0 errors;
      ruff ratchet intact; smoke_security clean
- [ ] All three CI workflows green on the final pushed commit
- [ ] `STATUS.md` session log complete; `CHANGELOG.md` current (versioned if R9)
- [ ] Working tree clean; local master == origin/master
- [ ] Final session-log line: "RUN-1 complete — summary of shipped / blocked"


