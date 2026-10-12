import bundleAnalyzer from "@next/bundle-analyzer";

const withBundleAnalyzer = bundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",

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

  // Explicit choice required when cacheComponents is on. `false` preserves
  // today's prefetch behavior; switching to App-Shell prefetching (`true`) is
  // the next-cache-components-optimizer skill's post-adoption step.
  partialPrefetching: false,

  // Reduce bundle size by excluding server-only packages from client bundles
  serverExternalPackages: ["sharp"],

  // Tree-shake large icon/chart libraries — saves 50-100KB
  experimental: {
    optimizePackageImports: ["lucide-react", "recharts", "framer-motion", "@deck.gl/core", "@deck.gl/layers", "maplibre-gl"],

    // @next/playwright `instant()` lock — needed only in the e2e prod rig.
    // Never enable on live deployments (per @next/playwright README).
    exposeTestingApiInProductionBuild: process.env.FISHINTEL_E2E === "1",
  },
};

export default withBundleAnalyzer(nextConfig);
