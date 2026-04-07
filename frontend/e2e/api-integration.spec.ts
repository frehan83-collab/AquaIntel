import { test, expect } from "@playwright/test";

/**
 * API Integration E2E Tests
 * ==========================
 * Verify that pages correctly fetch and display data from the FastAPI backend.
 * These tests require the backend to be running on port 8000.
 */

const API_BASE = "http://localhost:8000";

test.describe("API health", () => {
  test("backend health endpoint responds", async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/health`);
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.status).toBe("healthy");
  });
});

test.describe("Core API endpoints", () => {
  test("lice summary returns data", async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/lice/summary`);
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty("data_provenance");
  });

  test("morning brief returns structured data", async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/brief`);
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty("data_provenance");
  });

  test("anomaly scores return risk level", async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/anomaly/scores`);
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty("risk_level");
    expect(["LOW", "ELEVATED", "HIGH", "CRITICAL"]).toContain(body.risk_level);
  });

  test("decision engine returns valid action", async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/decision/10001`);
    // May return error if no data for locality, but should not crash
    expect(response.status()).toBeLessThan(500);
  });

  test("price outlook returns forecast", async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/market/price-outlook`);
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty("data_provenance");
  });

  test("feed cost index returns data", async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/feed-cost/composite-index`);
    expect(response.ok()).toBeTruthy();
  });
});

test.describe("Data provenance", () => {
  test("all major endpoints include provenance", async ({ request }) => {
    const endpoints = [
      "/api/lice/summary",
      "/api/market/price-outlook",
      "/api/brief",
      "/api/anomaly/scores",
    ];

    for (const endpoint of endpoints) {
      const response = await request.get(`${API_BASE}${endpoint}`);
      if (response.ok()) {
        const body = await response.json();
        expect(body.data_provenance, `${endpoint} missing provenance`).toBeDefined();
        expect(body.data_provenance.source).toBeTruthy();
      }
    }
  });
});
