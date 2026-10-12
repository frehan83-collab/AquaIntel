import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E Test Configuration
 * ==================================
 * Runs against the Next.js dev server (port 3001) and FastAPI backend (port 8000).
 * Setup: npx playwright install --with-deps chromium
 *
 * Reference: https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: "./e2e",
  // instant.spec.ts belongs to the prod rig (playwright.instant.config.ts)
  testIgnore: /instant\.spec\.ts/,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",

  use: {
    baseURL: "http://localhost:3001",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile",
      use: { ...devices["Pixel 5"] },
    },
  ],

  /* Start dev server before running tests */
  webServer: [
    {
      command: "npm run dev",
      url: "http://localhost:3001",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
