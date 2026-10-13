/**
 * /supply-forecast contract regression (post-review L5 migration finding)
 * ========================================================================
 * The page previously read fictional fields (`smoltData.monthly_projections`,
 * cohort `projected_harvest_tonnes`) against a backend that returns a
 * pipeline list / cohort rows — the smolt section silently showed
 * "No data" and the cohort volume column always showed "—". These tests
 * pin the real (corrected) envelopes:
 *
 * - /api/supply/smolt-forecast → {pipeline[], horizon_months,
 *   total_harvest_tonnes, data_provenance}
 * - /api/supply/cohort-timeline → {cohorts[], count, data_provenance}
 *
 * All /api/** calls are stubbed; no backend required.
 */
import { test, expect } from "@playwright/test";
import { blockServiceWorker, suppressOnboarding } from "./utils";

const SUMMARY = {
  next_quarter_harvest_tonnes: 480000,
  smolt_releases_ytd_millions: 210.5,
  supply_growth_yoy_pct: 3.0,
  mab_utilization_pct: 82.1,
  price_pressure: "neutral",
  pipeline: [
    {
      year: 2026, month: 6, month_label: "2026-06",
      projected_harvest_tonnes: 142000, lo80: 118000, hi80: 166000,
      demand_tonnes: 130000, balance: 12000, n_cohorts: 9,
    },
    {
      year: 2026, month: 7, month_label: "2026-07",
      projected_harvest_tonnes: 150000, lo80: 120000, hi80: 180000,
      demand_tonnes: 132000, balance: 18000, n_cohorts: 10,
    },
  ],
  cohorts: [],
  demand_balance: {
    horizon_months: 6, total_supply_tonnes: 870000, total_demand_tonnes: 780000,
    balance_tonnes: 90000, balance_pct: 11.5, signal: "balanced",
    price_pressure: "neutral",
  },
  data_provenance: {
    source: "Smolt model + Fiskeridirektoratet + BarentsWatch",
    is_live: true, freshness: "2026-10-13T00:00:00+00:00", confidence: 0.75,
  },
};

const SMOLT = {
  pipeline: [
    {
      year: 2026, month: 6, month_label: "2026-06",
      projected_harvest_tonnes: 142000, lo80: 118000, hi80: 166000,
      demand_tonnes: 130000, balance: 12000, n_cohorts: 9,
    },
  ],
  horizon_months: 18,
  total_harvest_tonnes: 142000,
  data_provenance: SUMMARY.data_provenance,
};

const COHORTS = {
  cohorts: [
    {
      intake: "2025-04", region: "NO-3", n_smolt_millions: 4.2,
      current_weight_kg: 3.1, months_at_sea: 18, stage: "harvestable",
      harvest_month: "2026-10", harvest_tonnes: 8400,
    },
  ],
  count: 1,
  data_provenance: SUMMARY.data_provenance,
};

test("supply-forecast renders the real smolt pipeline (no silent No data)", async ({ page }) => {
  await suppressOnboarding(page);
  await blockServiceWorker(page);
  await page.route("**/api/supply/smolt-forecast**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SMOLT) }));
  await page.route("**/api/supply/cohort-timeline**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(COHORTS) }));
  await page.route("**/api/supply/summary**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SUMMARY) }));
  await page.route("**/api/supply/demand-balance**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SUMMARY.demand_balance) }));

  await page.goto("/supply-forecast", { waitUntil: "networkidle" });

  // Smolt Forecast section renders real month_label rows (was: "No data")
  await expect(page.getByText("Smolt Forecast — Monthly Harvest Projections")).toBeVisible();
  await expect(page.getByText("2026-06").first()).toBeVisible();
  await expect(page.getByText("Total projected harvest")).toBeVisible();

  // Cohort timeline shows the real harvest volume column (was: "—")
  await expect(page.getByText("harvestable").first()).toBeVisible();
  await expect(page.getByText("2026-10").first()).toBeVisible();
  await expect(page.getByText("8.4k").first()).toBeVisible();

  // Provenance-driven badge (payload carries data_provenance -> Live).
  // Scoped to the badge itself: the global TopBar also renders "Live".
  const badge = page.locator('span[role="img"][aria-label*="Smolt model"]');
  await expect(badge).toBeVisible();
  await expect(badge).toHaveAttribute("aria-label", /Live/);
});

test("supply-forecast shows no provenance claim when payloads fail", async ({ page }) => {
  await suppressOnboarding(page);
  await blockServiceWorker(page);
  await page.route("**/api/supply/**", (route) =>
    route.fulfill({ status: 404, contentType: "application/json", body: "{}" }));

  await page.goto("/supply-forecast", { waitUntil: "networkidle" });

  // No summary -> no badge at all (no invented liveness), no smolt section
  await expect(page.getByText("Smolt Forecast — Monthly Harvest Projections")).toHaveCount(0);
  await expect(page.locator('span[role="img"][aria-label*="confidence"]')).toHaveCount(0);
});
