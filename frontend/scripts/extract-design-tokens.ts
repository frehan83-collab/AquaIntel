#!/usr/bin/env npx tsx
/**
 * Figma Design Token Extraction Pipeline
 * ========================================
 * Extracts design tokens from a Figma file and generates:
 * 1. CSS custom properties (tokens.css)
 * 2. Tailwind theme extension (tailwind.tokens.js)
 * 3. TypeScript theme object (theme.ts)
 *
 * Usage:
 *   FIGMA_ACCESS_TOKEN=xxx FIGMA_FILE_KEY=xxx npx tsx scripts/extract-design-tokens.ts
 *
 * If no Figma file exists yet, run with --generate-defaults to output
 * the current code-defined tokens in Figma-compatible format.
 */

import { FigmaClient, extractColorTokens } from "../src/lib/figma/client";
import * as fs from "fs";
import * as path from "path";

const TOKEN = process.env.FIGMA_ACCESS_TOKEN || "";
const FILE_KEY = process.env.FIGMA_FILE_KEY || "";
const OUTPUT_DIR = path.resolve(__dirname, "../src/styles");
const GENERATE_DEFAULTS = process.argv.includes("--generate-defaults");

// ── Current code-defined tokens (source of truth until Figma file exists) ──

const CODE_TOKENS = {
  light: {
    "--bg-primary": "#F8FAFB",
    "--bg-secondary": "#EFF3F6",
    "--bg-card": "rgba(0, 0, 0, 0.03)",
    "--accent": "#00A89F",
    "--accent-dim": "rgba(0, 168, 159, 0.12)",
    "--text-primary": "#1A2332",
    "--text-secondary": "#5A6B7D",
    "--border": "rgba(0, 0, 0, 0.08)",
    "--danger": "#F43F5E",
    "--success": "#10B981",
    "--warning": "#F59E0B",
    "--salmon": "#E8734A",
    "--color-biomass": "#F59E0B",
    "--color-lice": "#F43F5E",
    "--color-temperature": "#3B82F6",
    "--color-mortality": "#9F1239",
    "--color-feeding": "#059669",
    "--color-oxygen": "#06B6D4",
    "--color-traffic-green": "#22C55E",
    "--color-traffic-yellow": "#EAB308",
    "--color-traffic-red": "#EF4444",
    "--color-positive": "#34D399",
    "--color-negative": "#FB7185",
    "--color-warning": "#FBBF24",
    "--chart-1": "#00D4C8",
    "--chart-2": "#E8734A",
    "--chart-3": "#8B5CF6",
    "--chart-4": "#F59E0B",
    "--chart-5": "#EC4899",
    "--chart-6": "#10B981",
    "--chart-7": "#6366F1",
    "--chart-8": "#14B8A6",
    "--surface-0": "#F8FAFB",
    "--surface-1": "#FFFFFF",
    "--surface-2": "#F1F5F9",
    "--surface-3": "#E2E8F0",
    "--surface-4": "#CBD5E1",
  },
  dark: {
    "--bg-primary": "#060F1C",
    "--bg-secondary": "#0A1A2F",
    "--bg-card": "rgba(255, 255, 255, 0.04)",
    "--accent": "#00D4C8",
    "--accent-dim": "rgba(0, 212, 200, 0.15)",
    "--text-primary": "#E8EDF2",
    "--text-secondary": "#8899AA",
    "--border": "rgba(255, 255, 255, 0.06)",
    "--danger": "#F43F5E",
    "--success": "#10B981",
    "--warning": "#F59E0B",
    "--salmon": "#E8734A",
    "--color-biomass": "#F59E0B",
    "--color-lice": "#F43F5E",
    "--color-temperature": "#3B82F6",
    "--color-mortality": "#9F1239",
    "--color-feeding": "#059669",
    "--color-oxygen": "#06B6D4",
    "--color-traffic-green": "#22C55E",
    "--color-traffic-yellow": "#EAB308",
    "--color-traffic-red": "#EF4444",
    "--color-positive": "#34D399",
    "--color-negative": "#FB7185",
    "--color-warning": "#FBBF24",
    "--chart-1": "#00D4C8",
    "--chart-2": "#E8734A",
    "--chart-3": "#8B5CF6",
    "--chart-4": "#F59E0B",
    "--chart-5": "#EC4899",
    "--chart-6": "#10B981",
    "--chart-7": "#6366F1",
    "--chart-8": "#14B8A6",
    "--surface-0": "#060F1C",
    "--surface-1": "#0A1629",
    "--surface-2": "#0F1D33",
    "--surface-3": "#152640",
    "--surface-4": "#1A2F4D",
  },
};

const TYPOGRAPHY = {
  "--text-xs": "0.75rem",
  "--text-sm": "0.875rem",
  "--text-base": "1rem",
  "--text-lg": "1.125rem",
  "--text-xl": "1.25rem",
  "--text-2xl": "1.5rem",
  "--text-3xl": "1.875rem",
  "--text-4xl": "2.25rem",
  "--font-sans": "'DM Sans', system-ui, -apple-system, sans-serif",
  "--font-display": "'DM Serif Display', Georgia, serif",
  "--font-mono": "'JetBrains Mono', 'Fira Code', monospace",
};

const SPACING = {
  "--space-1": "4px",
  "--space-2": "8px",
  "--space-3": "12px",
  "--space-4": "16px",
  "--space-5": "20px",
  "--space-6": "24px",
  "--space-8": "32px",
  "--space-10": "40px",
  "--space-12": "48px",
  "--space-16": "64px",
};

const RADIUS = {
  "--radius-sm": "6px",
  "--radius-md": "8px",
  "--radius-lg": "12px",
  "--radius-xl": "16px",
  "--radius-2xl": "20px",
  "--radius-full": "9999px",
};

// ── Output Generators ────────────────────────────────────────────

function generateCssFile(tokens: Record<string, Record<string, string>>): string {
  let css = "/* Auto-generated design tokens — do not edit manually */\n";
  css += "/* Source: Figma file or code-defined defaults */\n";
  css += `/* Generated: ${new Date().toISOString()} */\n\n`;

  css += ":root {\n";
  for (const [key, value] of Object.entries(tokens.light || {})) {
    css += `  ${key}: ${value};\n`;
  }
  for (const [key, value] of Object.entries(TYPOGRAPHY)) {
    css += `  ${key}: ${value};\n`;
  }
  for (const [key, value] of Object.entries(SPACING)) {
    css += `  ${key}: ${value};\n`;
  }
  for (const [key, value] of Object.entries(RADIUS)) {
    css += `  ${key}: ${value};\n`;
  }
  css += "}\n\n";

  css += ".dark {\n";
  for (const [key, value] of Object.entries(tokens.dark || {})) {
    css += `  ${key}: ${value};\n`;
  }
  css += "}\n";

  return css;
}

function generateTailwindTokens(tokens: Record<string, Record<string, string>>): string {
  const colors: Record<string, string> = {};
  const darkColors = tokens.dark || {};

  for (const [key] of Object.entries(tokens.light || {})) {
    const name = key.replace(/^--/, "").replace(/-/g, ".");
    colors[name] = `var(${key})`;
  }

  return `// Auto-generated Tailwind token extension
// Source: design tokens pipeline
// Generated: ${new Date().toISOString()}

module.exports = {
  theme: {
    extend: {
      colors: ${JSON.stringify(colors, null, 8)},
    },
  },
};
`;
}

function generateThemeTs(tokens: Record<string, Record<string, string>>): string {
  return `// Auto-generated TypeScript theme object
// Source: design tokens pipeline
// Generated: ${new Date().toISOString()}

export const theme = {
  light: ${JSON.stringify(tokens.light, null, 4)},
  dark: ${JSON.stringify(tokens.dark, null, 4)},
  typography: ${JSON.stringify(TYPOGRAPHY, null, 4)},
  spacing: ${JSON.stringify(SPACING, null, 4)},
  radius: ${JSON.stringify(RADIUS, null, 4)},
} as const;

export type ThemeMode = "light" | "dark";
export type ThemeTokens = typeof theme.light;
`;
}

// ── Main ─────────────────────────────────────────────────────────

async function main() {
  console.log("🎨 Design Token Extraction Pipeline");
  console.log("====================================\n");

  // Ensure output directory exists
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  let tokens = CODE_TOKENS;

  if (TOKEN && FILE_KEY && !GENERATE_DEFAULTS) {
    // Extract from Figma
    console.log("📡 Connecting to Figma API...");
    const client = new FigmaClient(TOKEN);

    try {
      const user = await client.testConnection();
      console.log(`✓ Connected as ${user.handle} (${user.email})\n`);

      console.log("📦 Fetching variables from file...");
      const { variables, variableCollections } = await client.getVariables(FILE_KEY);

      const varCount = Object.keys(variables).length;
      const collectionCount = Object.keys(variableCollections).length;
      console.log(`✓ Found ${varCount} variables in ${collectionCount} collections\n`);

      if (varCount > 0) {
        const figmaTokens = extractColorTokens(variables, variableCollections);
        // Merge Figma tokens over code defaults (Figma is source of truth)
        tokens = {
          light: { ...CODE_TOKENS.light, ...figmaTokens["light"] },
          dark: { ...CODE_TOKENS.dark, ...figmaTokens["dark"] },
        };
        console.log("✓ Figma tokens merged (Figma overrides code defaults)\n");
      } else {
        console.log("⚠ No variables found in Figma file — using code defaults\n");
      }
    } catch (err) {
      console.error("⚠ Figma API error:", (err as Error).message);
      console.log("  Falling back to code-defined defaults\n");
    }
  } else {
    console.log("📋 Using code-defined design tokens (no Figma file configured)\n");
    console.log("  To connect Figma: set FIGMA_ACCESS_TOKEN and FIGMA_FILE_KEY\n");
  }

  // Generate output files
  const cssContent = generateCssFile(tokens);
  const tailwindContent = generateTailwindTokens(tokens);
  const themeContent = generateThemeTs(tokens);

  fs.writeFileSync(path.join(OUTPUT_DIR, "tokens.css"), cssContent);
  fs.writeFileSync(path.join(OUTPUT_DIR, "tailwind.tokens.js"), tailwindContent);
  fs.writeFileSync(path.join(OUTPUT_DIR, "theme.ts"), themeContent);

  console.log("✅ Generated files:");
  console.log(`   ${path.join(OUTPUT_DIR, "tokens.css")} (${Object.keys(tokens.light).length} light + ${Object.keys(tokens.dark).length} dark tokens)`);
  console.log(`   ${path.join(OUTPUT_DIR, "tailwind.tokens.js")} (Tailwind theme extension)`);
  console.log(`   ${path.join(OUTPUT_DIR, "theme.ts")} (TypeScript theme object)`);
  console.log(`\n🎨 Total: ${Object.keys(tokens.light).length + Object.keys(tokens.dark).length + Object.keys(TYPOGRAPHY).length + Object.keys(SPACING).length + Object.keys(RADIUS).length} design tokens`);
}

main().catch(console.error);
