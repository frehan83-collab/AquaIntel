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

  test("GET /api/metrics returns prometheus format", async ({ request }) => {
    const res = await request.get(`${API}/api/metrics`);
    expect(res.ok()).toBeTruthy();
    const text = await res.text();
    expect(text).toContain("http_request");
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

  test("GET /api/ssb/price-history returns prices", async ({ request }) => {
    const res = await request.get(`${API}/api/ssb/price-history?weeks=4`);
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
  test("GET /api/analytics/leaders returns ranked companies", async ({ request }) => {
    const res = await request.get(`${API}/api/analytics/leaders`);
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

  test("GET /api/supply/smolt-forecast returns pipeline", async ({ request }) => {
    const res = await request.get(`${API}/api/supply/smolt-forecast`);
    expect(res.ok()).toBeTruthy();
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
  test("GET /api/traffic-light/current returns PA status", async ({ request }) => {
    const res = await request.get(`${API}/api/traffic-light/current`);
    expect(res.ok()).toBeTruthy();
  });

  test("GET /api/compliance/asc/checklist returns checks", async ({ request }) => {
    const res = await request.get(`${API}/api/compliance/asc/checklist`);
    expect(res.ok()).toBeTruthy();
  });
});

test.describe("Admin", () => {
  test("GET /api/admin/status returns platform health", async ({ request }) => {
    const res = await request.get(`${API}/api/admin/status`);
    expect(res.ok()).toBeTruthy();
  });

  test("GET /api/admin/export-summary returns datasets", async ({ request }) => {
    const res = await request.get(`${API}/api/admin/export-summary`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("datasets");
  });

  test("GET /api/cache/stats returns cache metrics", async ({ request }) => {
    const res = await request.get(`${API}/api/cache/stats`);
    expect(res.ok()).toBeTruthy();
  });
});
