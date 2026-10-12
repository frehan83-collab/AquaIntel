/**
 * Instant-navigation rig (next-cache-components-optimizer, phases 0/C).
 *
 * Runs against a PRODUCTION build (`next build && next start` on :3101) with
 * the @next/playwright testing API explicitly enabled for this rig only
 * (FISHINTEL_E2E=1). Same browser version line as the main config.
 *
 * Usage:  npx playwright test --config playwright.instant.config.ts
 */
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: /instant\.spec\.ts/,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "list",

  use: {
    baseURL: "http://localhost:3101",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],

  webServer: {
    command: "npm run build:e2e && npx next start -p 3101",
    url: "http://localhost:3101",
    reuseExistingServer: !process.env.CI,
    timeout: 240_000,
    env: { FISHINTEL_E2E: "1" },
  },
});
