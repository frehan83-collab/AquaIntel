#!/usr/bin/env npx tsx
/**
 * Figma Design Token Extraction Pipeline (Session 39)
 * ====================================================
 * Source of truth: docs/figma-tokens.json (Tokens Studio format)
 * Generates: tokens.css, tailwind.tokens.js, theme.ts, figma-variables.json
 *
 * Modes:
 *   (1) offline    — read docs/figma-tokens.json, generate outputs
 *   (2) pull       — fetch from Figma REST, merge over figma-tokens.json
 *   (3) push       — upload figma-tokens.json to Figma Variables via REST
 *
 * Environment:
 *   FIGMA_ACCESS_TOKEN — personal access token (for pull/push)
 *   FIGMA_FILE_KEY     — target file key       (for pull/push)
 *
 * Usage:
 *   npx tsx scripts/extract-design-tokens.ts              # offline (default)
 *   npx tsx scripts/extract-design-tokens.ts --pull       # fetch from Figma
 *   npx tsx scripts/extract-design-tokens.ts --push       # push to Figma
 *   npx tsx scripts/extract-design-tokens.ts --dry-run    # preview output sizes
 */

import { FigmaClient } from "../src/lib/figma/client";
import * as fs from "fs";
import * as path from "path";

const TOKEN = process.env.FIGMA_ACCESS_TOKEN || "";
const FILE_KEY = process.env.FIGMA_FILE_KEY || "";
const OUTPUT_DIR = path.resolve(__dirname, "../src/styles");
const TOKENS_SOURCE = path.resolve(__dirname, "../../docs/figma-tokens.json");
const TOKENS_STUDIO_SOURCE = path.resolve(__dirname, "../../docs/figma-tokens-studio.json");
const FIGMA_VARIABLES_OUT = path.resolve(__dirname, "../../docs/figma-variables-payload.json");

const MODE = process.argv.includes("--pull") ? "pull"
  : process.argv.includes("--push") ? "push"
  : process.argv.includes("--dry-run") ? "dry-run"
  : "offline";

// ── Types (Tokens Studio format) ────────────────────────────────────

interface TokenValue { value: string; type: string; description?: string }
type TokenNode = TokenValue | { [key: string]: TokenNode };

interface TokensStudioFile {
  $schema?: string;
  $metadata?: Record<string, unknown>;
  [set: string]: unknown;
}

// ── Flatten Tokens Studio into CSS vars ─────────────────────────────

function isLeaf(n: unknown): n is TokenValue {
  return !!n && typeof n === "object" && "value" in (n as object) && "type" in (n as object);
}

function flatten(node: TokenNode | unknown, prefix: string[] = [], out: Record<string, TokenValue> = {}): Record<string, TokenValue> {
  if (!node || typeof node !== "object") return out;
  if (isLeaf(node)) {
    out[prefix.join("-")] = node;
    return out;
  }
  for (const [k, v] of Object.entries(node as Record<string, unknown>)) {
    if (k.startsWith("$")) continue;
    flatten(v as TokenNode, [...prefix, k], out);
  }
  return out;
}

// Convert raw token value to CSS-usable value (add px to unitless sizes, etc.)
function formatValue(token: TokenValue): string {
  const v = token.value;
  switch (token.type) {
    case "fontSizes":
      return /px|rem|em|%$/.test(v) ? v : `${parseFloat(v) / 16}rem`;
    case "spacing":
    case "borderRadius":
    case "lineHeights":
      return /px|rem|em|%$|^[0-9.]+$/.test(v) && !v.includes("px") && !v.includes("rem")
        ? (token.type === "lineHeights" ? v : `${v}px`)
        : v;
    case "fontFamilies":
      return `"${v}", system-ui, sans-serif`;
    default:
      return v;
  }
}

// Convert flat.dotted.name to --css-var-name
function cssVarName(dottedName: string): string {
  return `--${dottedName.replace(/\./g, "-").replace(/_/g, "-").toLowerCase()}`;
}

// ── Load canonical tokens ───────────────────────────────────────────

function loadTokensStudio(): TokensStudioFile {
  if (!fs.existsSync(TOKENS_STUDIO_SOURCE)) {
    throw new Error(`Missing ${TOKENS_STUDIO_SOURCE}. Run with --generate-defaults first.`);
  }
  return JSON.parse(fs.readFileSync(TOKENS_STUDIO_SOURCE, "utf8"));
}

function loadFigmaTokensJson(): Record<string, unknown> {
  if (!fs.existsSync(TOKENS_SOURCE)) return {};
  return JSON.parse(fs.readFileSync(TOKENS_SOURCE, "utf8"));
}

// ── Output generators ───────────────────────────────────────────────

function generateCss(studio: TokensStudioFile): string {
  const global = flatten(studio.global);
  const light = flatten(studio.light);
  const dark = flatten(studio.dark);

  const header = `/* Auto-generated design tokens — DO NOT EDIT MANUALLY.
 * Source of truth: docs/figma-tokens-studio.json
 * Pipeline:       scripts/extract-design-tokens.ts
 * Runtime:        frontend/src/app/globals.css (hand-authored; this file is a backup)
 * Generated:      ${new Date().toISOString()}
 *
 * The runtime app loads globals.css, not this file. This file exists so the
 * token pipeline round-trips through Figma cleanly.
 */
`;

  const globalBlock = Object.entries(global)
    .map(([k, v]) => `  ${cssVarName(k)}: ${formatValue(v)};`)
    .join("\n");

  const lightBlock = Object.entries(light)
    .map(([k, v]) => `  ${cssVarName(k)}: ${formatValue(v)};`)
    .join("\n");

  const darkBlock = Object.entries(dark)
    .map(([k, v]) => `  ${cssVarName(k)}: ${formatValue(v)};`)
    .join("\n");

  return `${header}
:root {
${globalBlock}

${lightBlock}
}

.dark {
${darkBlock}
}
`;
}

function generateTailwindTokens(studio: TokensStudioFile): string {
  // Map tokens to Tailwind theme.extend shape using CSS vars (runtime-themeable)
  const all = { ...flatten(studio.global), ...flatten(studio.light) };

  const colors: Record<string, string> = {};
  const fontSize: Record<string, string> = {};
  const spacing: Record<string, string> = {};
  const borderRadius: Record<string, string> = {};
  const transitionDuration: Record<string, string> = {};
  const transitionTimingFunction: Record<string, string> = {};
  const boxShadow: Record<string, string> = {};
  const lineHeight: Record<string, string> = {};

  for (const [k, v] of Object.entries(all)) {
    const varName = cssVarName(k);
    switch (v.type) {
      case "color":
        colors[k.replace(/\./g, "-")] = `var(${varName})`;
        break;
      case "fontSizes": {
        const label = k.replace(/^typography-fontsize-/i, "");
        fontSize[label] = `var(${varName})`;
        break;
      }
      case "spacing": {
        const label = k.replace(/^spacing-/, "");
        spacing[label] = `var(${varName})`;
        break;
      }
      case "borderRadius": {
        const label = k.replace(/^borderradius-/i, "");
        borderRadius[label] = `var(${varName})`;
        break;
      }
      case "lineHeights": {
        const label = k.replace(/^typography-lineheight-/i, "");
        lineHeight[label] = `var(${varName})`;
        break;
      }
      case "boxShadow": {
        const label = k.replace(/^elevation-/, "elevation-").replace(/^effects-shadow-/, "");
        boxShadow[label] = `var(${varName})`;
        break;
      }
      case "other": {
        if (k.includes("motion-duration")) {
          transitionDuration[k.replace(/^motion-duration-/, "")] = `var(${varName})`;
        } else if (k.includes("motion-easing")) {
          transitionTimingFunction[k.replace(/^motion-easing-/, "")] = `var(${varName})`;
        }
        break;
      }
    }
  }

  return `// Auto-generated Tailwind token extension
// Source: docs/figma-tokens-studio.json
// Generated: ${new Date().toISOString()}
// NOTE: frontend/tailwind.config.ts is the live config. This file is a Figma-sync artifact.

module.exports = {
  theme: {
    extend: {
      colors: ${JSON.stringify(colors, null, 8)},
      fontSize: ${JSON.stringify(fontSize, null, 8)},
      spacing: ${JSON.stringify(spacing, null, 8)},
      borderRadius: ${JSON.stringify(borderRadius, null, 8)},
      transitionDuration: ${JSON.stringify(transitionDuration, null, 8)},
      transitionTimingFunction: ${JSON.stringify(transitionTimingFunction, null, 8)},
      boxShadow: ${JSON.stringify(boxShadow, null, 8)},
      lineHeight: ${JSON.stringify(lineHeight, null, 8)},
    },
  },
};
`;
}

function generateThemeTs(studio: TokensStudioFile): string {
  return `// Auto-generated TypeScript theme object
// Source: docs/figma-tokens-studio.json
// Generated: ${new Date().toISOString()}
// ⚠️  UNUSED by runtime — kept only as a Figma-sync artifact. Runtime source of truth: globals.css.

export const theme = {
  global: ${JSON.stringify(studio.global, null, 2)},
  light: ${JSON.stringify(studio.light, null, 2)},
  dark: ${JSON.stringify(studio.dark, null, 2)},
} as const;

export type ThemeMode = "light" | "dark";
`;
}

// ── Figma REST Variables payload (for --push mode) ──────────────────

function generateFigmaVariablesPayload(studio: TokensStudioFile): unknown {
  /* Figma REST Variables API expects:
   *   variableCollections: [{ action, id?, name, initialModeId? }]
   *   variableModes:       [{ action, id?, name, variableCollectionId }]
   *   variables:           [{ action, id?, name, variableCollectionId, resolvedType, codeSyntax, scopes }]
   *   variableModeValues:  [{ variableId, modeId, value }]
   *
   * We build a single collection "OpenClaw/Session39" with 2 modes (light, dark).
   * Each flattened token becomes a variable with a value per mode.
   */
  const COLLECTION_TEMP_ID = "col_openclaw_s39";
  const MODE_LIGHT_TEMP = "mode_light";
  const MODE_DARK_TEMP = "mode_dark";

  const global = flatten(studio.global);
  const light = flatten(studio.light);
  const dark = flatten(studio.dark);

  const variables: unknown[] = [];
  const variableModeValues: unknown[] = [];

  for (const [name, token] of Object.entries(global)) {
    const tempId = `var_${name.replace(/[^a-z0-9]/gi, "_")}`;
    const resolvedType = token.type === "color" ? "COLOR"
      : token.type === "fontSizes" || token.type === "spacing" || token.type === "borderRadius" ? "FLOAT"
      : "STRING";
    variables.push({
      action: "CREATE",
      id: tempId,
      name: name.replace(/-/g, "/"),
      variableCollectionId: COLLECTION_TEMP_ID,
      resolvedType,
      codeSyntax: { WEB: `var(${cssVarName(name)})` },
      scopes: resolvedType === "COLOR" ? ["ALL_FILLS", "STROKE_COLOR"] : ["ALL_SCOPES"],
    });
    // Global tokens apply to both modes
    const resolvedValue = token.type === "color" ? hexToRgba(token.value) : parseFloat(token.value) || token.value;
    variableModeValues.push({ variableId: tempId, modeId: MODE_LIGHT_TEMP, value: resolvedValue });
    variableModeValues.push({ variableId: tempId, modeId: MODE_DARK_TEMP, value: resolvedValue });
  }

  // Mode-specific overrides (light/dark)
  const applyModeSpecific = (modeTokens: Record<string, TokenValue>, modeId: string) => {
    for (const [name, token] of Object.entries(modeTokens)) {
      const tempId = `var_${name.replace(/[^a-z0-9]/gi, "_")}`;
      const exists = variables.some((v) => (v as { id: string }).id === tempId);
      if (!exists) {
        const resolvedType = token.type === "color" ? "COLOR" : "STRING";
        variables.push({
          action: "CREATE",
          id: tempId,
          name: name.replace(/-/g, "/"),
          variableCollectionId: COLLECTION_TEMP_ID,
          resolvedType,
          codeSyntax: { WEB: `var(${cssVarName(name)})` },
        });
      }
      const resolvedValue = token.type === "color" ? hexToRgba(token.value) : token.value;
      variableModeValues.push({ variableId: tempId, modeId, value: resolvedValue });
    }
  };
  applyModeSpecific(light, MODE_LIGHT_TEMP);
  applyModeSpecific(dark, MODE_DARK_TEMP);

  return {
    variableCollections: [
      { action: "CREATE", id: COLLECTION_TEMP_ID, name: "OpenClaw / Session 39", initialModeId: MODE_LIGHT_TEMP },
    ],
    variableModes: [
      { action: "CREATE", id: MODE_LIGHT_TEMP, name: "Light", variableCollectionId: COLLECTION_TEMP_ID },
      { action: "CREATE", id: MODE_DARK_TEMP, name: "Dark", variableCollectionId: COLLECTION_TEMP_ID },
    ],
    variables,
    variableModeValues,
  };
}

function hexToRgba(input: string): { r: number; g: number; b: number; a: number } {
  // Parse #rrggbb or rgba(r,g,b,a) → { r, g, b, a } in [0,1]
  const m = input.match(/^#([0-9a-f]{6})$/i);
  if (m) {
    const n = parseInt(m[1], 16);
    return { r: ((n >> 16) & 0xff) / 255, g: ((n >> 8) & 0xff) / 255, b: (n & 0xff) / 255, a: 1 };
  }
  const rgba = input.match(/rgba?\(([^)]+)\)/);
  if (rgba) {
    const [r, g, b, a] = rgba[1].split(",").map((s) => parseFloat(s.trim()));
    return { r: r / 255, g: g / 255, b: b / 255, a: a ?? 1 };
  }
  return { r: 0, g: 0, b: 0, a: 1 };
}

// ── Pull from Figma ─────────────────────────────────────────────────

async function pullFromFigma() {
  if (!TOKEN || !FILE_KEY) {
    console.error("❌ --pull requires FIGMA_ACCESS_TOKEN and FIGMA_FILE_KEY.");
    process.exit(1);
  }
  console.log("📡 Pulling variables from Figma...");
  const client = new FigmaClient(TOKEN);
  const user = await client.testConnection();
  console.log(`✓ Connected as ${user.handle}`);
  const { variables, variableCollections } = await client.getVariables(FILE_KEY);
  console.log(`✓ Got ${Object.keys(variables).length} variables in ${Object.keys(variableCollections).length} collections`);

  // Convert Figma variables to Tokens Studio format and merge over existing
  // (Implementation depth left for when a live Figma file exists.)
  const merged = loadTokensStudio();
  console.log("⚠ Pull merge not yet implemented. Saving raw Figma response to docs/figma-pulled.json for inspection.");
  fs.writeFileSync(path.resolve(__dirname, "../../docs/figma-pulled.json"), JSON.stringify({ variables, variableCollections }, null, 2));
  return merged;
}

// ── Push to Figma ───────────────────────────────────────────────────

async function pushToFigma(payload: unknown) {
  if (!TOKEN || !FILE_KEY) {
    console.error("❌ --push requires FIGMA_ACCESS_TOKEN and FIGMA_FILE_KEY.");
    process.exit(1);
  }
  console.log("📤 Pushing tokens to Figma...");
  const client = new FigmaClient(TOKEN);
  const user = await client.testConnection();
  console.log(`✓ Connected as ${user.handle}`);
  const result = await client.postVariables(FILE_KEY, payload as Parameters<typeof client.postVariables>[1]);
  console.log(`✓ Push complete. Mapped ${Object.keys(result.tempIdToRealId).length} temp IDs to real Figma IDs.`);
  fs.writeFileSync(path.resolve(__dirname, "../../docs/figma-push-result.json"), JSON.stringify(result, null, 2));
}

// ── Main ─────────────────────────────────────────────────────────────

async function main() {
  console.log("🎨 OpenClaw Design Token Pipeline (Session 39)");
  console.log("================================================\n");
  console.log(`Mode: ${MODE}`);
  console.log(`Source: ${TOKENS_STUDIO_SOURCE}`);
  console.log(`Output: ${OUTPUT_DIR}\n`);

  if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  let studio: TokensStudioFile;

  if (MODE === "pull") {
    studio = await pullFromFigma();
  } else {
    studio = loadTokensStudio();
  }

  const tokenCounts = {
    global: Object.keys(flatten(studio.global)).length,
    light: Object.keys(flatten(studio.light)).length,
    dark: Object.keys(flatten(studio.dark)).length,
  };
  const total = tokenCounts.global + tokenCounts.light + tokenCounts.dark;
  console.log(`📊 Token count: global=${tokenCounts.global}, light=${tokenCounts.light}, dark=${tokenCounts.dark} (total ${total})\n`);

  // Generate outputs
  const cssContent = generateCss(studio);
  const tailwindContent = generateTailwindTokens(studio);
  const themeContent = generateThemeTs(studio);
  const figmaPayload = generateFigmaVariablesPayload(studio);

  if (MODE === "dry-run") {
    console.log("🔍 Dry run — sizes only:");
    console.log(`   tokens.css:            ${cssContent.length.toLocaleString()} bytes`);
    console.log(`   tailwind.tokens.js:    ${tailwindContent.length.toLocaleString()} bytes`);
    console.log(`   theme.ts:              ${themeContent.length.toLocaleString()} bytes`);
    console.log(`   figma-variables JSON:  ${JSON.stringify(figmaPayload).length.toLocaleString()} bytes`);
    console.log(`   variables in payload:  ${(figmaPayload as { variables: unknown[] }).variables.length}`);
    return;
  }

  fs.writeFileSync(path.join(OUTPUT_DIR, "tokens.css"), cssContent);
  fs.writeFileSync(path.join(OUTPUT_DIR, "tailwind.tokens.js"), tailwindContent);
  fs.writeFileSync(path.join(OUTPUT_DIR, "theme.ts"), themeContent);
  fs.writeFileSync(FIGMA_VARIABLES_OUT, JSON.stringify(figmaPayload, null, 2));

  console.log("✅ Generated files:");
  console.log(`   ${path.join(OUTPUT_DIR, "tokens.css")}           (${cssContent.length.toLocaleString()}B)`);
  console.log(`   ${path.join(OUTPUT_DIR, "tailwind.tokens.js")}   (${tailwindContent.length.toLocaleString()}B)`);
  console.log(`   ${path.join(OUTPUT_DIR, "theme.ts")}             (${themeContent.length.toLocaleString()}B)`);
  console.log(`   ${FIGMA_VARIABLES_OUT}   (${JSON.stringify(figmaPayload).length.toLocaleString()}B — REST payload)\n`);

  if (MODE === "push") {
    await pushToFigma(figmaPayload);
  } else {
    console.log(`💡 To push to Figma: FIGMA_ACCESS_TOKEN=xxx FIGMA_FILE_KEY=xxx npx tsx ${path.basename(__filename)} --push`);
  }

  console.log(`\n🎨 Done — ${total} tokens across 3 sets`);
}

main().catch((e) => { console.error(e); process.exit(1); });
