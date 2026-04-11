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

  // Reduce bundle size by excluding server-only packages from client bundles
  serverExternalPackages: ["sharp"],

  // Tree-shake large icon/chart libraries — saves 50-100KB
  experimental: {
    optimizePackageImports: ["lucide-react", "recharts", "framer-motion", "@deck.gl/core", "@deck.gl/layers", "maplibre-gl"],
  },
};

export default withBundleAnalyzer(nextConfig);
