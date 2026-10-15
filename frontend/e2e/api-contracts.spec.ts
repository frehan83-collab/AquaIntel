import { test, expect } from "@playwright/test";

/**
 * API Contract E2E Tests
 * =======================
 * Verify all critical API endpoints return correct response shapes.
 * These prevent silent API breakage — if a field is renamed or removed,
 * these tests catch it before users see blank pages.
 */

const API = "http://localhost:8000";

test.describe("Health & System", () => {
  test("GET /api/health returns structured health", async ({ request }) => {
    const res = await request.get(`${API}/api/health`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.status).toBe("healthy");
    expect(body).toHaveProperty("version");
    expect(body).toHaveProperty("database");
  });

  test("GET /api/metrics returns JSON system metrics", async ({ request }) => {
    const res = await request.get(`${API}/api/metrics`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    // /api/metrics is the hand-written JSON view (cache + process stats);
    // Prometheus text lives at /api/metrics/prometheus (instrumentator).
    expect(body).toHaveProperty("cache");
    expect(body).toHaveProperty("process");
  });

  test("GET /api/rate-limit-info returns tier data", async ({ request }) => {
    const res = await request.get(`${API}/api/rate-limit-info`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("tier");
  });
});

test.describe("Lice & Disease Intelligence", () => {
  test("GET /api/lice/summary has provenance", async ({ request }) => {
    const res = await request.get(`${API}/api/lice/summary`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("data_provenance");
    expect(body.data_provenance).toHaveProperty("source");
    expect(body.data_provenance).toHaveProperty("confidence");
  });

  test("GET /api/disease/norway returns cases", async ({ request }) => {
    const res = await request.get(`${API}/api/disease/norway`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    // Should have cases array or wrapped object
    const cases = Array.isArray(body) ? body : body.cases || body.data || [];
    expect(Array.isArray(cases)).toBeTruthy();
  });

  test("GET /api/disease/by-company returns dict", async ({ request }) => {
    const res = await request.get(`${API}/api/disease/by-company`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(typeof body).toBe("object");
  });

  test("GET /api/disease/resistance-map returns PA data", async ({ request }) => {
    const res = await request.get(`${API}/api/disease/resistance-map`);
    expect(res.ok()).toBeTruthy();
  });
});

test.describe("Market & Price", () => {
  test("GET /api/market/price-outlook has forecast", async ({ request }) => {
    const res = await request.get(`${API}/api/market/price-outlook`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("data_provenance");
  });

  test("GET /api/market/ssb-price-history returns prices", async ({ request }) => {
    const res = await request.get(`${API}/api/market/ssb-price-history?weeks=4`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("spot_nok");
    expect(typeof body.spot_nok).toBe("number");
  });

  test("GET /api/feed-cost/composite-index returns index", async ({ request }) => {
    const res = await request.get(`${API}/api/feed-cost/composite-index`);
    expect(res.ok()).toBeTruthy();
  });

  test("GET /api/competitiveness/origin-index returns rankings", async ({ request }) => {
    const res = await request.get(`${API}/api/competitiveness/origin-index`);
    expect(res.ok()).toBeTruthy();
  });

  test("GET /api/futures/forward-curve returns curve", async ({ request }) => {
    const res = await request.get(`${API}/api/futures/forward-curve`);
    expect(res.ok()).toBeTruthy();
  });
});

test.describe("Decision Engine", () => {
  test("GET /api/decision/{locality} returns valid action", async ({ request }) => {
    const res = await request.get(`${API}/api/decision/10001`);
    // May 404 if locality doesn't exist, but should not 500
    expect(res.status()).toBeLessThan(500);
    if (res.ok()) {
      const body = await res.json();
      const action = body.action || body.data?.action;
      if (action) {
        expect(["TREAT_NOW", "SCHEDULE_TREATMENT", "MONITOR", "NO_ACTION"]).toContain(action);
      }
    }
  });
});

test.describe("Analytics & Leaders", () => {
  test("GET /api/leaders/top30 returns ranked companies", async ({ request }) => {
    const res = await request.get(`${API}/api/leaders/top30`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const data = Array.isArray(body) ? body : body.data || body.companies || [];
    expect(Array.isArray(data)).toBeTruthy();
  });

  test("GET /api/anomaly/scores returns composite", async ({ request }) => {
    const res = await request.get(`${API}/api/anomaly/scores`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("composite_score");
    expect(body).toHaveProperty("risk_level");
    expect(typeof body.composite_score).toBe("number");
  });

  test("GET /api/analytics/yoy-comparison returns trend", async ({ request }) => {
    const res = await request.get(`${API}/api/analytics/yoy-comparison?metric=lice`);
    expect(res.ok()).toBeTruthy();
  });
});

test.describe("Supply Chain", () => {
  test("GET /api/global-supply returns country data", async ({ request }) => {
    const res = await request.get(`${API}/api/global-supply`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const data = body.data || body;
    expect(data).toHaveProperty("countries");
  });

  test("GET /api/supply/smolt-forecast returns pipeline envelope", async ({ request }) => {
    const res = await request.get(`${API}/api/supply/smolt-forecast`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    // Contract corrected post-review: envelope with provenance (was a
    // bare list with an unreachable provenance guard, consumed by three
    // fictional shapes).
    expect(Array.isArray(body.pipeline)).toBeTruthy();
    expect(body).toHaveProperty("horizon_months");
    expect(body).toHaveProperty("total_harvest_tonnes");
    expect(body).toHaveProperty("data_provenance");
  });

  test("GET /api/supply/cohort-timeline returns cohorts envelope", async ({ request }) => {
    const res = await request.get(`${API}/api/supply/cohort-timeline`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body.cohorts)).toBeTruthy();
    expect(body).toHaveProperty("count");
    expect(body).toHaveProperty("data_provenance");
  });

  test("GET /api/market/ssb-price-history returns price_nok rows", async ({ request }) => {
    const res = await request.get(`${API}/api/market/ssb-price-history?weeks=8`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("spot_nok");
    expect(Array.isArray(body.history)).toBeTruthy();
    if (body.history.length > 0) {
      // The row key is price_nok (page mapping used to read it via `as any`)
      expect(body.history[0]).toHaveProperty("price_nok");
    }
  });

  test("GET /api/market/export-destinations returns a destinations dict", async ({ request }) => {
    const res = await request.get(`${API}/api/market/export-destinations?months=12`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    // DICT keyed by country code (was consumed as a list -> eternal skeleton)
    expect(typeof body.destinations).toBe("object");
    expect(Array.isArray(body.destinations)).toBeFalsy();
  });

  test("GET /api/market/hedger-signals returns the Signal rows as a list", async ({ request }) => {
    const res = await request.get(`${API}/api/market/hedger-signals`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    // LIST of Signal rows (was consumed as {signals:[...]} -> always empty)
    expect(Array.isArray(body)).toBeTruthy();
    if (body.length > 0) expect(body[0]).toHaveProperty("ticker");
  });

  test("GET /api/ais/harvest-intelligence matches the corrected contract", async ({ request }) => {
    const res = await request.get(`${API}/api/ais/harvest-intelligence`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    for (const key of [
      "total_vessels", "summary", "supply_pressure",
      "treatment_pressure", "harvest_signals_72h", "treatment_signals_72h", "price_signal",
    ]) {
      expect(body, `missing ${key}`).toHaveProperty(key);
    }
  });

  test("GET /api/sentiment/summary matches the corrected contract", async ({ request }) => {
    const res = await request.get(`${API}/api/sentiment/summary`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    for (const key of ["articles_24h", "avg_sentiment_24h", "sentiment_trend"]) {
      expect(body, `missing ${key}`).toHaveProperty(key);
    }
  });

  test("GET /api/macro/snapshot returns indices + benchmarks", async ({ request }) => {
    const res = await request.get(`${API}/api/macro/snapshot`);
    if (res.status() === 404) {
      // Documented degraded path: FRED data unavailable -> explicit 404
      // (never an empty 200 pretending to be a snapshot).
      const body = await res.json();
      expect(JSON.stringify(body)).toContain("not available");
      return;
    }
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("indices");
    expect(body).toHaveProperty("benchmarks");
  });

  test("GET /api/market/price-outlook/multi returns horizon rows", async ({ request }) => {
    const res = await request.get(`${API}/api/market/price-outlook/multi`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body.horizons)).toBeTruthy();
    expect(body).toHaveProperty("current_spot_nok");
    if (body.horizons.length > 0) {
      for (const key of ["horizon", "predicted", "lo80", "hi80", "direction"]) {
        expect(body.horizons[0], `missing ${key}`).toHaveProperty(key);
      }
    }
  });

  test("GET /api/market/prediction-history returns a list", async ({ request }) => {
    const res = await request.get(`${API}/api/market/prediction-history?horizon=4&days=30`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body)).toBeTruthy();
    if (body.length > 0) {
      // Real row keys (the page used to read date/actual — always 0)
      expect(body[0]).toHaveProperty("predicted_nok");
      expect(body[0]).toHaveProperty("created_at");
    }
  });

  test("GET /api/market/price-outlook/explain uses top_drivers", async ({ request }) => {
    const res = await request.get(`${API}/api/market/price-outlook/explain?horizon=4`);
    if (res.status() === 503) {
      // Documented degraded path: TFT weights not trained -> explicit 503
      return;
    }
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body.top_drivers)).toBeTruthy();
    if (body.top_drivers.length > 0) {
      expect(body.top_drivers[0]).toHaveProperty("feature");
      expect(body.top_drivers[0]).toHaveProperty("importance");
    }
  });

  test("GET /api/market/futures-curve returns SSB price_nok rows", async ({ request }) => {
    const res = await request.get(`${API}/api/market/futures-curve`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("spot_nok");
    expect(Array.isArray(body.history)).toBeTruthy();
    if (body.history.length > 0) expect(body.history[0]).toHaveProperty("price_nok");
  });

  test("GET /api/disease/by-company returns the companies envelope", async ({ request }) => {
    const res = await request.get(`${API}/api/disease/by-company`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    // Envelope corrected post-review: provenance used to be mixed into the map
    expect(typeof body.companies).toBe("object");
    expect(Array.isArray(body.companies)).toBeFalsy();
    expect(body).toHaveProperty("count");
    expect(body).toHaveProperty("data_provenance");
    expect(body.companies).not.toHaveProperty("data_provenance");
  });

  test("GET /api/disease/norway returns by_disease + active_outbreaks", async ({ request }) => {
    const res = await request.get(`${API}/api/disease/norway`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("by_disease");
    expect(Array.isArray(body.active_outbreaks)).toBeTruthy();
    if (body.active_outbreaks.length > 0) {
      // Real outbreak keys (the page used to read disease_type/production_area)
      for (const key of ["locality_no", "locality_name", "disease", "status"]) {
        expect(body.active_outbreaks[0], `missing ${key}`).toHaveProperty(key);
      }
    }
  });

  test("GET /api/disease/alerts returns alert rows with report_date", async ({ request }) => {
    const res = await request.get(`${API}/api/disease/alerts`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body.alerts)).toBeTruthy();
    if (body.alerts.length > 0) {
      expect(body.alerts[0]).toHaveProperty("disease");
      expect(body.alerts[0]).toHaveProperty("report_date");
    }
  });

  test("GET /api/disease/treatments returns report rows", async ({ request }) => {
    const res = await request.get(`${API}/api/disease/treatments?year=2026`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body.reports)).toBeTruthy();
    expect(body).toHaveProperty("with_resistance_suspicions");
    if (body.reports.length > 0) {
      expect(body.reports[0]).toHaveProperty("locality_no");
    }
  });

  test("GET /api/analytics/yoy-comparison emits week+value series", async ({ request }) => {
    const res = await request.get(`${API}/api/analytics/yoy-comparison?metric=disease&production_area=0`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    for (const key of ["current_year", "previous_year", "two_years_ago"]) {
      expect(Array.isArray(body[key]), `missing ${key}`).toBeTruthy();
    }
    if (body.current_year.length > 0) {
      expect(body.current_year[0]).toHaveProperty("week");
      expect(body.current_year[0]).toHaveProperty("value");
    }
  });

  test("GET /api/feed-supply-chain/summary matches the corrected contract", async ({ request }) => {
    const res = await request.get(`${API}/api/feed-supply-chain/summary`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body.composition)).toBeTruthy();
    expect(Array.isArray(body.scenarios)).toBeTruthy();
    expect(body).toHaveProperty("eudr_risk");
    expect(body).toHaveProperty("sankey");
    expect(Array.isArray(body.sankey?.nodes)).toBeTruthy();
    // Standard platform provenance (was a hand-rolled dict: honestly degraded)
    expect(body.data_provenance).toHaveProperty("is_live");
    expect(body.data_provenance.is_live).toBe(false);
    expect(body.data_provenance).toHaveProperty("fallback_reason");
    if (body.composition.length > 0) {
      for (const key of ["name", "weight_pct", "cost_nok_per_kg", "eudr_risk"]) {
        expect(body.composition[0], `missing ${key}`).toHaveProperty(key);
      }
    }
  });

  test("GET /api/brief matches the response-model contract", async ({ request }) => {
    const res = await request.get(`${API}/api/brief`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body.sections)).toBeTruthy();
    expect(body).toHaveProperty("generated_at");
    // Real keys (the frontend type used to claim title/key_risks/market_sentiment)
    expect(body).toHaveProperty("market_mood");
    expect(body).toHaveProperty("greeting");
    expect(body).toHaveProperty("top_insight");
    if (body.sections.length > 0) {
      for (const key of ["title", "headline", "detail", "sentiment", "value"]) {
        expect(body.sections[0], `missing ${key}`).toHaveProperty(key);
      }
    }
  });

  test("GET /api/anomaly/scores returns composite + component_scores", async ({ request }) => {
    const res = await request.get(`${API}/api/anomaly/scores`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("composite_score");
    expect(body).toHaveProperty("risk_level");
    // Real breakdown key (the page used to read a nonexistent `breakdown`)
    expect(body).toHaveProperty("component_scores");
    expect(Array.isArray(body.anomalies)).toBeTruthy();
  });

  test("GET /api/feed-cost/latest uses margin_trend", async ({ request }) => {
    const res = await request.get(`${API}/api/feed-cost/latest`);
    if (res.status() === 404) return; // documented degraded path
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("margin_pct");
    expect(body).toHaveProperty("margin_trend");
    expect(body).toHaveProperty("fcr");
  });

  test("GET /api/global-supply matches the real to_dict shape", async ({ request }) => {
    const res = await request.get(`${API}/api/global-supply`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("balance");
    expect(body).toHaveProperty("supply_deficit_pct");
    expect(body).toHaveProperty("norway_premium_pct");
    expect(body).toHaveProperty("global_salmon_usd_kg");
    expect(body).toHaveProperty("price_pressure");
    expect(body).toHaveProperty("countries");
  });

  test("GET /api/disease/by-company uses lowercase isa/pd", async ({ request }) => {
    const res = await request.get(`${API}/api/disease/by-company`);
    expect(res.ok()).toBeTruthy();
    const body = (await res.json()) as { companies?: Record<string, Record<string, unknown>> };
    const rows = Object.values(body.companies ?? {});
    if (rows.length > 0) {
      const counts = rows[0];
      expect(counts["total"]).toBeDefined();
      expect(counts["isa"]).toBeDefined();
      expect(counts["pd"]).toBeDefined();
      // The investor page used to read uppercase ISA/PD (always "Clear")
      expect(Object.keys(counts)).not.toContain("ISA");
      expect(Object.keys(counts)).not.toContain("PD");
    }
  });

  test("GET /api/regime/states rows carry current_color", async ({ request }) => {
    const res = await request.get(`${API}/api/regime/states`);
    expect(res.ok()).toBeTruthy();
    const body = (await res.json()) as Array<Record<string, unknown>>;
    expect(Array.isArray(body)).toBeTruthy();
    if (body.length > 0) {
      expect(body[0]).toHaveProperty("production_area");
      expect(body[0]).toHaveProperty("current_color");
      expect(body[0]).toHaveProperty("probabilities");
    }
  });

  test("GET /api/market/equity-prices exposes prices_nok benchmarks", async ({ request }) => {
    const res = await request.get(`${API}/api/market/equity-prices`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("prices_nok");
    expect(body).toHaveProperty("benchmarks");
  });

  test("GET /api/esg/scores rows carry grade + total", async ({ request }) => {
    const res = await request.get(`${API}/api/esg/scores`);
    expect(res.ok()).toBeTruthy();
    const body = (await res.json()) as Record<string, unknown> | unknown[];
    const rows = Array.isArray(body) ? body : ((body?.data ?? body?.companies) as unknown[] | undefined) ?? [];
    if (rows.length > 0) {
      const row = rows[0] as Record<string, unknown>;
      expect(row["company_name"]).toBeDefined();
      expect(row["total"]).toBeDefined();
      expect(row["grade"]).toBeDefined();
    }
  });

  test("GET /api/competitiveness/origin-index carries real origin rows", async ({ request }) => {
    const res = await request.get(`${API}/api/competitiveness/origin-index`);
    expect(res.ok()).toBeTruthy();
    const body = (await res.json()) as {
      origins: Array<Record<string, unknown>>;
      us_spot_usd_kg: number;
      data_quality: string;
      fallback_value: boolean;
    };
    expect(body).toHaveProperty("us_spot_usd_kg");
    expect(body).toHaveProperty("data_quality");
    expect(body).toHaveProperty("fallback_value");
    if (body.origins.length > 0) {
      const origin = body.origins[0];
      // Old fiction keys must not reappear
      expect(origin["production_cost_nok_kg"]).toBeUndefined();
      expect(origin["total_cif_usd_kg"]).toBeUndefined();
      expect(origin["total_delivered_usd"]).toBeDefined();
      expect(origin["margin_pct"]).toBeDefined();
    }
  });

  test("POST /api/competitiveness/tariff-scenario returns re-ranking", async ({ request }) => {
    await request.get(`${API}/api/competitiveness/origin-index`); // warm cache
    const res = await request.post(`${API}/api/competitiveness/tariff-scenario`, {
      data: { Norway: 10 },
    });
    expect(res.ok()).toBeTruthy();
    const body = (await res.json()) as {
      scenario_origins: Array<Record<string, unknown>>;
      tariff_overrides: Record<string, unknown>;
    };
    expect(body["scenario_origins"]).toBeInstanceOf(Array);
    expect(body["tariff_overrides"]).toBeDefined();
  });

  test("GET /api/supply/demand-balance keeps the additive R7 contract", async ({ request }) => {
    const res = await request.get(`${API}/api/supply/demand-balance`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    // Legacy smolt-model fields must never disappear (additive-only policy)
    for (const legacy of [
      "horizon_months",
      "total_supply_tonnes",
      "total_demand_tonnes",
      "balance_tonnes",
      "balance_pct",
      "signal",
      "price_pressure",
    ]) {
      expect(body, `legacy field ${legacy} missing`).toHaveProperty(legacy);
    }
    // Additive R7 integration payload
    expect(body).toHaveProperty("integration");
    expect(body).toHaveProperty("supply_breakdown");
    expect(body).toHaveProperty("demand_breakdown");
    expect(body).toHaveProperty("price_forecast");
    expect(body.data_provenance).toBeTruthy();
    if (body.price_forecast) {
      // 2..20 weeks -> 19 points; bands must be ordered when present
      expect(body.price_forecast.weekly.length).toBe(19);
    }
  });
});

test.describe("ML Models", () => {
  test("GET /api/ml/chronos/price-forecast returns forecast", async ({ request }) => {
    const res = await request.get(`${API}/api/ml/chronos/price-forecast`);
    // ML endpoints may fail if models not loaded, but should not 500
    expect(res.status()).toBeLessThan(500);
  });

  test("GET /api/ml/timesfm/price-forecast returns forecast", async ({ request }) => {
    const res = await request.get(`${API}/api/ml/timesfm/price-forecast`);
    expect(res.status()).toBeLessThan(500);
  });

  test("GET /api/ml/ensemble/price-forecast returns ensemble", async ({ request }) => {
    const res = await request.get(`${API}/api/ml/ensemble/price-forecast`);
    expect(res.status()).toBeLessThan(500);
  });
});

test.describe("Country Data", () => {
  test("GET /api/canada/snapshot returns BC data", async ({ request }) => {
    const res = await request.get(`${API}/api/canada/snapshot`);
    expect(res.ok()).toBeTruthy();
  });

  test("GET /api/iceland/snapshot returns data", async ({ request }) => {
    const res = await request.get(`${API}/api/iceland/snapshot`);
    expect(res.ok()).toBeTruthy();
  });

  test("GET /api/scotland/snapshot returns data", async ({ request }) => {
    const res = await request.get(`${API}/api/scotland/snapshot`);
    expect(res.ok()).toBeTruthy();
  });

  test("GET /api/faroe/snapshot returns data", async ({ request }) => {
    const res = await request.get(`${API}/api/faroe/snapshot`);
    expect(res.ok()).toBeTruthy();
  });
});

test.describe("Notifications & Alerts", () => {
  test("GET /api/notifications/alerts returns alert array", async ({ request }) => {
    const res = await request.get(`${API}/api/notifications/alerts`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const alerts = Array.isArray(body) ? body : body.alerts || [];
    expect(Array.isArray(alerts)).toBeTruthy();
  });
});

test.describe("Compliance", () => {
  test("GET /api/regulatory/traffic-light/current returns PA status", async ({ request }) => {
    const res = await request.get(`${API}/api/regulatory/traffic-light/current`);
    expect(res.ok()).toBeTruthy();
  });

  test("GET /api/compliance/asc/checklist returns checks", async ({ request }) => {
    const res = await request.get(`${API}/api/compliance/asc/checklist`);
    expect(res.ok()).toBeTruthy();
  });
});

test.describe("Admin (auth-gated)", () => {
  /**
   * Session 38 CRIT #2 contract, mirrored from tests/test_api_routes.py:
   *   anonymous -> 401, authenticated non-admin -> 403, admin -> 200.
   * Admin is granted only via User.role or FISHINTEL_ADMIN_EMAILS on the
   * server (bootstrap path) — self-serve registration cannot escalate.
   * The CI job sets FISHINTEL_ADMIN_EMAILS=ci-admin@fishintel.test.
   */
  const ADMIN_EMAIL = "ci-admin@fishintel.test";
  const ADMIN_PASSWORD = "ci-admin-password-123!";
  const USER_EMAIL = "ci-user@fishintel.test";
  const USER_PASSWORD = "ci-user-password-123!";
  const ADMIN_PATHS = [
    "/api/admin/status",
    "/api/admin/export-summary",
    "/api/cache/stats",
  ];

  async function registerOrLogin(
    ctx: import("@playwright/test").APIRequestContext,
    email: string,
    password: string,
    role: string,
  ): Promise<string> {
    const payload = { email, password, role };
    let res = await ctx.post(`${API}/api/auth/register`, { data: payload });
    if (!res.ok()) {
      // 400 = already registered (re-runs); fall back to login.
      res = await ctx.post(`${API}/api/auth/login`, { data: { email, password } });
    }
    expect(res.ok(), `register/login failed for ${email}`).toBeTruthy();
    const { token } = await res.json();
    expect(token).toBeTruthy();
    return token;
  }

  test("admin endpoints reject unauthenticated requests (401)", async ({ request }) => {
    for (const path of ADMIN_PATHS) {
      const res = await request.get(`${API}${path}`);
      expect(res.status(), `${path} must be 401 without credentials`).toBe(401);
    }
  });

  test("authenticated non-admin is forbidden (403)", async ({ playwright }) => {
    const ctx = await playwright.request.newContext();
    const token = await registerOrLogin(ctx, USER_EMAIL, USER_PASSWORD, "farmer");
    const res = await ctx.get(`${API}/api/admin/status`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(403);
    await ctx.dispose();
  });

  test("admin via FISHINTEL_ADMIN_EMAILS passes the gate (200)", async ({ playwright }) => {
    const ctx = await playwright.request.newContext();
    const token = await registerOrLogin(ctx, ADMIN_EMAIL, ADMIN_PASSWORD, "analyst");
    const headers = { Authorization: `Bearer ${token}` };

    const status = await ctx.get(`${API}/api/admin/status`, { headers });
    expect(status.ok()).toBeTruthy();

    const exportSummary = await ctx.get(`${API}/api/admin/export-summary`, { headers });
    expect(exportSummary.ok()).toBeTruthy();
    expect(await exportSummary.json()).toHaveProperty("datasets");

    const cacheStats = await ctx.get(`${API}/api/cache/stats`, { headers });
    expect(cacheStats.ok()).toBeTruthy();
    await ctx.dispose();
  });
});
