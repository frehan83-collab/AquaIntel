---
name: visual-regression
description: Playwright screenshot baseline and diff workflow for the FishIntel Next.js frontend (63 routes). Use before/after any UI change to catch visual regressions without manual review.
---

# Visual Regression (FishIntel frontend)

## Setup (one-time)

Frontend already has `@playwright/test`. Screenshot specs live in
`frontend/e2e/` (create if missing). Config note: the app expects the API on
`:8000` (see frontend `.env.local`).

```bash
cd frontend
npx playwright install chromium          # first time only
```

## Baseline workflow

1. Start backend + frontend (dev or built):
   ```bash
   python main.py            # :8000 (repo root)
   cd frontend && npm run dev  # :3000
   ```
2. Create/Update baseline AFTER a known-good visual review:
   ```bash
   npx playwright test visual.spec.ts --update-snapshots
   ```
3. After changes, run without the flag; Playwright diffs against the stored
   snapshots and writes `test-results/` artifacts for failures:
   ```bash
   npx playwright test visual.spec.ts
   ```
4. Investigate every diff; only `--update-snapshots` for INTENTIONAL changes,
   and mention snapshot updates in the commit message.

## Practical rules for this app

- Screenshot the KPI/GlassCard regions, not full pages, for the data-heavy
  dashboards (full-page diffs are noisy because numbers change daily).
- For time-series charts: mask or freeze data via a screenshot test that
  intercepts API routes (`page.route('**/api/**', ...)`) and serves fixtures —
  otherwise every run "fails" because prices moved.
- 3 breakpoints: 375 px (mobile), 768 px (tablet), 1440 px (desktop).
- Prefer `toHaveScreenshot()` with `maxDiffPixelRatio: 0.01`; store snapshots
  in git (they are small PNGs).
- CI: `frontend.yml` runs on ubuntu — add the visual job only after snapshots
  are proven stable on Linux (font rendering differs from Windows).

## War stories (Session 41 — read before a migration)

- **Baselines first, then migrate.** Generate + COMMIT baselines before any
  CSS change; they catch catastrophic regressions instantly (a reverted
  globals.css `@import` → unstyled pages → 0.89 pixel diff, caught in 3 s).
- **Class-token-only renames.** A naive word-boundary regex over `src`
  rewrote object keys (`ring: string`), breaking JSX. Require
  quote/space/colon context on both sides of the token AND run a dry-run
  listing every planned match before applying.
- **Never run `npm run build` while `next dev` is watching `.next`** —
  Turbopack churn corrupts the dev asset graph and pages render unstyled
  (looks like a visual catastrophe but isn't). Stop the dev server first.
- Dev server must bind the port in `playwright.config.ts` (`PORT=3001 npm
  run dev`); Playwright reuses it locally (`reuseExistingServer`).
- Commit baselines + the migration as SEPARATE commits so a needed
  `git checkout` of source can never revert the migration entry point
  (globals.css lives in `src/`!).

