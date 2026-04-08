// ═══════════════════════════════════════════════════════════════
// OpenClaw Design System — Figma Plugin Script
// Generated: 2026-04-08 19:02 UTC
// Tokens: 34 colors, 8 font sizes
// 
// HOW TO USE:
// 1. Open your Figma file
// 2. Plugins > Development > Open Console
// 3. Paste this entire script and press Enter
// ═══════════════════════════════════════════════════════════════

async function buildDesignSystem() {
  await figma.loadFontAsync({ family: 'Inter', style: 'Regular' });
  await figma.loadFontAsync({ family: 'Inter', style: 'Bold' });
  await figma.loadFontAsync({ family: 'Inter', style: 'Medium' });

  const PAGE_W = 1440;
  let currentY = 0;

  function createSectionHeader(text, y) {
    const label = figma.createText();
    label.characters = text;
    label.fontSize = 24;
    label.fontName = { family: 'Inter', style: 'Bold' };
    label.fills = [{ type: 'SOLID', color: { r: 0.91, g: 0.93, b: 0.95 } }];
    label.x = 40;
    label.y = y;
    return label;
  }

  function createColorSwatch(hex, name, desc, x, y, w, h) {
    const frame = figma.createFrame();
    frame.resize(w, h);
    frame.x = x;
    frame.y = y;
    frame.cornerRadius = 12;
    const c = hexToRgb(hex);
    frame.fills = [{ type: 'SOLID', color: c }];

    const label = figma.createText();
    label.characters = name;
    label.fontSize = 11;
    label.fontName = { family: 'Inter', style: 'Medium' };
    // Use contrasting text color
    const brightness = c.r * 0.299 + c.g * 0.587 + c.b * 0.114;
    label.fills = [{ type: 'SOLID', color: brightness > 0.5 ? {r:0.1,g:0.1,b:0.1} : {r:0.9,g:0.9,b:0.9} }];
    label.x = 8;
    label.y = 8;
    frame.appendChild(label);

    const hexLabel = figma.createText();
    hexLabel.characters = hex;
    hexLabel.fontSize = 10;
    hexLabel.fontName = { family: 'Inter', style: 'Regular' };
    hexLabel.fills = [{ type: 'SOLID', color: brightness > 0.5 ? {r:0.3,g:0.3,b:0.3} : {r:0.7,g:0.7,b:0.7} }];
    hexLabel.x = 8;
    hexLabel.y = h - 24;
    frame.appendChild(hexLabel);

    if (desc) {
      const descLabel = figma.createText();
      descLabel.characters = desc;
      descLabel.fontSize = 9;
      descLabel.fontName = { family: 'Inter', style: 'Regular' };
      descLabel.fills = [{ type: 'SOLID', color: brightness > 0.5 ? {r:0.4,g:0.4,b:0.4} : {r:0.6,g:0.6,b:0.6} }];
      descLabel.x = 8;
      descLabel.y = h - 38;
      frame.appendChild(descLabel);
    }

    return frame;
  }

  function hexToRgb(hex) {
    const h = hex.replace('#', '');
    return {
      r: parseInt(h.substring(0,2), 16) / 255,
      g: parseInt(h.substring(2,4), 16) / 255,
      b: parseInt(h.substring(4,6), 16) / 255
    };
  }

  // ── Page: Color System ─────────────────────────────────────
  const colorPage = figma.createPage();
  colorPage.name = '1. Color System';

  // Dark background frame
  const darkBg = figma.createFrame();
  darkBg.name = 'Color System — Dark Mode';
  darkBg.resize(PAGE_W, 2400);
  darkBg.fills = [{ type: 'SOLID', color: hexToRgb('#060F1C') }];
  colorPage.appendChild(darkBg);

  // --- Bg Colors ---
  darkBg.appendChild(createSectionHeader('Bg Colors', 40));
  darkBg.appendChild(createColorSwatch('#060F1C', 'bg.primary', 'Page background (dark)', 40, 80, 200, 90));
  darkBg.appendChild(createColorSwatch('#0A1A2F', 'bg.secondary', 'Section background (dark)', 260, 80, 200, 90));
  // --- Core Colors ---
  darkBg.appendChild(createSectionHeader('Core Colors', 220));
  darkBg.appendChild(createColorSwatch('#00D4C8', 'accent', 'Primary interactive cyan', 40, 260, 200, 90));
  darkBg.appendChild(createColorSwatch('#1E293B', 'border', 'Dividers (dark)', 260, 260, 200, 90));
  darkBg.appendChild(createColorSwatch('#F43F5E', 'danger', 'Errors, destructive', 480, 260, 200, 90));
  darkBg.appendChild(createColorSwatch('#10B981', 'success', 'Positive actions', 700, 260, 200, 90));
  darkBg.appendChild(createColorSwatch('#F59E0B', 'warning', 'Caution states', 920, 260, 200, 90));
  darkBg.appendChild(createColorSwatch('#E8734A', 'salmon', 'Brand accent (Norwegian salmon)', 1140, 260, 200, 90));
  darkBg.appendChild(createColorSwatch('#34D399', 'positive', 'Good trends', 40, 370, 200, 90));
  darkBg.appendChild(createColorSwatch('#FB7185', 'negative', 'Bad trends', 260, 370, 200, 90));
  // --- Text Colors ---
  darkBg.appendChild(createSectionHeader('Text Colors', 510));
  darkBg.appendChild(createColorSwatch('#E8EDF2', 'text.primary', 'Main content text (dark)', 40, 550, 200, 90));
  darkBg.appendChild(createColorSwatch('#8899AA', 'text.secondary', 'Labels, descriptions (dark)', 260, 550, 200, 90));
  // --- Data Colors ---
  darkBg.appendChild(createSectionHeader('Data Colors', 690));
  darkBg.appendChild(createColorSwatch('#F59E0B', 'data.biomass', 'Fish weight/growth', 40, 730, 200, 90));
  darkBg.appendChild(createColorSwatch('#F43F5E', 'data.lice', 'Lice counts', 260, 730, 200, 90));
  darkBg.appendChild(createColorSwatch('#3B82F6', 'data.temperature', 'Sea temperature', 480, 730, 200, 90));
  darkBg.appendChild(createColorSwatch('#9F1239', 'data.mortality', 'Death rate', 700, 730, 200, 90));
  darkBg.appendChild(createColorSwatch('#059669', 'data.feeding', 'Feed data', 920, 730, 200, 90));
  darkBg.appendChild(createColorSwatch('#06B6D4', 'data.oxygen', 'O2 levels', 1140, 730, 200, 90));
  // --- Traffic Colors ---
  darkBg.appendChild(createSectionHeader('Traffic Colors', 870));
  darkBg.appendChild(createColorSwatch('#22C55E', 'traffic.green', 'Traffic light green (+6% MTB)', 40, 910, 200, 90));
  darkBg.appendChild(createColorSwatch('#EAB308', 'traffic.yellow', 'Traffic light yellow (0% MTB)', 260, 910, 200, 90));
  darkBg.appendChild(createColorSwatch('#EF4444', 'traffic.red', 'Traffic light red (-6% MTB)', 480, 910, 200, 90));
  // --- Chart Colors ---
  darkBg.appendChild(createSectionHeader('Chart Colors', 1050));
  darkBg.appendChild(createColorSwatch('#00D4C8', 'chart.1', 'Chart: Cyan', 40, 1090, 200, 90));
  darkBg.appendChild(createColorSwatch('#E8734A', 'chart.2', 'Chart: Salmon', 260, 1090, 200, 90));
  darkBg.appendChild(createColorSwatch('#8B5CF6', 'chart.3', 'Chart: Violet', 480, 1090, 200, 90));
  darkBg.appendChild(createColorSwatch('#F59E0B', 'chart.4', 'Chart: Amber', 700, 1090, 200, 90));
  darkBg.appendChild(createColorSwatch('#EC4899', 'chart.5', 'Chart: Pink', 920, 1090, 200, 90));
  darkBg.appendChild(createColorSwatch('#10B981', 'chart.6', 'Chart: Emerald', 1140, 1090, 200, 90));
  darkBg.appendChild(createColorSwatch('#6366F1', 'chart.7', 'Chart: Indigo', 40, 1200, 200, 90));
  darkBg.appendChild(createColorSwatch('#14B8A6', 'chart.8', 'Chart: Teal', 260, 1200, 200, 90));
  // --- Surface Colors ---
  darkBg.appendChild(createSectionHeader('Surface Colors', 1340));
  darkBg.appendChild(createColorSwatch('#060F1C', 'surface.0', 'Page level', 40, 1380, 200, 90));
  darkBg.appendChild(createColorSwatch('#0A1629', 'surface.1', 'Card level', 260, 1380, 200, 90));
  darkBg.appendChild(createColorSwatch('#0F1D33', 'surface.2', 'Elevated card', 480, 1380, 200, 90));
  darkBg.appendChild(createColorSwatch('#152640', 'surface.3', 'Modal/dropdown', 700, 1380, 200, 90));
  darkBg.appendChild(createColorSwatch('#1A2F4D', 'surface.4', 'Tooltip/popover', 920, 1380, 200, 90));

  // ── Page: Typography ────────────────────────────────────────
  const typoPage = figma.createPage();
  typoPage.name = '2. Typography';

  const typoBg = figma.createFrame();
  typoBg.name = 'Typography Scale';
  typoBg.resize(PAGE_W, 1200);
  typoBg.fills = [{ type: 'SOLID', color: hexToRgb('#060F1C') }];
  typoPage.appendChild(typoBg);

  typoBg.appendChild(createSectionHeader('Typography Scale', 40));

  const typo_4xl = figma.createText();
  typo_4xl.characters = '4xl — 36px / 2.25rem';
  typo_4xl.fontSize = 36;
  typo_4xl.fontName = { family: 'Inter', style: 'Regular' };
  typo_4xl.fills = [{ type: 'SOLID', color: { r: 0.91, g: 0.93, b: 0.95 } }];
  typo_4xl.x = 40;
  typo_4xl.y = 100;
  typoBg.appendChild(typo_4xl);

  const typo_3xl = figma.createText();
  typo_3xl.characters = '3xl — 30px / 1.875rem';
  typo_3xl.fontSize = 30;
  typo_3xl.fontName = { family: 'Inter', style: 'Regular' };
  typo_3xl.fills = [{ type: 'SOLID', color: { r: 0.91, g: 0.93, b: 0.95 } }];
  typo_3xl.x = 40;
  typo_3xl.y = 160;
  typoBg.appendChild(typo_3xl);

  const typo_2xl = figma.createText();
  typo_2xl.characters = '2xl — 24px / 1.5rem';
  typo_2xl.fontSize = 24;
  typo_2xl.fontName = { family: 'Inter', style: 'Regular' };
  typo_2xl.fills = [{ type: 'SOLID', color: { r: 0.91, g: 0.93, b: 0.95 } }];
  typo_2xl.x = 40;
  typo_2xl.y = 214;
  typoBg.appendChild(typo_2xl);

  const typo_xl = figma.createText();
  typo_xl.characters = 'xl — 20px / 1.25rem';
  typo_xl.fontSize = 20;
  typo_xl.fontName = { family: 'Inter', style: 'Regular' };
  typo_xl.fills = [{ type: 'SOLID', color: { r: 0.91, g: 0.93, b: 0.95 } }];
  typo_xl.x = 40;
  typo_xl.y = 262;
  typoBg.appendChild(typo_xl);

  const typo_lg = figma.createText();
  typo_lg.characters = 'lg — 18px / 1.125rem';
  typo_lg.fontSize = 18;
  typo_lg.fontName = { family: 'Inter', style: 'Regular' };
  typo_lg.fills = [{ type: 'SOLID', color: { r: 0.91, g: 0.93, b: 0.95 } }];
  typo_lg.x = 40;
  typo_lg.y = 306;
  typoBg.appendChild(typo_lg);

  const typo_base = figma.createText();
  typo_base.characters = 'base — 16px / 1.0rem';
  typo_base.fontSize = 16;
  typo_base.fontName = { family: 'Inter', style: 'Regular' };
  typo_base.fills = [{ type: 'SOLID', color: { r: 0.91, g: 0.93, b: 0.95 } }];
  typo_base.x = 40;
  typo_base.y = 348;
  typoBg.appendChild(typo_base);

  const typo_sm = figma.createText();
  typo_sm.characters = 'sm — 14px / 0.875rem';
  typo_sm.fontSize = 14;
  typo_sm.fontName = { family: 'Inter', style: 'Regular' };
  typo_sm.fills = [{ type: 'SOLID', color: { r: 0.91, g: 0.93, b: 0.95 } }];
  typo_sm.x = 40;
  typo_sm.y = 388;
  typoBg.appendChild(typo_sm);

  const typo_xs = figma.createText();
  typo_xs.characters = 'xs — 12px / 0.75rem';
  typo_xs.fontSize = 12;
  typo_xs.fontName = { family: 'Inter', style: 'Regular' };
  typo_xs.fills = [{ type: 'SOLID', color: { r: 0.91, g: 0.93, b: 0.95 } }];
  typo_xs.x = 40;
  typo_xs.y = 426;
  typoBg.appendChild(typo_xs);

  // ── Page: Spacing & Radius ──────────────────────────────────
  const spacingPage = figma.createPage();
  spacingPage.name = '3. Spacing & Radius';

  const spaceBg = figma.createFrame();
  spaceBg.name = 'Spacing Scale';
  spaceBg.resize(PAGE_W, 800);
  spaceBg.fills = [{ type: 'SOLID', color: hexToRgb('#060F1C') }];
  spacingPage.appendChild(spaceBg);

  spaceBg.appendChild(createSectionHeader('Spacing Scale (4px base grid)', 40));

  const sp_1 = figma.createFrame();
  sp_1.resize(4, 24);
  sp_1.x = 40;
  sp_1.y = 100;
  sp_1.fills = [{ type: 'SOLID', color: hexToRgb('#00D4C8') }];
  sp_1.opacity = 0.3;
  sp_1.cornerRadius = 4;
  spaceBg.appendChild(sp_1);

  const spLabel_1 = figma.createText();
  spLabel_1.characters = 'space-1: 4px';
  spLabel_1.fontSize = 11;
  spLabel_1.fontName = { family: 'Inter', style: 'Regular' };
  spLabel_1.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  spLabel_1.x = 100;
  spLabel_1.y = 104;
  spaceBg.appendChild(spLabel_1);

  const sp_2 = figma.createFrame();
  sp_2.resize(8, 24);
  sp_2.x = 40;
  sp_2.y = 140;
  sp_2.fills = [{ type: 'SOLID', color: hexToRgb('#00D4C8') }];
  sp_2.opacity = 0.3;
  sp_2.cornerRadius = 4;
  spaceBg.appendChild(sp_2);

  const spLabel_2 = figma.createText();
  spLabel_2.characters = 'space-2: 8px';
  spLabel_2.fontSize = 11;
  spLabel_2.fontName = { family: 'Inter', style: 'Regular' };
  spLabel_2.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  spLabel_2.x = 100;
  spLabel_2.y = 144;
  spaceBg.appendChild(spLabel_2);

  const sp_3 = figma.createFrame();
  sp_3.resize(12, 24);
  sp_3.x = 40;
  sp_3.y = 180;
  sp_3.fills = [{ type: 'SOLID', color: hexToRgb('#00D4C8') }];
  sp_3.opacity = 0.3;
  sp_3.cornerRadius = 4;
  spaceBg.appendChild(sp_3);

  const spLabel_3 = figma.createText();
  spLabel_3.characters = 'space-3: 12px';
  spLabel_3.fontSize = 11;
  spLabel_3.fontName = { family: 'Inter', style: 'Regular' };
  spLabel_3.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  spLabel_3.x = 100;
  spLabel_3.y = 184;
  spaceBg.appendChild(spLabel_3);

  const sp_4 = figma.createFrame();
  sp_4.resize(16, 24);
  sp_4.x = 40;
  sp_4.y = 220;
  sp_4.fills = [{ type: 'SOLID', color: hexToRgb('#00D4C8') }];
  sp_4.opacity = 0.3;
  sp_4.cornerRadius = 4;
  spaceBg.appendChild(sp_4);

  const spLabel_4 = figma.createText();
  spLabel_4.characters = 'space-4: 16px';
  spLabel_4.fontSize = 11;
  spLabel_4.fontName = { family: 'Inter', style: 'Regular' };
  spLabel_4.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  spLabel_4.x = 100;
  spLabel_4.y = 224;
  spaceBg.appendChild(spLabel_4);

  const sp_5 = figma.createFrame();
  sp_5.resize(20, 24);
  sp_5.x = 40;
  sp_5.y = 260;
  sp_5.fills = [{ type: 'SOLID', color: hexToRgb('#00D4C8') }];
  sp_5.opacity = 0.3;
  sp_5.cornerRadius = 4;
  spaceBg.appendChild(sp_5);

  const spLabel_5 = figma.createText();
  spLabel_5.characters = 'space-5: 20px';
  spLabel_5.fontSize = 11;
  spLabel_5.fontName = { family: 'Inter', style: 'Regular' };
  spLabel_5.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  spLabel_5.x = 100;
  spLabel_5.y = 264;
  spaceBg.appendChild(spLabel_5);

  const sp_6 = figma.createFrame();
  sp_6.resize(24, 24);
  sp_6.x = 40;
  sp_6.y = 300;
  sp_6.fills = [{ type: 'SOLID', color: hexToRgb('#00D4C8') }];
  sp_6.opacity = 0.3;
  sp_6.cornerRadius = 4;
  spaceBg.appendChild(sp_6);

  const spLabel_6 = figma.createText();
  spLabel_6.characters = 'space-6: 24px';
  spLabel_6.fontSize = 11;
  spLabel_6.fontName = { family: 'Inter', style: 'Regular' };
  spLabel_6.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  spLabel_6.x = 100;
  spLabel_6.y = 304;
  spaceBg.appendChild(spLabel_6);

  const sp_8 = figma.createFrame();
  sp_8.resize(32, 24);
  sp_8.x = 40;
  sp_8.y = 340;
  sp_8.fills = [{ type: 'SOLID', color: hexToRgb('#00D4C8') }];
  sp_8.opacity = 0.3;
  sp_8.cornerRadius = 4;
  spaceBg.appendChild(sp_8);

  const spLabel_8 = figma.createText();
  spLabel_8.characters = 'space-8: 32px';
  spLabel_8.fontSize = 11;
  spLabel_8.fontName = { family: 'Inter', style: 'Regular' };
  spLabel_8.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  spLabel_8.x = 100;
  spLabel_8.y = 344;
  spaceBg.appendChild(spLabel_8);

  const sp_10 = figma.createFrame();
  sp_10.resize(40, 24);
  sp_10.x = 40;
  sp_10.y = 380;
  sp_10.fills = [{ type: 'SOLID', color: hexToRgb('#00D4C8') }];
  sp_10.opacity = 0.3;
  sp_10.cornerRadius = 4;
  spaceBg.appendChild(sp_10);

  const spLabel_10 = figma.createText();
  spLabel_10.characters = 'space-10: 40px';
  spLabel_10.fontSize = 11;
  spLabel_10.fontName = { family: 'Inter', style: 'Regular' };
  spLabel_10.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  spLabel_10.x = 100;
  spLabel_10.y = 384;
  spaceBg.appendChild(spLabel_10);

  const sp_12 = figma.createFrame();
  sp_12.resize(48, 24);
  sp_12.x = 40;
  sp_12.y = 420;
  sp_12.fills = [{ type: 'SOLID', color: hexToRgb('#00D4C8') }];
  sp_12.opacity = 0.3;
  sp_12.cornerRadius = 4;
  spaceBg.appendChild(sp_12);

  const spLabel_12 = figma.createText();
  spLabel_12.characters = 'space-12: 48px';
  spLabel_12.fontSize = 11;
  spLabel_12.fontName = { family: 'Inter', style: 'Regular' };
  spLabel_12.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  spLabel_12.x = 100;
  spLabel_12.y = 424;
  spaceBg.appendChild(spLabel_12);

  const sp_16 = figma.createFrame();
  sp_16.resize(64, 24);
  sp_16.x = 40;
  sp_16.y = 460;
  sp_16.fills = [{ type: 'SOLID', color: hexToRgb('#00D4C8') }];
  sp_16.opacity = 0.3;
  sp_16.cornerRadius = 4;
  spaceBg.appendChild(sp_16);

  const spLabel_16 = figma.createText();
  spLabel_16.characters = 'space-16: 64px';
  spLabel_16.fontSize = 11;
  spLabel_16.fontName = { family: 'Inter', style: 'Regular' };
  spLabel_16.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  spLabel_16.x = 100;
  spLabel_16.y = 464;
  spaceBg.appendChild(spLabel_16);

  const sp_20 = figma.createFrame();
  sp_20.resize(80, 24);
  sp_20.x = 40;
  sp_20.y = 500;
  sp_20.fills = [{ type: 'SOLID', color: hexToRgb('#00D4C8') }];
  sp_20.opacity = 0.3;
  sp_20.cornerRadius = 4;
  spaceBg.appendChild(sp_20);

  const spLabel_20 = figma.createText();
  spLabel_20.characters = 'space-20: 80px';
  spLabel_20.fontSize = 11;
  spLabel_20.fontName = { family: 'Inter', style: 'Regular' };
  spLabel_20.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  spLabel_20.x = 100;
  spLabel_20.y = 504;
  spaceBg.appendChild(spLabel_20);

  // ── Page: Components ─────────────────────────────────────────
  const compPage = figma.createPage();
  compPage.name = '4. Components';

  const compBg = figma.createFrame();
  compBg.name = 'Component Library';
  compBg.resize(PAGE_W, 3000);
  compBg.fills = [{ type: 'SOLID', color: hexToRgb('#060F1C') }];
  compPage.appendChild(compBg);

  compBg.appendChild(createSectionHeader('KPICard', 40));
  const desc_KPICard = figma.createText();
  desc_KPICard.characters = 'Metric display with count-up animation, sparkline, delta indicator';
  desc_KPICard.fontSize = 12;
  desc_KPICard.fontName = { family: 'Inter', style: 'Regular' };
  desc_KPICard.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  desc_KPICard.x = 40;
  desc_KPICard.y = 72;
  compBg.appendChild(desc_KPICard);

  // Placeholder frame for KPICard component variants
  const frame_KPICard = figma.createFrame();
  frame_KPICard.name = 'KPICard Variants';
  frame_KPICard.resize(1360, 200);
  frame_KPICard.x = 40;
  frame_KPICard.y = 96;
  frame_KPICard.fills = [{ type: 'SOLID', color: hexToRgb('#0A1629') }];
  frame_KPICard.cornerRadius = 16;
  frame_KPICard.strokeWeight = 1;
  frame_KPICard.strokes = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 }, opacity: 0.06 }];
  compBg.appendChild(frame_KPICard);

  compBg.appendChild(createSectionHeader('GlassCard', 340));
  const desc_GlassCard = figma.createText();
  desc_GlassCard.characters = 'Glassmorphic container with 3 tiers and 7 accent colors';
  desc_GlassCard.fontSize = 12;
  desc_GlassCard.fontName = { family: 'Inter', style: 'Regular' };
  desc_GlassCard.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  desc_GlassCard.x = 40;
  desc_GlassCard.y = 372;
  compBg.appendChild(desc_GlassCard);

  // Placeholder frame for GlassCard component variants
  const frame_GlassCard = figma.createFrame();
  frame_GlassCard.name = 'GlassCard Variants';
  frame_GlassCard.resize(1360, 200);
  frame_GlassCard.x = 40;
  frame_GlassCard.y = 396;
  frame_GlassCard.fills = [{ type: 'SOLID', color: hexToRgb('#0A1629') }];
  frame_GlassCard.cornerRadius = 16;
  frame_GlassCard.strokeWeight = 1;
  frame_GlassCard.strokes = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 }, opacity: 0.06 }];
  compBg.appendChild(frame_GlassCard);

  compBg.appendChild(createSectionHeader('StatusBadge', 640));
  const desc_StatusBadge = figma.createText();
  desc_StatusBadge.characters = '6 severity variants (critical/high/warning/normal/good/info)';
  desc_StatusBadge.fontSize = 12;
  desc_StatusBadge.fontName = { family: 'Inter', style: 'Regular' };
  desc_StatusBadge.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  desc_StatusBadge.x = 40;
  desc_StatusBadge.y = 672;
  compBg.appendChild(desc_StatusBadge);

  // Placeholder frame for StatusBadge component variants
  const frame_StatusBadge = figma.createFrame();
  frame_StatusBadge.name = 'StatusBadge Variants';
  frame_StatusBadge.resize(1360, 200);
  frame_StatusBadge.x = 40;
  frame_StatusBadge.y = 696;
  frame_StatusBadge.fills = [{ type: 'SOLID', color: hexToRgb('#0A1629') }];
  frame_StatusBadge.cornerRadius = 16;
  frame_StatusBadge.strokeWeight = 1;
  frame_StatusBadge.strokes = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 }, opacity: 0.06 }];
  compBg.appendChild(frame_StatusBadge);

  compBg.appendChild(createSectionHeader('TrafikklysIndicator', 940));
  const desc_TrafikklysIndicator = figma.createText();
  desc_TrafikklysIndicator.characters = 'Norwegian traffic light system (3 colors x 3 sizes)';
  desc_TrafikklysIndicator.fontSize = 12;
  desc_TrafikklysIndicator.fontName = { family: 'Inter', style: 'Regular' };
  desc_TrafikklysIndicator.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  desc_TrafikklysIndicator.x = 40;
  desc_TrafikklysIndicator.y = 972;
  compBg.appendChild(desc_TrafikklysIndicator);

  // Placeholder frame for TrafikklysIndicator component variants
  const frame_TrafikklysIndicator = figma.createFrame();
  frame_TrafikklysIndicator.name = 'TrafikklysIndicator Variants';
  frame_TrafikklysIndicator.resize(1360, 200);
  frame_TrafikklysIndicator.x = 40;
  frame_TrafikklysIndicator.y = 996;
  frame_TrafikklysIndicator.fills = [{ type: 'SOLID', color: hexToRgb('#0A1629') }];
  frame_TrafikklysIndicator.cornerRadius = 16;
  frame_TrafikklysIndicator.strokeWeight = 1;
  frame_TrafikklysIndicator.strokes = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 }, opacity: 0.06 }];
  compBg.appendChild(frame_TrafikklysIndicator);

  compBg.appendChild(createSectionHeader('DataTable', 1240));
  const desc_DataTable = figma.createText();
  desc_DataTable.characters = 'Sortable, searchable table with CSV/Excel export';
  desc_DataTable.fontSize = 12;
  desc_DataTable.fontName = { family: 'Inter', style: 'Regular' };
  desc_DataTable.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  desc_DataTable.x = 40;
  desc_DataTable.y = 1272;
  compBg.appendChild(desc_DataTable);

  // Placeholder frame for DataTable component variants
  const frame_DataTable = figma.createFrame();
  frame_DataTable.name = 'DataTable Variants';
  frame_DataTable.resize(1360, 200);
  frame_DataTable.x = 40;
  frame_DataTable.y = 1296;
  frame_DataTable.fills = [{ type: 'SOLID', color: hexToRgb('#0A1629') }];
  frame_DataTable.cornerRadius = 16;
  frame_DataTable.strokeWeight = 1;
  frame_DataTable.strokes = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 }, opacity: 0.06 }];
  compBg.appendChild(frame_DataTable);

  compBg.appendChild(createSectionHeader('InteractiveChart', 1540));
  const desc_InteractiveChart = figma.createText();
  desc_InteractiveChart.characters = 'Crosshair hover chart with confidence bands';
  desc_InteractiveChart.fontSize = 12;
  desc_InteractiveChart.fontName = { family: 'Inter', style: 'Regular' };
  desc_InteractiveChart.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  desc_InteractiveChart.x = 40;
  desc_InteractiveChart.y = 1572;
  compBg.appendChild(desc_InteractiveChart);

  // Placeholder frame for InteractiveChart component variants
  const frame_InteractiveChart = figma.createFrame();
  frame_InteractiveChart.name = 'InteractiveChart Variants';
  frame_InteractiveChart.resize(1360, 200);
  frame_InteractiveChart.x = 40;
  frame_InteractiveChart.y = 1596;
  frame_InteractiveChart.fills = [{ type: 'SOLID', color: hexToRgb('#0A1629') }];
  frame_InteractiveChart.cornerRadius = 16;
  frame_InteractiveChart.strokeWeight = 1;
  frame_InteractiveChart.strokes = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 }, opacity: 0.06 }];
  compBg.appendChild(frame_InteractiveChart);

  compBg.appendChild(createSectionHeader('Sidebar', 1840));
  const desc_Sidebar = figma.createText();
  desc_Sidebar.characters = '240px desktop nav with search, mobile hamburger overlay';
  desc_Sidebar.fontSize = 12;
  desc_Sidebar.fontName = { family: 'Inter', style: 'Regular' };
  desc_Sidebar.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  desc_Sidebar.x = 40;
  desc_Sidebar.y = 1872;
  compBg.appendChild(desc_Sidebar);

  // Placeholder frame for Sidebar component variants
  const frame_Sidebar = figma.createFrame();
  frame_Sidebar.name = 'Sidebar Variants';
  frame_Sidebar.resize(1360, 200);
  frame_Sidebar.x = 40;
  frame_Sidebar.y = 1896;
  frame_Sidebar.fills = [{ type: 'SOLID', color: hexToRgb('#0A1629') }];
  frame_Sidebar.cornerRadius = 16;
  frame_Sidebar.strokeWeight = 1;
  frame_Sidebar.strokes = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 }, opacity: 0.06 }];
  compBg.appendChild(frame_Sidebar);

  compBg.appendChild(createSectionHeader('Button', 2140));
  const desc_Button = figma.createText();
  desc_Button.characters = 'OcButton with 8 variants (primary/secondary/ghost/danger/etc)';
  desc_Button.fontSize = 12;
  desc_Button.fontName = { family: 'Inter', style: 'Regular' };
  desc_Button.fills = [{ type: 'SOLID', color: { r: 0.53, g: 0.6, b: 0.67 } }];
  desc_Button.x = 40;
  desc_Button.y = 2172;
  compBg.appendChild(desc_Button);

  // Placeholder frame for Button component variants
  const frame_Button = figma.createFrame();
  frame_Button.name = 'Button Variants';
  frame_Button.resize(1360, 200);
  frame_Button.x = 40;
  frame_Button.y = 2196;
  frame_Button.fills = [{ type: 'SOLID', color: hexToRgb('#0A1629') }];
  frame_Button.cornerRadius = 16;
  frame_Button.strokeWeight = 1;
  frame_Button.strokes = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 }, opacity: 0.06 }];
  compBg.appendChild(frame_Button);

  // ── Page: Dashboard Layout ───────────────────────────────────
  const layoutPage = figma.createPage();
  layoutPage.name = '5. Dashboard Layout';

  // Desktop frame
  const desktop = figma.createFrame();
  desktop.name = 'Desktop 1440px';
  desktop.resize(1440, 900);
  desktop.fills = [{ type: 'SOLID', color: hexToRgb('#060F1C') }];
  layoutPage.appendChild(desktop);

  // Sidebar placeholder
  const sidebar = figma.createFrame();
  sidebar.name = 'Sidebar 240px';
  sidebar.resize(240, 900);
  sidebar.fills = [{ type: 'SOLID', color: hexToRgb('#0A1629') }];
  sidebar.strokeWeight = 1;
  sidebar.strokes = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 }, opacity: 0.06 }];
  desktop.appendChild(sidebar);

  // Main content area
  const main = figma.createFrame();
  main.name = 'Main Content';
  main.resize(1200, 900);
  main.x = 240;
  main.fills = [{ type: 'SOLID', color: hexToRgb('#060F1C') }];
  desktop.appendChild(main);

  // Mobile frame
  const mobile = figma.createFrame();
  mobile.name = 'Mobile 375px';
  mobile.resize(375, 812);
  mobile.x = 1500;
  mobile.fills = [{ type: 'SOLID', color: hexToRgb('#060F1C') }];
  layoutPage.appendChild(mobile);

  // Tablet frame
  const tablet = figma.createFrame();
  tablet.name = 'Tablet 768px';
  tablet.resize(768, 1024);
  tablet.x = 1940;
  tablet.fills = [{ type: 'SOLID', color: hexToRgb('#060F1C') }];
  layoutPage.appendChild(tablet);

  // Clean up — remove the default page if empty
  if (figma.root.children.length > 5) {
    const defaultPage = figma.root.children[0];
    if (defaultPage.children.length === 0) {
      defaultPage.remove();
    }
  }

  figma.viewport.scrollAndZoomIntoView([darkBg]);
  figma.notify('OpenClaw Design System built: 34 colors, 8 font sizes, 11 spacing tokens, 8 components');
}

buildDesignSystem();