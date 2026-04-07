"use client";
import DemoBanner from "./DemoBanner";
import GuidedTour from "./GuidedTour";
import OnboardingWizard from "./OnboardingWizard";

/**
 * Client-side wrapper that renders the DemoBanner, GuidedTour, and OnboardingWizard.
 * Included in the root layout so all are available on every page.
 */
export default function DemoShell() {
  return (
    <>
      <DemoBanner />
      <GuidedTour />
      <OnboardingWizard />
    </>
  );
}
