/**
 * Instant-navigation guard (next-cache-components-optimizer, phase C).
 *
 * Contract: on an INITIAL LOAD (hard navigation), the route's static shell
 * must commit without waiting for any dynamic data. The @next/playwright
 * `instant()` lock defers dynamic data while the callback runs, so the
 * assertions inside the callback can ONLY observe cached/shell content —
 * if the shell is missing (a blocking boundary, a lost prerender), the test
 * fails deterministically.
 *
 * Rig: production build via playwright.instant.config.ts (port 3101).
 * Client API calls are stubbed so data timing never affects the verdict.
 */
import { test, expect } from "@playwright/test";
import { instant } from "@next/playwright";

const BASE_URL = process.env.INSTANT_BASE_URL ?? "http://localhost:3101";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
  );
});

const ROUTES: Array<[path: string, name: string]> = [
  ["/", "dashboard"],
  ["/market", "market"],
  ["/traffic-light", "traffic-light"],
  ["/brief", "brief"],
  ["/farmer-daily", "farmer-daily"],
  ["/disease", "disease"],
  ["/leaders", "leaders"],
  ["/futures", "futures"],
  ["/feed-cost", "feed-cost"],
  ["/global-supply", "global-supply"],
  ["/notifications", "notifications"],
];

for (const [path, name] of ROUTES) {
  test(`instant shell: ${name} initial load`, async ({ page }) => {
    await instant(
      page,
      async () => {
        await page.goto(`${BASE_URL}${path}`);

        // Shell landmarks come from the root layout and must be committed
        // immediately — no data, no hydration wait.
        await expect(page.locator("main#main-content")).toBeVisible();
        await expect(page.locator("nav").first()).toBeVisible();
      },
      { baseURL: BASE_URL }
    );
  });
}
