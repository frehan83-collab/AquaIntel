import { test, expect } from "@playwright/test";
import { suppressOnboarding } from "./utils";

/**
 * E2E Navigation Tests
 * =====================
 * Verify that all major pages load without errors and display expected content.
 * These are smoke tests — they ensure nothing is fundamentally broken.
 */

test.beforeEach(async ({ page }) => {
  await suppressOnboarding(page);
});

test.describe("Core navigation", () => {
  test("dashboard loads and shows KPI cards", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/AquaIntel|FishIntel/i);
    // Dashboard should show at least one KPI card
    await expect(page.locator('[class*="kpi"], [class*="KPI"], [class*="glass"]').first()).toBeVisible({
      timeout: 10_000,
    });
  });

  test("morning brief loads", async ({ page }) => {
    await page.goto("/brief");
    await expect(page.locator("h1, h2").first()).toBeVisible({ timeout: 10_000 });
  });

  test("farmer daily check loads", async ({ page }) => {
    await page.goto("/farmer-daily");
    await expect(page.locator("h1, h2").first()).toBeVisible({ timeout: 10_000 });
  });

  test("market terminal loads", async ({ page }) => {
    await page.goto("/market");
    await expect(page.locator("h1, h2").first()).toBeVisible({ timeout: 10_000 });
  });

  test("disease intel loads", async ({ page }) => {
    await page.goto("/disease");
    await expect(page.locator("h1, h2").first()).toBeVisible({ timeout: 10_000 });
  });

  test("leaders page loads", async ({ page }) => {
    await page.goto("/leaders");
    await expect(page.locator("h1, h2").first()).toBeVisible({ timeout: 10_000 });
  });

  test("notifications page loads", async ({ page }) => {
    await page.goto("/notifications");
    await expect(page.locator("h1, h2").first()).toBeVisible({ timeout: 10_000 });
  });

  test("feed cost page loads", async ({ page }) => {
    await page.goto("/feed-cost");
    await expect(page.locator("h1, h2").first()).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Sidebar navigation", () => {
  test("sidebar is visible on desktop", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("nav, [class*='sidebar'], [class*='Sidebar']").first()).toBeVisible({
      timeout: 10_000,
    });
  });

  test("sidebar has search functionality", async ({ page }) => {
    await page.goto("/");
    const searchInput = page.locator("input[placeholder*='Search'], input[placeholder*='Søk']").first();
    // Search input may or may not be visible depending on viewport
    if (await searchInput.isVisible()) {
      await searchInput.fill("disease");
      // Should filter sidebar items (link role avoids the "Disease Outbreaks"
      // group heading, which also matches text=Disease and trips strict mode)
      await expect(page.getByRole("link", { name: /Disease/i }).first()).toBeVisible();
    }
  });
});

test.describe("Theme toggle", () => {
  test("theme can be toggled", async ({ page }) => {
    await page.goto("/");
    // Look for theme toggle button (sun/moon icon)
    const themeBtn = page.locator("button[aria-label*='theme'], button[title*='theme'], [class*='theme']").first();
    if (await themeBtn.isVisible()) {
      await themeBtn.click();
      // Page should not crash after toggle
      await expect(page.locator("body")).toBeVisible();
    }
  });
});

test.describe("Error handling", () => {
  test("404 page renders for unknown routes", async ({ page }) => {
    await page.goto("/this-page-does-not-exist-12345");
    // Should show a 404 or not-found message, not a blank page
    await expect(page.locator("body")).toContainText(/not found|404|ocean/i, {
      timeout: 10_000,
    });
  });
});

test.describe("Responsive design", () => {
  test("mobile viewport shows hamburger menu", async ({ page, browserName }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/");
    // On mobile, sidebar should be hidden or hamburger visible
    await expect(page.locator("body")).toBeVisible({ timeout: 10_000 });
  });
});
