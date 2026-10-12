import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

// ESLint 9 flat config (Next.js 16 removed `next lint`).
// eslint-config-next@16 ships native flat-config arrays — no FlatCompat needed.
const eslintConfig = [
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": "warn",
      // React-Compiler-era rules shipped by eslint-plugin-react-hooks v6
      // (arrived with the Next 16 upgrade). Aspirational until the React
      // Compiler build is enabled — track as warnings, do not block CI.
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/immutability": "warn",
      "react-hooks/static-components": "warn",
      "react-hooks/purity": "warn",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "out/**",
      "src/types/generated.ts", // machine-generated from OpenAPI
    ],
  },
];

export default eslintConfig;
