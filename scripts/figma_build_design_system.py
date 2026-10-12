"""
Figma Design System Builder — Populates the OpenClaw Design System Figma file
with color swatches, typography samples, component specs, and layout references.

This script uses the Figma REST API (via FigmaClient) to create visual
documentation frames in the design system file.

Prerequisites:
    - FIGMA_ACCESS_TOKEN env var set
    - Figma file created (UklcflWFBHal5xPSrSQolq)

Usage:
    python scripts/figma_build_design_system.py
    python scripts/figma_build_design_system.py --file-key YOUR_FILE_KEY
    python scripts/figma_build_design_system.py --dry-run   # Preview without API calls

Note: Figma REST API can only read files, export images, and post comments.
Creating visual elements requires the Figma Plugin API (runs inside the Figma app).
This script generates a Figma plugin script that can be pasted into the Figma
developer console to build out the design system visuals.
"""

import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).parent.parent
TOKENS_FILE = PROJECT_ROOT / "docs" / "figma-tokens.json"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "generated"

# ── Light mode overrides ───────────────────────────────────────────────
LIGHT_OVERRIDES = {
    "bg.primary": "#F8FAFB",
    "bg.secondary": "#EFF3F6",
    "accent": "#00A89F",
    "text.primary": "#1A2332",
    "text.secondary": "#5A6B7D",
    "border": "#D1D5DB",
    "surface.0": "#F8FAFB",
    "surface.1": "#FFFFFF",
    "surface.2": "#F1F5F9",
    "surface.3": "#E2E8F0",
    "surface.4": "#CBD5E1",
}


def hex_to_rgb_float(hex_color: str) -> dict:
    """Convert hex to Figma RGB (0-1 float)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    return {"r": round(r, 4), "g": round(g, 4), "b": round(b, 4)}


def load_tokens() -> dict:
    with open(TOKENS_FILE, encoding="utf-8") as f:
        return json.load(f)


def flatten_colors(obj: dict, prefix: str = "") -> list[tuple[str, str, str]]:
    """Flatten to list of (path, hex_value, description)."""
    result = []
    for key, val in obj.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(val, dict) and "value" in val and val.get("type") == "color":
            result.append((path, val["value"], val.get("description", "")))
        elif isinstance(val, dict):
            result.extend(flatten_colors(val, path))
    return result


def generate_figma_plugin_script(tokens: dict) -> str:
    """Generate a Figma Plugin API script that builds the full design system."""
    colors = flatten_colors(tokens.get("global", {}).get("colors", {}))
    typo = tokens.get("global", {}).get("typography", {})
    spacing = tokens.get("global", {}).get("spacing", {})

    script_lines = [
        "// ═══════════════════════════════════════════════════════════════",
        "// OpenClaw Design System — Figma Plugin Script",
        f"// Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"// Tokens: {len(colors)} colors, {len(typo.get('fontSize', {}))} font sizes",
        "// ",
        "// HOW TO USE:",
        "// 1. Open your Figma file",
        "// 2. Plugins > Development > Open Console",
        "// 3. Paste this entire script and press Enter",
        "// ═══════════════════════════════════════════════════════════════",
        "",
        "async function buildDesignSystem() {",
        "  await figma.loadFontAsync({ family: 'Inter', style: 'Regular' });",
        "  await figma.loadFontAsync({ family: 'Inter', style: 'Bold' });",
        "  await figma.loadFontAsync({ family: 'Inter', style: 'Medium' });",
        "",
        "  const PAGE_W = 1440;",
        "  let currentY = 0;",
        "",
        "  function createSectionHeader(text, y) {",
        "    const label = figma.createText();",
        "    label.characters = text;",
        "    label.fontSize = 24;",
        "    label.fontName = { family: 'Inter', style: 'Bold' };",
        "    label.fills = [{ type: 'SOLID', color: { r: 0.91, g: 0.93, b: 0.95 } }];",
        "    label.x = 40;",
        "    label.y = y;",
        "    return label;",
        "  }",
        "",
        "  function createColorSwatch(hex, name, desc, x, y, w, h) {",
        "    const frame = figma.createFrame();",
        "    frame.resize(w, h);",
        "    frame.x = x;",
        "    frame.y = y;",
        "    frame.cornerRadius = 12;",
        "    const c = hexToRgb(hex);",
        "    frame.fills = [{ type: 'SOLID', color: c }];",
        "",
        "    const label = figma.createText();",
        "    label.characters = name;",
        "    label.fontSize = 11;",
        "    label.fontName = { family: 'Inter', style: 'Medium' };",
        "    // Use contrasting text color",
        "    const brightness = c.r * 0.299 + c.g * 0.587 + c.b * 0.114;",
        "    label.fills = [{ type: 'SOLID', color: brightness > 0.5 ? {r:0.1,g:0.1,b:0.1} : {r:0.9,g:0.9,b:0.9} }];",
        "    label.x = 8;",
        "    label.y = 8;",
        "    frame.appendChild(label);",
        "",
        "    const hexLabel = figma.createText();",
        "    hexLabel.characters = hex;",
        "    hexLabel.fontSize = 10;",
        "    hexLabel.fontName = { family: 'Inter', style: 'Regular' };",
        "    hexLabel.fills = [{ type: 'SOLID', color: brightness > 0.5 ? {r:0.3,g:0.3,b:0.3} : {r:0.7,g:0.7,b:0.7} }];",
        "    hexLabel.x = 8;",
        "    hexLabel.y = h - 24;",
        "    frame.appendChild(hexLabel);",
        "",
        "    if (desc) {",
        "      const descLabel = figma.createText();",
        "      descLabel.characters = desc;",
        "      descLabel.fontSize = 9;",
        "      descLabel.fontName = { family: 'Inter', style: 'Regular' };",
        "      descLabel.fills = [{ type: 'SOLID', color: brightness > 0.5 ? {r:0.4,g:0.4,b:0.4} : {r:0.6,g:0.6,b:0.6} }];",
        "      descLabel.x = 8;",
        "      descLabel.y = h - 38;",
        "      frame.appendChild(descLabel);",
        "    }",
        "",
        "    return frame;",
        "  }",
        "",
        "  function hexToRgb(hex) {",
        "    const h = hex.replace('#', '');",
        "    return {",
        "      r: parseInt(h.substring(0,2), 16) / 255,",
        "      g: parseInt(h.substring(2,4), 16) / 255,",
        "      b: parseInt(h.substring(4,6), 16) / 255",
        "    };",
        "  }",
        "",
        "  // ── Page: Color System ─────────────────────────────────────",
        "  const colorPage = figma.createPage();",
        "  colorPage.name = '1. Color System';",
        "",
        "  // Dark background frame",
        "  const darkBg = figma.createFrame();",
        "  darkBg.name = 'Color System — Dark Mode';",
        "  darkBg.resize(PAGE_W, 2400);",
        "  darkBg.fills = [{ type: 'SOLID', color: hexToRgb('#060F1C') }];",
        "  colorPage.appendChild(darkBg);",
        "",
    ]

    # Group colors by category
    categories = {}
    for path, hex_val, desc in colors:
        parts = path.split(".")
        cat = parts[0] if len(parts) > 1 else "core"
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((path, hex_val, desc))

    y_offset = 40
    for cat_name, cat_colors in categories.items():
        label = cat_name.replace("_", " ").title()
        script_lines.append(f"  // --- {label} Colors ---")
        script_lines.append(f"  darkBg.appendChild(createSectionHeader('{label} Colors', {y_offset}));")
        y_offset += 40

        for i, (path, hex_val, desc) in enumerate(cat_colors):
            col = i % 6
            row = i // 6
            x = 40 + col * 220
            y = y_offset + row * 110
            name = path.split(".")[-1] if "." in path else path
            safe_desc = desc.replace("'", "\\'")
            script_lines.append(
                f"  darkBg.appendChild(createColorSwatch('{hex_val}', '{path}', '{safe_desc}', {x}, {y}, 200, 90));"
            )

        rows = (len(cat_colors) + 5) // 6
        y_offset += rows * 110 + 30

    # Typography page
    script_lines.extend([
        "",
        "  // ── Page: Typography ────────────────────────────────────────",
        "  const typoPage = figma.createPage();",
        "  typoPage.name = '2. Typography';",
        "",
        "  const typoBg = figma.createFrame();",
        "  typoBg.name = 'Typography Scale';",
        "  typoBg.resize(PAGE_W, 1200);",
        "  typoBg.fills = [{ type: 'SOLID', color: hexToRgb('#060F1C') }];",
        "  typoPage.appendChild(typoBg);",
        "",
        "  typoBg.appendChild(createSectionHeader('Typography Scale', 40));",
        "",
    ])

    font_sizes = typo.get("fontSize", {})
    y = 100
    for name, info in sorted(font_sizes.items(), key=lambda x: int(x[1]["value"]), reverse=True):
        px = info["value"]
        script_lines.extend([
            f"  const typo_{name.replace('-', '_')} = figma.createText();",
            f"  typo_{name.replace('-', '_')}.characters = '{name} — {px}px / {round(int(px)/16, 3)}rem';",
            f"  typo_{name.replace('-', '_')}.fontSize = {px};",
            f"  typo_{name.replace('-', '_')}.fontName = {{ family: 'Inter', style: 'Regular' }};",
            f"  typo_{name.replace('-', '_')}.fills = [{{ type: 'SOLID', color: {{ r: 0.91, g: 0.93, b: 0.95 }} }}];",
            f"  typo_{name.replace('-', '_')}.x = 40;",
            f"  typo_{name.replace('-', '_')}.y = {y};",
            f"  typoBg.appendChild(typo_{name.replace('-', '_')});",
            "",
        ])
        y += int(px) + 24

    # Spacing page
    script_lines.extend([
        "  // ── Page: Spacing & Radius ──────────────────────────────────",
        "  const spacingPage = figma.createPage();",
        "  spacingPage.name = '3. Spacing & Radius';",
        "",
        "  const spaceBg = figma.createFrame();",
        "  spaceBg.name = 'Spacing Scale';",
        "  spaceBg.resize(PAGE_W, 800);",
        "  spaceBg.fills = [{ type: 'SOLID', color: hexToRgb('#060F1C') }];",
        "  spacingPage.appendChild(spaceBg);",
        "",
        "  spaceBg.appendChild(createSectionHeader('Spacing Scale (4px base grid)', 40));",
        "",
    ])

    y = 100
    for name, info in sorted(spacing.items(), key=lambda x: int(x[1]["value"])):
        px = int(info["value"])
        script_lines.extend([
            f"  const sp_{name} = figma.createFrame();",
            f"  sp_{name}.resize({px}, 24);",
            f"  sp_{name}.x = 40;",
            f"  sp_{name}.y = {y};",
            f"  sp_{name}.fills = [{{ type: 'SOLID', color: hexToRgb('#00D4C8') }}];",
            f"  sp_{name}.opacity = 0.3;",
            f"  sp_{name}.cornerRadius = 4;",
            f"  spaceBg.appendChild(sp_{name});",
            "",
            f"  const spLabel_{name} = figma.createText();",
            f"  spLabel_{name}.characters = 'space-{name}: {px}px';",
            f"  spLabel_{name}.fontSize = 11;",
            f"  spLabel_{name}.fontName = {{ family: 'Inter', style: 'Regular' }};",
            f"  spLabel_{name}.fills = [{{ type: 'SOLID', color: {{ r: 0.53, g: 0.6, b: 0.67 }} }}];",
            f"  spLabel_{name}.x = {max(px + 16, 100)};",
            f"  spLabel_{name}.y = {y + 4};",
            f"  spaceBg.appendChild(spLabel_{name});",
            "",
        ])
        y += 40

    # Component spec page (placeholder frames)
    script_lines.extend([
        "  // ── Page: Components ─────────────────────────────────────────",
        "  const compPage = figma.createPage();",
        "  compPage.name = '4. Components';",
        "",
        "  const compBg = figma.createFrame();",
        "  compBg.name = 'Component Library';",
        "  compBg.resize(PAGE_W, 3000);",
        "  compBg.fills = [{ type: 'SOLID', color: hexToRgb('#060F1C') }];",
        "  compPage.appendChild(compBg);",
        "",
    ])

    # Component placeholder frames
    components = [
        ("KPICard", "Metric display with count-up animation, sparkline, delta indicator"),
        ("GlassCard", "Glassmorphic container with 3 tiers and 7 accent colors"),
        ("StatusBadge", "6 severity variants (critical/high/warning/normal/good/info)"),
        ("TrafikklysIndicator", "Norwegian traffic light system (3 colors x 3 sizes)"),
        ("DataTable", "Sortable, searchable table with CSV/Excel export"),
        ("InteractiveChart", "Crosshair hover chart with confidence bands"),
        ("Sidebar", "240px desktop nav with search, mobile hamburger overlay"),
        ("Button", "OcButton with 8 variants (primary/secondary/ghost/danger/etc)"),
    ]

    comp_y = 40
    for comp_name, comp_desc in components:
        script_lines.extend([
            f"  compBg.appendChild(createSectionHeader('{comp_name}', {comp_y}));",
            f"  const desc_{comp_name} = figma.createText();",
            f"  desc_{comp_name}.characters = '{comp_desc}';",
            f"  desc_{comp_name}.fontSize = 12;",
            f"  desc_{comp_name}.fontName = {{ family: 'Inter', style: 'Regular' }};",
            f"  desc_{comp_name}.fills = [{{ type: 'SOLID', color: {{ r: 0.53, g: 0.6, b: 0.67 }} }}];",
            f"  desc_{comp_name}.x = 40;",
            f"  desc_{comp_name}.y = {comp_y + 32};",
            f"  compBg.appendChild(desc_{comp_name});",
            "",
            f"  // Placeholder frame for {comp_name} component variants",
            f"  const frame_{comp_name} = figma.createFrame();",
            f"  frame_{comp_name}.name = '{comp_name} Variants';",
            f"  frame_{comp_name}.resize(1360, 200);",
            f"  frame_{comp_name}.x = 40;",
            f"  frame_{comp_name}.y = {comp_y + 56};",
            f"  frame_{comp_name}.fills = [{{ type: 'SOLID', color: hexToRgb('#0A1629') }}];",
            f"  frame_{comp_name}.cornerRadius = 16;",
            f"  frame_{comp_name}.strokeWeight = 1;",
            f"  frame_{comp_name}.strokes = [{{ type: 'SOLID', color: {{ r: 1, g: 1, b: 1 }}, opacity: 0.06 }}];",
            f"  compBg.appendChild(frame_{comp_name});",
            "",
        ])
        comp_y += 300

    # Layout page
    script_lines.extend([
        "  // ── Page: Dashboard Layout ───────────────────────────────────",
        "  const layoutPage = figma.createPage();",
        "  layoutPage.name = '5. Dashboard Layout';",
        "",
        "  // Desktop frame",
        "  const desktop = figma.createFrame();",
        "  desktop.name = 'Desktop 1440px';",
        "  desktop.resize(1440, 900);",
        "  desktop.fills = [{ type: 'SOLID', color: hexToRgb('#060F1C') }];",
        "  layoutPage.appendChild(desktop);",
        "",
        "  // Sidebar placeholder",
        "  const sidebar = figma.createFrame();",
        "  sidebar.name = 'Sidebar 240px';",
        "  sidebar.resize(240, 900);",
        "  sidebar.fills = [{ type: 'SOLID', color: hexToRgb('#0A1629') }];",
        "  sidebar.strokeWeight = 1;",
        "  sidebar.strokes = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 }, opacity: 0.06 }];",
        "  desktop.appendChild(sidebar);",
        "",
        "  // Main content area",
        "  const main = figma.createFrame();",
        "  main.name = 'Main Content';",
        "  main.resize(1200, 900);",
        "  main.x = 240;",
        "  main.fills = [{ type: 'SOLID', color: hexToRgb('#060F1C') }];",
        "  desktop.appendChild(main);",
        "",
        "  // Mobile frame",
        "  const mobile = figma.createFrame();",
        "  mobile.name = 'Mobile 375px';",
        "  mobile.resize(375, 812);",
        "  mobile.x = 1500;",
        "  mobile.fills = [{ type: 'SOLID', color: hexToRgb('#060F1C') }];",
        "  layoutPage.appendChild(mobile);",
        "",
        "  // Tablet frame",
        "  const tablet = figma.createFrame();",
        "  tablet.name = 'Tablet 768px';",
        "  tablet.resize(768, 1024);",
        "  tablet.x = 1940;",
        "  tablet.fills = [{ type: 'SOLID', color: hexToRgb('#060F1C') }];",
        "  layoutPage.appendChild(tablet);",
        "",
        "  // Clean up — remove the default page if empty",
        "  if (figma.root.children.length > 5) {",
        "    const defaultPage = figma.root.children[0];",
        "    if (defaultPage.children.length === 0) {",
        "      defaultPage.remove();",
        "    }",
        "  }",
        "",
        "  figma.viewport.scrollAndZoomIntoView([darkBg]);",
        f"  figma.notify('OpenClaw Design System built: {len(colors)} colors, 8 font sizes, {len(spacing)} spacing tokens, 8 components');",
        "}",
        "",
        "buildDesignSystem();",
    ])

    return "\n".join(script_lines)


def main():
    parser = argparse.ArgumentParser(description="Build OpenClaw Design System in Figma")
    parser.add_argument("--file-key", default="UklcflWFBHal5xPSrSQolq", help="Figma file key")
    parser.add_argument("--dry-run", action="store_true", help="Generate script without API calls")
    args = parser.parse_args()

    tokens = load_tokens()
    colors = flatten_colors(tokens.get("global", {}).get("colors", {}))

    print(f"OpenClaw Design System Builder")
    print(f"  File: https://www.figma.com/design/{args.file_key}/")
    print(f"  Tokens: {len(colors)} colors")

    # Generate the Figma plugin script
    script = generate_figma_plugin_script(tokens)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "figma-plugin-script.js"
    output_file.write_text(script, encoding="utf-8")
    print(f"\n  Plugin script: {output_file}")
    print(f"  Lines: {len(script.splitlines())}")
    print()
    print("  To populate the Figma file:")
    print("  1. Open the Figma file in your browser")
    print("  2. Go to Plugins > Development > Open Console")
    print("  3. Paste the contents of figma-plugin-script.js")
    print("  4. Press Enter")
    print()
    print("  OR use Tokens Studio plugin:")
    print("  1. Install 'Tokens Studio for Figma' plugin")
    print("  2. Import docs/figma-tokens-studio.json")
    print("  3. Select 'dark' or 'light' theme")


if __name__ == "__main__":
    main()
