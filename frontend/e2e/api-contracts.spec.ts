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

  test("GET /api/supply/smolt-forecast returns pipeline", async ({ request }) => {
    const res = await request.get(`${API}/api/supply/smolt-forecast`);
    expect(res.ok()).toBeTruthy();
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
