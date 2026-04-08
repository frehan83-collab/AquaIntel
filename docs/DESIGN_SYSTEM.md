# OpenClaw Design System Specification
## Figma File: https://www.figma.com/design/UklcflWFBHal5xPSrSQolq/OpenClaw-Design-System

> **Vision:** Bloomberg Terminal meets Norwegian fjord.
> **Principles:** Data density. Scandinavian restraint. Every color carries meaning.

---

## 1. Color System (34 tokens, light + dark modes)

### Core UI Colors
| Token | Light Mode | Dark Mode | Usage |
|-------|-----------|-----------|-------|
| `bg/primary` | #F8FAFB | #060F1C | Page background |
| `bg/secondary` | #EFF3F6 | #0A1A2F | Section background |
| `accent` | #00A89F | #00D4C8 | Primary interactive (cyan) |
| `text/primary` | #1A2332 | #E8EDF2 | Main content text |
| `text/secondary` | #5A6B7D | #8899AA | Labels, descriptions |
| `border` | #D1D5DB | #1E293B | Dividers, input borders |
| `danger` | #F43F5E | #F43F5E | Destructive, errors |
| `success` | #10B981 | #10B981 | Positive actions |
| `warning` | #F59E0B | #F59E0B | Caution states |
| `salmon` | #E8734A | #E8734A | Brand accent (Norwegian salmon) |

### Aquaculture Data Colors (semantic — each metric has its own color)
| Token | Hex | Usage |
|-------|-----|-------|
| `data/biomass` | #F59E0B | Fish weight, growth curves |
| `data/lice` | #F43F5E | Lice counts, lice charts |
| `data/temperature` | #3B82F6 | Sea temperature, SST |
| `data/mortality` | #9F1239 | Mortality rate, death events |
| `data/feeding` | #059669 | Feed data, FCR |
| `data/oxygen` | #06B6D4 | O2 saturation levels |

### Trafikklyssystemet (Traffic Light — Norwegian regulation)
| Token | Hex | Usage |
|-------|-----|-------|
| `traffic/green` | #22C55E | PA status: growth allowed (+6% MTB) |
| `traffic/yellow` | #EAB308 | PA status: freeze (0% MTB) |
| `traffic/red` | #EF4444 | PA status: reduction (-6% MTB) |

### Signal Colors
| Token | Hex | Usage |
|-------|-----|-------|
| `positive` | #34D399 | Good trends, within limits |
| `negative` | #FB7185 | Bad trends, threshold breaches |

### Chart Palette (8 colors, accessible, distinct)
| # | Hex | Name |
|---|-----|------|
| 1 | #00D4C8 | Cyan (primary) |
| 2 | #E8734A | Salmon (brand) |
| 3 | #8B5CF6 | Violet |
| 4 | #F59E0B | Amber |
| 5 | #EC4899 | Pink |
| 6 | #10B981 | Emerald |
| 7 | #6366F1 | Indigo |
| 8 | #14B8A6 | Teal |

### Elevation Surfaces (dark mode depth hierarchy)
| Level | Light | Dark | Usage |
|-------|-------|------|-------|
| Surface 0 | #F8FAFB | #060F1C | Page background |
| Surface 1 | #FFFFFF | #0A1629 | Card background |
| Surface 2 | #F1F5F9 | #0F1D33 | Elevated card |
| Surface 3 | #E2E8F0 | #152640 | Modal, dropdown |
| Surface 4 | #CBD5E1 | #1A2F4D | Tooltip, popover |

---

## 2. Typography

| Scale | Size | Line Height | Weight | Usage |
|-------|------|-------------|--------|-------|
| xs | 0.75rem (12px) | 1rem | 400 | Data tables, fine print |
| sm | 0.875rem (14px) | 1.25rem | 400-500 | Labels, secondary |
| base | 1rem (16px) | 1.5rem | 400 | Body text |
| lg | 1.125rem (18px) | 1.75rem | 500 | Subheadings |
| xl | 1.25rem (20px) | 1.75rem | 600 | Section titles |
| 2xl | 1.5rem (24px) | 2rem | 700 | Page titles |
| 3xl | 1.875rem (30px) | 2.25rem | 700 | Dashboard KPI hero |
| 4xl | 2.25rem (36px) | 2.5rem | 700 | KPI spotlight |

### Font Families
- **Sans:** DM Sans (body, labels, UI)
- **Display:** DM Serif Display (page titles, hero text)
- **Mono:** JetBrains Mono (numbers, data, code) — `font-variant-numeric: tabular-nums`

### Key Rule
> ALL numbers in the UI use JetBrains Mono with tabular-nums for column alignment.

---

## 3. Spacing Scale (4px base grid)

| Token | Value | Usage |
|-------|-------|-------|
| space-1 | 4px | Tight gaps (icon to label) |
| space-2 | 8px | Default gap between elements |
| space-3 | 12px | Dense card padding |
| space-4 | 16px | Standard card padding |
| space-5 | 20px | Comfortable spacing |
| space-6 | 24px | Section gaps |
| space-8 | 32px | Large section gaps |
| space-10 | 40px | Page section dividers |

---

## 4. Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| radius-sm | 6px | Buttons, inputs |
| radius-md | 8px | Small cards, badges |
| radius-lg | 12px | Medium cards |
| radius-xl | 16px | Main cards (GlassCard primary) |
| radius-2xl | 20px | Large hero cards |
| radius-full | 9999px | Pills, circular badges |

---

## 5. Component Library

### KPICard
- **Variants:** default, hero (2x size)
- **States:** loading (skeleton), populated, error
- **Props:** label, value (with count-up animation), delta, deltaType, sparkline, icon, unit
- **Visual:** Left accent bar color-coded by deltaType, JetBrains Mono for numbers, DM Sans for labels
- **Sizes:** Compact (p-4, text-[22px] value) / Hero (p-6, text-[36px] value)

### GlassCard
- **Variants:** primary (prominent), secondary (recedes), flush (no padding)
- **Accents:** ocean, emerald, amber, rose, violet, salmon, none
- **Visual:** Glassmorphic background with gradient, left accent bar, bathymetric contour overlay
- **Dark mode:** `bg-gradient-to-br from-fjord-surface/60 to-fjord-midwater/40`
- **Hover:** border-salmon tint, shadow lift, -translate-y-0.5

### StatusBadge
- **Variants:** critical (rose), high (orange), warning (amber), normal (slate), good (emerald), info (blue)
- **Props:** status, label, pulse (optional animated dot), size (sm/md)

### TrafikklysIndicator
- **Visual:** Vertical stack of 3 lights (green/yellow/red), active light glows
- **Props:** color, pa (production area number), showImpact, size (sm/md/lg)

### DataTable
- **Features:** Sort, search, pagination (10/25/50/100), CSV/Excel export
- **Typography:** 11px compact / 12px normal, JetBrains Mono for numeric columns
- **Interactive:** Hover rows, sort arrows, focus states

### InteractiveChart
- **Features:** Crosshair hover, tooltips, area gradient, high/low markers
- **Colors:** Uses chart palette (--chart-1 through --chart-8)
- **Dark mode:** Subtle grid lines at rgba(255,255,255,0.05)

### Sidebar
- **Width:** 240px (desktop), overlay on mobile
- **Features:** Search (Cmd+K), section groups, active state highlight, collapse toggle
- **Mobile:** Hamburger menu, backdrop blur overlay, slide-in animation

---

## 6. Figma File Structure

```
OpenClaw Design System (UklcflWFBHal5xPSrSQolq)
├── Page 1: Color System
│   ├── Frame: Core UI Colors (light + dark swatches)
│   ├── Frame: Data Colors (6 aquaculture metrics)
│   ├── Frame: Traffic Light (3 regulatory colors)
│   ├── Frame: Chart Palette (8 accessible colors)
│   └── Frame: Elevation Surfaces (5 levels)
├── Page 2: Typography
│   ├── Frame: Type Scale (xs through 4xl)
│   ├── Frame: Font Families (Sans, Display, Mono)
│   └── Frame: Number Display (tabular-nums examples)
├── Page 3: Components
│   ├── Frame: KPICard (default + hero, all deltaTypes)
│   ├── Frame: GlassCard (3 tiers, 7 accents)
│   ├── Frame: StatusBadge (6 variants × 2 sizes)
│   ├── Frame: TrafikklysIndicator (3 colors × 3 sizes)
│   ├── Frame: DataTable (header + rows + pagination)
│   └── Frame: Button (8 variants × 3 sizes)
├── Page 4: Dashboard Layout
│   ├── Frame: Desktop 1440px (reference screenshot)
│   ├── Frame: Tablet 768px
│   └── Frame: Mobile 375px
└── Page 5: Page Templates
    ├── Frame: Data-Heavy Page (farmer-daily, disease)
    ├── Frame: Chart-Heavy Page (market, futures)
    └── Frame: Form Page (settings, billing)
```

---

## 7. Tokens Studio Import Format

To import these tokens into Figma via the [Tokens Studio plugin](https://www.figma.com/community/plugin/843461159747178978/tokens-studio-for-figma), use this JSON:

Save as `tokens.json` and import in Tokens Studio:

```json
{
  "OpenClaw": {
    "bg": {
      "primary": { "value": "{bg.primary}", "type": "color" },
      "secondary": { "value": "{bg.secondary}", "type": "color" }
    },
    "accent": { "value": "#00D4C8", "type": "color" },
    "text": {
      "primary": { "value": "{text.primary}", "type": "color" },
      "secondary": { "value": "{text.secondary}", "type": "color" }
    },
    "data": {
      "biomass": { "value": "#F59E0B", "type": "color" },
      "lice": { "value": "#F43F5E", "type": "color" },
      "temperature": { "value": "#3B82F6", "type": "color" },
      "mortality": { "value": "#9F1239", "type": "color" },
      "feeding": { "value": "#059669", "type": "color" },
      "oxygen": { "value": "#06B6D4", "type": "color" }
    },
    "traffic": {
      "green": { "value": "#22C55E", "type": "color" },
      "yellow": { "value": "#EAB308", "type": "color" },
      "red": { "value": "#EF4444", "type": "color" }
    }
  }
}
```

---

## 8. Implementation Status

| Component | Code | Figma | Synced |
|-----------|------|-------|--------|
| Color tokens | ✅ globals.css + tailwind.config | ⬜ Pending | ⬜ |
| Typography | ✅ Font imports + scale | ⬜ Pending | ⬜ |
| KPICard | ✅ With count-up animation | ⬜ Pending | ⬜ |
| GlassCard | ✅ 3 tiers, 7 accents | ⬜ Pending | ⬜ |
| StatusBadge | ✅ 6 variants | ⬜ Pending | ⬜ |
| TrafikklysIndicator | ✅ 3 sizes | ⬜ Pending | ⬜ |
| DataTable | ✅ Sort/search/export | ⬜ Pending | ⬜ |
| Sidebar | ✅ Mobile + desktop | ⬜ Pending | ⬜ |
| SkeletonCard | ✅ Loading state | ⬜ Pending | ⬜ |
| SegmentError | ✅ Error boundary | ⬜ Pending | ⬜ |
| FigmaClient | ✅ API integration | N/A | N/A |
| Token Pipeline | ✅ 101 tokens generated | ⬜ Pending import | ⬜ |
