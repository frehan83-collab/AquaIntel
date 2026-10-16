import type { Page } from "@playwright/test";

/**
 * Deterministic e2e setup for the app specs (navigation / golden-path /
 * interactions).
 *
 * The first-visit OnboardingWizard gates on localStorage `oc_onboarded`
 * (src/components/OnboardingWizard.tsx) and renders a `fixed inset-0 z-[70]`
 * backdrop that intercepts pointer events on every fresh browser profile
 * (CI always) — the sidebar/hamburger behind it become unclickable.
 * Pre-mark it (plus the GuidedTour key) as completed before the app boots.
 *
 * NOTE: visual.spec.ts deliberately does NOT use this helper — its committed
 * baselines encode the current first-visit look; never change that here.
 */
export async function suppressOnboarding(page: Page): Promise<void> {
  await page.addInitScript(() => {
    window.localStorage.setItem("oc_onboarded", "true");
    window.localStorage.setItem("aquaintel_tour_completed", "true");
  });
}

/**
 * Block the PWA service worker (public/sw.js) for route-stubbed specs.
 *
 * sw.js intercepts ALL GET fetches (network-first, offline -> cache ->
 * 503 "Offline"). Once active it takes over the page's data fetches,
 * and service-worker fetches BYPASS page.route — route stubs silently
 * stop intercepting (observed: stubbed /api/china/demand answered 503
 * with zero route-handler hits). PWARegister registers /sw.js on mount;
 * stubbing navigator.serviceWorker.register keeps page.route in control.
 * Errors are swallowed by PWARegister's own .catch(() => {}).
 */
export async function blockServiceWorker(page: Page): Promise<void> {
  await page.addInitScript(() => {
    if ("serviceWorker" in navigator) {
      Object.defineProperty(navigator.serviceWorker, "register", {
        value: () => Promise.reject(new Error("SW disabled for this e2e spec")),
        configurable: true,
      });
    }
  });
}
