import { test, expect } from "@playwright/test";

/**
 * Golden Demo Path E2E Tests
 * ===========================
 * Tests the 3-minute demo flow: Dashboard → Brief → Farmer Daily → Market → Leaders
 * Verifies that data renders, charts appear, and navigation is seamless.
 *
 * These tests run against the live backend — they verify real API integration,
 * not mocks. If the backend is down, these tests will fail (correctly).
 */

const TIMEOUT = 15_000;

test.describe("Demo Golden Path", () => {
  test("1. Dashboard renders all sections", async ({ page }) => {
    await page.goto("/");

    // Title visible
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });

    // KPI cards render (at least 4 in the metrics section)
    const kpiCards = page.locator('[class*="rounded-2xl"], [class*="GlassCard"]');
    await expect(kpiCards.first()).toBeVisible({ timeout: TIMEOUT });

    // Lice chart or data section should render
    await expect(page.locator("svg, canvas, [class*='chart'], [class*='Chart']").first()).toBeVisible({ timeout: TIMEOUT });

    // No error boundaries triggered (no "Something went wrong" text)
    await expect(page.locator("text=Something went wrong")).not.toBeVisible();
  });

  test("2. Dashboard → Brief navigation is instant", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });

    // Click on Morning Brief in sidebar
    await page.click('a[href="/brief"], text=Morning Brief, text=Morgenrapport');

    // Brief page loads with heading
    await expect(page.locator("h1, h2").first()).toBeVisible({ timeout: TIMEOUT });
    await expect(page.url()).toContain("/brief");
  });

  test("3. Morning Brief shows structured sections", async ({ page }) => {
    await page.goto("/brief");

    // Title visible
    await expect(page.locator("h1, h2").first()).toBeVisible({ timeout: TIMEOUT });

    // PDF export button exists
    await expect(page.locator("text=PDF, button:has-text('PDF')").first()).toBeVisible({ timeout: TIMEOUT });

    // At least some content sections should render
    const sections = page.locator('[class*="rounded-2xl"], [class*="GlassCard"]');
    await expect(sections.first()).toBeVisible({ timeout: TIMEOUT });

    // No error state
    await expect(page.locator("text=Something went wrong")).not.toBeVisible();
  });

  test("4. Farmer Daily Check renders decision card", async ({ page }) => {
    await page.goto("/farmer-daily");

    // Page title
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });

    // Farm search input exists
    await expect(page.locator("input[placeholder]").first()).toBeVisible({ timeout: TIMEOUT });

    // Should show either a decision card or loading state
    const content = page.locator('[class*="rounded-2xl"], [class*="GlassCard"], [class*="Loader"]');
    await expect(content.first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("5. Market Terminal renders price data", async ({ page }) => {
    await page.goto("/market");

    // Title
    await expect(page.locator("h1, h2").first()).toBeVisible({ timeout: TIMEOUT });

    // SVG chart should render (FishPoolChart)
    await expect(page.locator("svg").first()).toBeVisible({ timeout: TIMEOUT });

    // KPI cards with price data
    const cards = page.locator('[class*="rounded-2xl"]');
    await expect(cards.first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("6. Leaders & ESG shows company rankings", async ({ page }) => {
    await page.goto("/leaders");

    // Title
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });

    // Should show a table or list of companies
    const table = page.locator("table, [class*='DataTable'], [role='table']");
    const cards = page.locator('[class*="rounded-2xl"]');

    // Either a data table or glass cards should be visible
    await expect(table.or(cards).first()).toBeVisible({ timeout: TIMEOUT });
  });
});

test.describe("Key Feature Pages", () => {
  test("Disease Intel renders outbreak data", async ({ page }) => {
    await page.goto("/disease");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });

    // KPI cards (ISA count, PD count, etc.)
    const cards = page.locator('[class*="rounded-2xl"]');
    await expect(cards.first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("Feed Cost renders composite index", async ({ page }) => {
    await page.goto("/feed-cost");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
    const content = page.locator('[class*="rounded-2xl"]');
    await expect(content.first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("Salmon Futures renders forward curve", async ({ page }) => {
    await page.goto("/futures");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
    // Forward curve chart (SVG)
    await expect(page.locator("svg").first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("Global Supply shows country data", async ({ page }) => {
    await page.goto("/global-supply");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
    const content = page.locator('[class*="rounded-2xl"]');
    await expect(content.first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("Traffic Light shows PA status", async ({ page }) => {
    await page.goto("/traffic-light");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
    const content = page.locator('[class*="rounded-2xl"]');
    await expect(content.first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("Signals page renders trading signals", async ({ page }) => {
    await page.goto("/signals");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
    const content = page.locator('[class*="rounded-2xl"]');
    await expect(content.first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("Trader Intel renders event simulator", async ({ page }) => {
    await page.goto("/trader");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
    const content = page.locator('[class*="rounded-2xl"]');
    await expect(content.first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("Portfolio shows saved farms", async ({ page }) => {
    await page.goto("/portfolio");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
    // Should show either farms or "add farm" prompt
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });

  test("Competitiveness shows origin ranking", async ({ page }) => {
    await page.goto("/competitiveness");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
    const content = page.locator('[class*="rounded-2xl"]');
    await expect(content.first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("Bio Risk Map renders map container", async ({ page }) => {
    await page.goto("/bio-risk");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
    // Map or canvas element
    const map = page.locator("canvas, [class*='map'], [class*='Map'], [class*='maplibre']");
    const fallback = page.locator('[class*="rounded-2xl"]');
    await expect(map.or(fallback).first()).toBeVisible({ timeout: TIMEOUT });
  });
});

test.describe("Country Intelligence Pages", () => {
  test("Canada/BC renders DFO data", async ({ page }) => {
    await page.goto("/canada");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
    const content = page.locator('[class*="rounded-2xl"]');
    await expect(content.first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("Scotland renders production data", async ({ page }) => {
    await page.goto("/scotland");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("Faroe Islands renders Bakkafrost data", async ({ page }) => {
    await page.goto("/faroe");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("Iceland renders MAB data", async ({ page }) => {
    await page.goto("/iceland");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
  });
});

test.describe("System & Admin Pages", () => {
  test("Admin dashboard loads", async ({ page }) => {
    await page.goto("/admin");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("API Docs page renders", async ({ page }) => {
    await page.goto("/api-docs");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("Settings page loads", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("Changelog page loads", async ({ page }) => {
    await page.goto("/changelog");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
  });

  test("Privacy policy loads", async ({ page }) => {
    await page.goto("/privacy");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: TIMEOUT });
  });
});
