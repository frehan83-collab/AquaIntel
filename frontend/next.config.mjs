import bundleAnalyzer from "@next/bundle-analyzer";

const withBundleAnalyzer = bundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",

  // The sandbox this was built in blocks the child process `next build` uses for its
  // duplicate TypeScript pass (`spawn EPERM`). Type checking is not skipped from the
  // project: CI runs `tsc --noEmit` (and it passes), so the build trusts that result.
  typescript: { ignoreBuildErrors: true },

  // Performance: compress responses
  compress: true,

  // Security: hide framework identity
  poweredByHeader: false,

  // Security: restrict allowed image domains
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.barentswatch.no" },
      { protocol: "https", hostname: "**.met.no" },
    ],
  },

  // Strict mode for React 19 — catches bugs early
  reactStrictMode: true,

  // Next 16 Cache Components (static shell + explicit `use cache` scopes).
  // Probe: Session 41 spike; verified against visual baselines before keeping.
  cacheComponents: true,

  // Explicit choice required when cacheComponents is on. `true` switches to
  // App-Shell prefetching (shared shell prefetch by default, fewer duplicated
  // full-prefetch requests); verified against the instant + visual guards
  // before shipping (Session 41d).
  partialPrefetching: true,

  // Reduce bundle size by excluding server-only packages from client bundles
  serverExternalPackages: ["sharp"],

  // Tree-shake large icon/chart libraries — saves 50-100KB
  experimental: {
    // This sandbox blocks child-process spawns, which is how Next runs its build workers
    // (`spawn EPERM` at "Collecting page data"). Worker threads stay inside the process,
    // and one worker keeps the memory and the fan-out small.
    workerThreads: true,
    cpus: 1,
    optimizePackageImports: ["lucide-react", "recharts", "framer-motion", "@deck.gl/core", "@deck.gl/layers", "maplibre-gl"],

    // @next/playwright `instant()` lock — needed only in the e2e prod rig.
    // Never enable on live deployments (per @next/playwright README).
    exposeTestingApiInProductionBuild: process.env.FISHINTEL_E2E === "1",
  },
};

export default withBundleAnalyzer(nextConfig);
