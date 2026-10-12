/**
 * Visual regression baseline (Session 41).
 *
 * Deterministic by construction: every /api/** call is stubbed with a minimal,
 * stable fixture, so snapshots never change with live data. This is the safety
 * net for the Tailwind 4 migration and card/layout work (see the
 * `visual-regression` project skill).
 *
 * Usage (dev server on :3001):
 *   npx playwright install chromium          # first time
 *   npx playwright test visual.spec.ts --update-snapshots   # create/accept baseline
 *   npx playwright test visual.spec.ts                      # compare (CI)
 */
import { test, expect } from "@playwright/test";

const LICE_SUMMARY = {
  year: 2026, week: 40,
  avg_adult_female_lice: 0.09, max_adult_female_lice: 0.4,
  min_adult_female_lice: 0.0, std_adult_female_lice: 0.05,
  sites_above_threshold: 0, count_above_05: 0, records: 100,
  threshold: 0.5, above_threshold_pct: 0.0,
  data_provenance: { source: "fixture", is_live: false, freshness: "2026-10-01T00:00:00+00:00", confidence: 0.5 },
};

const API_STUBS: Array<[string, unknown]> = [
  ["/api/lice/summary", LICE_SUMMARY],
  ["/api/signals", []],
  ["/api/leaders/top30", []],
  ["/api/market/ssb-price-history", { spot_nok: 73.8, history: [] }],
  ["/api/regime/alerts", []],
  ["/api/pairs/signals", []],
  ["/api/ais/harvest-signals", { total_vessels: 0, summary: {}, signals: [] }],
  ["/api/macro/snapshot", {}],
  ["/api/global-supply", {}],
  ["/api/disease/by-company", {}],
  ["/api/anomaly/scores", { composite_score: 10 }],
  ["/api/alerts", []],
  ["/api/notifications/alerts", { alerts: [] }],
  ["/api/production/summary", {}],
  ["/api/production/by-county", []],
  ["/api/brief", { generated_at: "2026-10-01T06:00:00+00:00", greeting: "Good morning", market_mood: "neutral", top_insight: "fixture", sections: [] }],
];

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const match = API_STUBS.find(([prefix]) => url.pathname.startsWith(prefix));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(match ? match[1] : []),
    });
  });
});

const ROUTES: Array<[string, string]> = [
  ["/", "home"],
  ["/market", "market"],
  ["/traffic-light", "traffic-light"],
  ["/satellite", "satellite"],
];

for (const [route, name] of ROUTES) {
  test(`visual baseline: ${name}`, async ({ page }) => {
    await page.goto(route, { waitUntil: "networkidle" });
    await expect(page).toHaveScreenshot(`${name}.png`, {
      fullPage: false,
      maxDiffPixelRatio: 0.01,
      animations: "disabled",
    });
  });
}
