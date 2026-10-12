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
    window.localStorage.setItem("openclaw_tour_completed", "true");
  });
}
