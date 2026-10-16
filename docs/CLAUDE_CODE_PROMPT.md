# Prompt for Claude Code — AquaIntel takeover

Copy everything inside the fence below into Claude Code, run from the repo root
(`C:\Users\freha\FishIntel` on Windows, or the equivalent clone path). It is written to
make the first hour productive: recon → plan → implement one workstream → verify.

````text
You are taking over active development of AquaIntel (repo: frehan83-collab/AquaIntel,
branch `master`), a production salmon-aquaculture intelligence platform: FastAPI
backend (~350 operations, ~77 engines), Next.js 16 frontend (68 pages),
PostgreSQL/TimescaleDB, 12 background agents, ~1000 tests. A previous agent just
finished a 10-step "commercial hardening" programme and pushed it. Continue from that
verified state.

START BY READING, IN THIS ORDER (do not skip step 1)
1. `docs/HANDOVER.md`   — verified state, gate commands, the WS-1…WS-13 backlog and
                          the trap table that will otherwise cost you hours.
2. `AGENTS.md`          — authoritative non-negotiable rules. If another doc
                          disagrees with it, AGENTS.md wins.
3. `PROJECT_STATUS.md`  — what is shipped, with evidence per step.
4. `CHANGELOG.md` (top) — why each recent change was made.
5. Only then the per-area docs for whatever you touch: `docs/ENTITLEMENTS.md`,
   `docs/BILLING.md`, `docs/INDICES.md`, `docs/ACCURACY.md`,
   `docs/PRODUCTION_TRUTH.md`, `docs/DESIGN_PARTNERS.md`, `docs/ADVICE_BOUNDARY.md`,
   `docs/REPORT_LIVENESS.md`.

ENVIRONMENT (verify, don't assume)
- Windows + PowerShell. Use `python -m pytest`, never bare `pytest`.
- Target is Python 3.12 (`.python-version`, `pyproject.toml` requires
  >=3.12,<3.13) but the interpreter on this box is 3.14.3 and the suite runs under it.
  That mismatch is known — do not "fix" the pin, and do not run
  `uv pip install --system -r requirements.lock` unless you mean it.
- `.env` exists; `frontend/node_modules` is installed; Node 24 / npm 11.
- Command runners can time out at ~30s, so background anything longer:
  Start-Process -FilePath python -ArgumentList '-m','pytest','tests/','-q'
    -RedirectStandardOutput data\_suite.txt -NoNewWindow
  then poll `data\_suite.txt`. `--timeout` is NOT available (no pytest-timeout).
- PowerShell swallows Python tracebacks and can report exit 1 for a *successful*
  `git push`. Capture tracebacks with `cmd /c "python x.py > out.txt 2>&1"` and read
  the file; confirm pushes with `git ls-remote origin refs/heads/master`.

GATES (run them; paste real output, never paraphrase)
Fast slice, ~14s, 207 tests:
  python -m pytest tests/test_entitlements.py tests/test_billing_money_path.py tests/test_indices.py tests/test_accuracy_registry.py tests/test_production_truth.py tests/test_partner_pilots.py tests/test_legal.py tests/test_provenance_ratchet.py tests/test_gtm_roi.py tests/test_migrations.py tests/test_openapi_contract.py -q
Then, depending on what you touched:
  python -m ruff check <changed files>
  cd frontend && npx tsc --noEmit        # must be 0 errors
  python scripts/provenance_ratchet.py   # exit 1 = new data route, no decision made
  python scripts/verify_production_truth.py
  python scripts/smoke_security.py       # only if you touched auth/security
After adding or changing ANY route, re-freeze deliberately:
  python scripts/freeze_openapi.py
  python scripts/provenance_ratchet.py --update    # only after a provenance decision
Never re-freeze merely to make a failure disappear.

NON-NEGOTIABLES (violating these fails review)
1. Never fabricate data or accuracy. A model fallback is `is_live: false`, always. No
   MAPE/coverage/backtest number may be shown unless a validated artifact in
   `artifacts/accuracy/` produced it.
2. One entitlement definition: `core/entitlements.py`. Never add a tier table
   elsewhere (three had already drifted before this was fixed).
3. Every data route carries provenance (`@with_provenance` from
   `core/market/provenance_envelope.py`) or is listed in
   `core/provenance_register.EXEMPT` with a written reason.
4. Security: admin-only `/api/admin/*` and `/api/cache/*`; ownership checks against
   the TOKEN user id (never a body `user_id`); SSRF guard on outbound URLs at
   creation AND dispatch; production refuses a weak JWT secret.
5. Surgical diffs, and a regression test for every bug you fix.
6. State gaps, never hide them. `unknown` / `degraded` / `synthetic_only` are correct
   answers; a green dashboard that lies is a defect.
7. Do not extend the frozen modules: `pairs_engine.py`, `regime_detector.py`,
   `satellite_engine.py`, `self_evolve.py`.
8. Do not add dependencies without asking.

HARD-WON TRAPS (full table in `docs/HANDOVER.md` §6; the top five)
- Alembic migrations: `exec_driver_sql` with `%s` is psycopg2-only and is a SYNTAX
  ERROR on SQLite. Use SQLAlchemy Core `update()` with bound parameters.
- SQLite returns timestamps as ISO STRINGS and drops tzinfo on read: coerce before
  comparing (this silently broke freshness for every source once).
- `ssb_price_client.get_price_history` returns week labels like `"W42"` — strip the
  `W` before `int()`.
- Never derive a route inventory from the live app for a ratchet: other tests inject
  `/api/test-*` routes. Use `docs/openapi.frozen.json`.
- `ssb_weekly_prices` rows are `source='demo_seed'` and `lice_records` has NO source
  column at all — never measure accuracy on them, never claim `is_live` from them.

YOUR WORK, IN THIS ORDER (one workstream per commit; details and acceptance criteria
in `docs/HANDOVER.md` §5)
1. WS-1 — add a `source` column to `lice_records` (migration + ingest + freshness +
   indices) so AI-LPI's lineage becomes verifiable. Today AI-LPI correctly reports
   `is_live: false` with "lineage unverifiable" on every call; after WS-1 it must be
   able to claim live when rows are real and must still refuse when they are demo.
   Highest-value item in the repo.
2. WS-2 — schedule the weekly index publication so `/api/indices/*/history` becomes a
   real series (`publish_week()` exists; a unique constraint already prevents
   double-publishing).
3. WS-3 — ship model artifacts through the release path (manifest + hash; verify the
   hash, not the file presence).
4. WS-4 — Timescale hypertable conversion (only tables with a real timestamp column).
Then continue down the list (WS-5 durable quota ledger → WS-12 enforce the licence
register at runtime). WS-13 is human-gated: do not attempt it and never imply it is
done.

WORKING AGREEMENT
- Recon first: for each workstream, read the real files and REPRODUCE the current
  behaviour (show the command and its output) before changing anything.
- Write the failing test first where behaviour is at stake, then make it pass.
- One workstream per commit, conventional subject plus a body explaining what and why,
  referencing the WS number. Update `CHANGELOG.md`, `PROJECT_STATUS.md` and
  `STATUS.md`, and add or refresh the relevant `docs/*.md` — documentation is part of
  the deliverable, not an afterthought.
- Commit locally as you go. Do NOT push until the user confirms.
- Report honestly: if a test fails, say so with the output; if you skipped something,
  say why. Never make a gate pass by weakening an assertion, widening an exemption
  list, or re-freezing a baseline without a written provenance decision.
- If you find a bug outside your workstream, fix it only when it is small and clearly
  related; otherwise record it as a numbered workstream in `docs/HANDOVER.md` with
  acceptance criteria instead of leaving it silent.

FIRST REPLY SHOULD BE
1. A short recon report: what you read, the state you verified, and the exact output
   of the fast gate.
2. A concrete plan for WS-1 (files, migration, test, acceptance checks).
3. Then implement it. Ask only when a decision is genuinely ambiguous — product and
   legal choices belong to the founder; engineering choices are yours.
````

## Why the prompt is shaped this way

- **Recon before code.** The main risk is a fresh agent "improving" something it has
  not reproduced — e.g. deleting the honest `is_live: false` on AI-LPI because it
  looks like a bug.
- **Traps inline.** Five of the ten traps cost real time in the last session; stating
  them is cheap, rediscovering them is not.
- **Honesty as an acceptance criterion.** "Never make a gate pass by weakening an
  assertion" targets the failure mode that would damage this codebase most.
- **WS-1 first** because it converts the flagship index from permanently degraded to
  legitimately live, and is the only backlog item that unblocks a *product* claim.
- **Push held for your confirmation**, while commits, docs and tests are expected as
  the work happens.

