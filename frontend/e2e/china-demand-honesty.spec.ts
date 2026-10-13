/**
 * /china-demand honesty regression (review H4)
 * ============================================
 * The page previously printed "Norwegian export figures are shown from
 * curated estimates" in the supplier note and the "Data Sources" footer
 * even while loading or after a total fetch failure — i.e. claiming
 * estimates were shown when nothing was shown at all.
 *
 * These tests pin the honest states:
 * - loading: no provenance claims while the snapshot is in flight
 * - fetch failure: a distinct error banner, no "estimates shown" claim
 * - live snapshot: LIVE SSB claim (data IS shown)
 * - degraded snapshot: explicit curated-estimate claim (data IS shown)
 *
 * All /api/china/** calls are stubbed; no backend required.
 */
import { test, expect } from "@playwright/test";
import { blockServiceWorker, suppressOnboarding } from "./utils";

const LIVE_SNAPSHOT = {
  norway_exports_to_china: {
    tonnes_12m: 42000,
    yoy_trend_pct: 5.2,
    is_live: true,
    data_source: "LIVE — SSB table 08799",
  },
  china_total_imports: {
    tonnes_annual: 95000,
    estimate_year: 2025,
    data_source: "Q4 2025",
  },
  suppliers: [
    {
      flag: "NO",
      origin: "Norway",
      is_live: true,
      share_pct: 44,
      tonnes: 42000,
      yoy_growth_pct: 5,
    },
  ],
  monthly_series: [{ month: "2026-08", tonnes: 3500, value_mnok: 250 }],
  norway_share_pct: 44,
  data_provenance: {
    source: "SSB table 08799",
    is_live: true,
    freshness: "2026-10-13T00:00:00+00:00",
    confidence: 0.9,
  },
};

const DEGRADED_SNAPSHOT = {
  norway_exports_to_china: {
    tonnes_12m: 42000,
    yoy_trend_pct: 5.2,
    is_live: false,
    data_source: "SSB table 08799 unavailable (upstream error)",
  },
  china_total_imports: {
    tonnes_annual: 95000,
    estimate_year: 2025,
    data_source: "Q4 2025",
  },
  suppliers: [
    {
      flag: "NO",
      origin: "Norway",
      is_live: false,
      share_pct: 44,
      tonnes: 42000,
      yoy_growth_pct: 5,
    },
  ],
  monthly_series: [],
  norway_share_pct: 44,
  data_provenance: {
    source: "SSB table 08799 unavailable",
    is_live: false,
    freshness: "2026-10-13T00:00:00+00:00",
    // Confidence < 0.4 deliberately: the old badge mapping mislabelled
    // this state as "Synthetic" (review M4).
    confidence: 0.3,
  },
};

const SIGNALS = {
  signal_label: "Neutral",
  signal_score: 0.42,
  signal_direction: "neutral",
  momentum_chart: [],
  insights: [],
};

const IMPACT = { impact_label: "Neutral", estimated_price_impact_pct: 0 };

interface StubOpts {
  snapshot?: unknown;
  snapshotStatus?: number;
  gate?: Promise<void>;
}

async function stubChina(page: import("@playwright/test").Page, opts: StubOpts = {}) {
  await page.route("**/api/china/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/china/demand") {
      if (opts.gate) await opts.gate;
      const status = opts.snapshotStatus ?? 200;
      const body =
        status === 200
          ? JSON.stringify(opts.snapshot ?? LIVE_SNAPSHOT)
          : JSON.stringify({ error: "fixture failure" });
      await route.fulfill({ status, contentType: "application/json", body });
      return;
    }
    if (path === "/api/china/demand-signals") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SIGNALS),
      });
      return;
    }
    if (path === "/api/china/demand-impact") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(IMPACT),
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
}

test("loading: no provenance claims while the snapshot is in flight", async ({ page }) => {
  await suppressOnboarding(page);
  await blockServiceWorker(page);
  let release = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await stubChina(page, { gate });
  await page.goto("/china-demand");
  // While in flight: no provenance claim anywhere, no error banner
  // (note: not "Data Sources" — the global app footer matches that too)
  await expect(page.getByText("curated estimates")).toHaveCount(0);
  await expect(page.getByText("The SSB table 08799 series is currently unavailable")).toHaveCount(0);
  await expect(page.getByText("are LIVE from SSB table 08799")).toHaveCount(0);
  await expect(page.getByText("Failed to load China demand data")).toHaveCount(0);
  // Once the snapshot lands, the honest footer appears
  release();
  await expect(
    page.getByText("Norwegian exports to China are LIVE from SSB table 08799"),
  ).toBeVisible();
});

test("fetch failure: distinct error state, no estimates claim", async ({ page }) => {
  await suppressOnboarding(page);
  await blockServiceWorker(page);
  await stubChina(page, { snapshotStatus: 404 });
  await page.goto("/china-demand", { waitUntil: "networkidle" });
  // Distinct failure banner instead of a provenance claim
  await expect(page.getByText("Failed to load China demand data")).toBeVisible();
  // No "estimates are shown" claims while nothing is shown
  await expect(page.getByText("curated estimates")).toHaveCount(0);
  await expect(page.getByText("The SSB table 08799 series is currently unavailable")).toHaveCount(0);
  await expect(page.getByText("are LIVE from SSB table 08799")).toHaveCount(0);
  await expect(page.getByText("Norway data is LIVE from SSB")).toHaveCount(0);
});

test("live snapshot: honest LIVE claims when data is shown", async ({ page }) => {
  await suppressOnboarding(page);
  await blockServiceWorker(page);
  await stubChina(page, {});
  await page.goto("/china-demand", { waitUntil: "networkidle" });
  await expect(
    page.getByText("Norwegian exports to China are LIVE from SSB table 08799"),
  ).toBeVisible();
  await expect(page.getByText("Norway data is LIVE from SSB.")).toBeVisible();
  await expect(page.getByText("curated estimates")).toHaveCount(0);
  // Badge state mapping (review M4): is_live payload -> "Live" badge
  await expect(page.getByText("Live").first()).toBeVisible();
  await expect(page.getByText("Synthetic")).toHaveCount(0);
});

test("degraded snapshot: honest estimate claims when data is shown", async ({ page }) => {
  await suppressOnboarding(page);
  await blockServiceWorker(page);
  await stubChina(page, { snapshot: DEGRADED_SNAPSHOT });
  await page.goto("/china-demand", { waitUntil: "networkidle" });
  // Data IS on screen -> the curated-estimate claim is now honest
  await expect(page.getByText("curated estimates").first()).toBeVisible();
  await expect(page.getByText("are LIVE from SSB")).toHaveCount(0);
  await expect(page.getByText("Norway data is LIVE from SSB.")).toHaveCount(0);
  // Badge mapping (review M4): confidence 0.3 + degraded state must show
  // "Degraded", never "Synthetic" (the old threshold-based mislabel)
  await expect(page.getByText("Degraded").first()).toBeVisible();
  await expect(page.getByText("Synthetic")).toHaveCount(0);
  // The native title tooltip is gone (review M4): the custom
  // group-hover/group-focus-within tooltip is the single tooltip
  await expect(page.locator('span[role="img"][title]')).toHaveCount(0);
  // Keyboard focus gets a visible ring (review M4)
  const badge = page.locator("span.group.inline-flex").first();
  await expect(badge).toHaveClass(/focus-visible:ring-2/);
});
