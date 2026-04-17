"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import GlassCard from "@/components/GlassCard";
import KPICard from "@/components/KPICard";
import StatusBadge from "@/components/StatusBadge";
import TrafikklysIndicator from "@/components/TrafikklysIndicator";
import { OcButton } from "@/components/ui/Button";
import ProgressRing from "@/components/ProgressRing";
import TickerStrip from "@/components/TickerStrip";
import { BentoGrid } from "@/components/BentoGrid";
import AnimatedGauge from "@/components/AnimatedGauge";
import MiniHeatmap from "@/components/MiniHeatmap";
import {
  colors,
  chartPalette,
  dataColors,
  trafficLight,
  spacing,
  borderRadius,
  typography,
  lightModeOverrides,
} from "@/lib/design-tokens";
import {
  Activity,
  Fish,
  Thermometer,
  TrendingUp,
  TrendingDown,
  Droplets,
  Heart,
  Download,
  Plus,
  Trash2,
  Check,
  Send,
  Zap,
} from "lucide-react";

export default function DesignSystemPage() {
  const [loadingBtn, setLoadingBtn] = useState(false);
  const [successBtn, setSuccessBtn] = useState(false);

  const handleLoadingDemo = () => {
    setLoadingBtn(true);
    setTimeout(() => {
      setLoadingBtn(false);
      setSuccessBtn(true);
      setTimeout(() => setSuccessBtn(false), 1500);
    }, 2000);
  };

  return (
    <div className="space-y-12 max-w-6xl">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-display text-[var(--text-primary)]">
          OpenClaw Design System
        </h1>
        <p className="text-[var(--text-secondary)] mt-2">
          Bloomberg Terminal meets Norwegian fjord. {Object.keys(colors).length} color groups,{" "}
          {chartPalette.length} chart colors, {Object.keys(spacing).length} spacing tokens.
        </p>
      </div>

      {/* ── Color System ────────────────────────────────────────── */}
      <section>
        <h2 className="section-header">Color Tokens</h2>

        {/* Core UI Colors */}
        <h3 className="text-sm font-semibold text-[var(--text-secondary)] mb-3 uppercase tracking-wider">
          Core UI
        </h3>
        <div className="grid grid-cols-3 sm:grid-cols-5 md:grid-cols-10 gap-3 mb-8">
          {[
            { name: "accent", hex: colors.accent },
            { name: "salmon", hex: colors.salmon },
            { name: "danger", hex: colors.danger },
            { name: "success", hex: colors.success },
            { name: "warning", hex: colors.warning },
            { name: "positive", hex: colors.positive },
            { name: "negative", hex: colors.negative },
            { name: "border", hex: colors.border },
            { name: "bg.primary", hex: colors.bg.primary },
            { name: "bg.secondary", hex: colors.bg.secondary },
          ].map(({ name, hex }) => (
            <div key={name} className="flex flex-col items-center gap-1">
              <div
                className="w-12 h-12 rounded-lg border border-white/10"
                style={{ backgroundColor: hex }}
              />
              <span className="text-[8px] font-mono text-[var(--text-secondary)]">{name}</span>
              <span className="text-[7px] font-mono text-[var(--text-secondary)] opacity-60">{hex}</span>
            </div>
          ))}
        </div>

        {/* Data Colors */}
        <h3 className="text-sm font-semibold text-[var(--text-secondary)] mb-3 uppercase tracking-wider">
          Aquaculture Data
        </h3>
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mb-8">
          {Object.entries(dataColors).map(([name, hex]) => (
            <div key={name} className="flex flex-col items-center gap-1">
              <div
                className="w-12 h-12 rounded-lg border border-white/10"
                style={{ backgroundColor: hex }}
              />
              <span className="text-[9px] font-mono text-[var(--text-secondary)]">{name}</span>
            </div>
          ))}
        </div>

        {/* Chart Palette */}
        <h3 className="text-sm font-semibold text-[var(--text-secondary)] mb-3 uppercase tracking-wider">
          Chart Palette ({chartPalette.length} colors)
        </h3>
        <div className="flex gap-2 mb-8">
          {chartPalette.map((hex, i) => (
            <div key={i} className="flex flex-col items-center gap-1">
              <div
                className="w-16 h-10 rounded-lg border border-white/10"
                style={{ backgroundColor: hex }}
              />
              <span className="text-[8px] font-mono text-[var(--text-secondary)]">chart-{i + 1}</span>
            </div>
          ))}
        </div>

        {/* Surface Elevation */}
        <h3 className="text-sm font-semibold text-[var(--text-secondary)] mb-3 uppercase tracking-wider">
          Surface Elevation
        </h3>
        <div className="flex gap-3 mb-8">
          {Object.entries(colors.surface).map(([level, hex]) => (
            <div key={level} className="flex flex-col items-center gap-1">
              <div
                className="w-20 h-14 rounded-xl border border-white/10"
                style={{ backgroundColor: hex }}
              />
              <span className="text-[9px] font-mono text-[var(--text-secondary)]">surface-{level}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ── Typography ──────────────────────────────────────────── */}
      <section>
        <h2 className="section-header">Typography</h2>
        <GlassCard accent="ocean" className="mb-6">
          <div className="space-y-4">
            <div className="flex items-baseline gap-4">
              <span className="text-[9px] font-mono text-[var(--text-secondary)] w-12">4xl</span>
              <span className="text-4xl font-bold text-[var(--text-primary)]">NOK 94.40</span>
            </div>
            <div className="flex items-baseline gap-4">
              <span className="text-[9px] font-mono text-[var(--text-secondary)] w-12">3xl</span>
              <span className="text-3xl font-bold text-[var(--text-primary)]">Dashboard KPI</span>
            </div>
            <div className="flex items-baseline gap-4">
              <span className="text-[9px] font-mono text-[var(--text-secondary)] w-12">2xl</span>
              <span className="text-2xl font-bold text-[var(--text-primary)]">Page Title</span>
            </div>
            <div className="flex items-baseline gap-4">
              <span className="text-[9px] font-mono text-[var(--text-secondary)] w-12">xl</span>
              <span className="text-xl font-semibold text-[var(--text-primary)]">Section Title</span>
            </div>
            <div className="flex items-baseline gap-4">
              <span className="text-[9px] font-mono text-[var(--text-secondary)] w-12">lg</span>
              <span className="text-lg font-medium text-[var(--text-primary)]">Subheading</span>
            </div>
            <div className="flex items-baseline gap-4">
              <span className="text-[9px] font-mono text-[var(--text-secondary)] w-12">base</span>
              <span className="text-base text-[var(--text-primary)]">Body text for content</span>
            </div>
            <div className="flex items-baseline gap-4">
              <span className="text-[9px] font-mono text-[var(--text-secondary)] w-12">sm</span>
              <span className="text-sm text-[var(--text-secondary)]">Labels and secondary</span>
            </div>
            <div className="flex items-baseline gap-4">
              <span className="text-[9px] font-mono text-[var(--text-secondary)] w-12">xs</span>
              <span className="text-xs text-[var(--text-secondary)]">Table data, fine print</span>
            </div>
          </div>
          <div className="mt-6 pt-4 border-t border-white/[0.06] grid grid-cols-3 gap-4">
            <div>
              <p className="text-[9px] text-[var(--text-secondary)] mb-1">Sans (DM Sans)</p>
              <p className="font-sans text-[var(--text-primary)]">Lice per fish: 0.23</p>
            </div>
            <div>
              <p className="text-[9px] text-[var(--text-secondary)] mb-1">Display (DM Serif)</p>
              <p className="font-display text-[var(--text-primary)]">Morning Brief</p>
            </div>
            <div>
              <p className="text-[9px] text-[var(--text-secondary)] mb-1">Mono (JetBrains)</p>
              <p className="font-data text-[var(--text-primary)]">1,234.50 NOK</p>
            </div>
          </div>
        </GlassCard>
      </section>

      {/* ── KPI Cards ───────────────────────────────────────────── */}
      <section>
        <h2 className="section-header">KPI Cards</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <KPICard
            label="SSB Spot"
            value={94.4}
            delta="+3.2%"
            deltaType="positive"
            icon={TrendingUp}
            unit="NOK/kg"
            sparkline={[88, 89, 91, 90, 92, 93, 94, 94.4]}
          />
          <KPICard
            label="Avg Lice"
            value={0.23}
            delta="-12%"
            deltaType="positive"
            icon={Activity}
            sparkline={[0.3, 0.28, 0.27, 0.25, 0.24, 0.23]}
          />
          <KPICard
            label="Mortality"
            value="1.8%"
            delta="+0.3%"
            deltaType="negative"
            icon={Heart}
            sparkline={[1.2, 1.3, 1.5, 1.6, 1.7, 1.8]}
          />
          <KPICard
            label="Feed Cost"
            value={42.1}
            delta="-"
            deltaType="neutral"
            icon={Fish}
            unit="NOK/kg"
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <KPICard
            label="National Biomass"
            value="886K"
            delta="+2.1%"
            deltaType="positive"
            icon={Droplets}
            unit="tonnes"
            hero
            sparkline={[840, 850, 860, 870, 880, 886]}
          />
          <KPICard
            label="Sea Temperature"
            value={8.4}
            delta="+1.2C"
            deltaType="negative"
            icon={Thermometer}
            unit="C"
            hero
            sparkline={[6.8, 7.2, 7.5, 7.9, 8.1, 8.4]}
          />
        </div>
      </section>

      {/* ── GlassCard ───────────────────────────────────────────── */}
      <section>
        <h2 className="section-header">GlassCard Variants</h2>
        <div className="grid grid-cols-3 gap-4 mb-6">
          {(["ocean", "salmon", "emerald", "amber", "rose", "violet"] as const).map((accent) => (
            <GlassCard key={accent} accent={accent}>
              <p className="text-sm font-semibold text-[var(--text-primary)] mb-1">
                accent=&quot;{accent}&quot;
              </p>
              <p className="text-xs text-[var(--text-secondary)]">
                Primary tier with left accent bar
              </p>
            </GlassCard>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-4">
          <GlassCard tier="secondary" accent="ocean">
            <p className="text-sm font-semibold text-[var(--text-primary)]">tier=&quot;secondary&quot;</p>
            <p className="text-xs text-[var(--text-secondary)]">Recessed visual hierarchy</p>
          </GlassCard>
          <GlassCard tier="flush" accent="none">
            <p className="text-sm font-semibold text-[var(--text-primary)]">tier=&quot;flush&quot;</p>
            <p className="text-xs text-[var(--text-secondary)]">No padding or border</p>
          </GlassCard>
        </div>
      </section>

      {/* ── Status Badges ───────────────────────────────────────── */}
      <section>
        <h2 className="section-header">Status Badges</h2>
        <GlassCard accent="ocean">
          <div className="flex flex-wrap gap-3 mb-4">
            {(["critical", "high", "warning", "normal", "good", "info"] as const).map((s) => (
              <StatusBadge key={s} status={s} label={s.charAt(0).toUpperCase() + s.slice(1)} size="md" />
            ))}
          </div>
          <div className="flex flex-wrap gap-3">
            {(["critical", "high", "warning", "normal", "good", "info"] as const).map((s) => (
              <StatusBadge key={`sm-${s}`} status={s} label={s} size="sm" pulse={s === "critical"} />
            ))}
          </div>
        </GlassCard>
      </section>

      {/* ── Traffic Light ───────────────────────────────────────── */}
      <section>
        <h2 className="section-header">Trafikklyssystemet</h2>
        <GlassCard accent="ocean">
          <div className="flex items-center gap-8">
            {(["green", "yellow", "red"] as const).map((c, ci) => (
              <div key={c} className="flex gap-6">
                <TrafikklysIndicator color={c} pa={ci * 4 + 1} showImpact size="sm" />
                <TrafikklysIndicator color={c} pa={ci * 4 + 2} showImpact size="md" />
                <TrafikklysIndicator color={c} pa={ci * 4 + 3} showImpact size="lg" />
              </div>
            ))}
          </div>
        </GlassCard>
      </section>

      {/* ── Buttons ─────────────────────────────────────────────── */}
      <section>
        <h2 className="section-header">OcButton Variants</h2>
        <GlassCard accent="ocean">
          <div className="flex flex-wrap gap-3 mb-4">
            <OcButton variant="primary" leftIcon={<Zap className="w-4 h-4" />}>Primary</OcButton>
            <OcButton variant="secondary">Secondary</OcButton>
            <OcButton variant="ghost">Ghost</OcButton>
            <OcButton variant="danger" leftIcon={<Trash2 className="w-4 h-4" />}>Danger</OcButton>
            <OcButton variant="success" leftIcon={<Check className="w-4 h-4" />}>Success</OcButton>
            <OcButton variant="accent">Accent</OcButton>
            <OcButton variant="salmon" leftIcon={<Fish className="w-4 h-4" />}>Salmon</OcButton>
          </div>
          <div className="flex flex-wrap gap-3 mb-4">
            <OcButton size="xs">Extra Small</OcButton>
            <OcButton size="sm">Small</OcButton>
            <OcButton size="md">Medium</OcButton>
            <OcButton size="lg">Large</OcButton>
            <OcButton size="xl">Extra Large</OcButton>
          </div>
          <div className="flex flex-wrap gap-3">
            <OcButton
              loading={loadingBtn}
              showSuccess={successBtn}
              loadingText="Processing..."
              onClick={handleLoadingDemo}
              leftIcon={<Send className="w-4 h-4" />}
            >
              Loading Demo
            </OcButton>
            <OcButton disabled>Disabled</OcButton>
            <OcButton variant="icon" size="icon_md"><Plus className="w-4 h-4" /></OcButton>
            <OcButton variant="icon" size="icon_sm"><Download className="w-3 h-3" /></OcButton>
          </div>
        </GlassCard>
      </section>

      {/* ── Spacing ─────────────────────────────────────────────── */}
      <section>
        <h2 className="section-header">Spacing Scale (4px base)</h2>
        <GlassCard accent="ocean">
          <div className="space-y-2">
            {Object.entries(spacing).map(([key, px]) => (
              <div key={key} className="flex items-center gap-4">
                <span className="text-[10px] font-mono text-[var(--text-secondary)] w-16">space-{key}</span>
                <div
                  className="h-5 rounded bg-ocean-500/30 border border-ocean-500/20"
                  style={{ width: px }}
                />
                <span className="text-[10px] font-mono text-[var(--text-secondary)]">{px}px</span>
              </div>
            ))}
          </div>
        </GlassCard>
      </section>

      {/* ── Border Radius ───────────────────────────────────────── */}
      <section>
        <h2 className="section-header">Border Radius</h2>
        <GlassCard accent="ocean">
          <div className="flex gap-4 items-end">
            {Object.entries(borderRadius).map(([key, val]) => (
              <div key={key} className="flex flex-col items-center gap-2">
                <div
                  className="w-16 h-16 bg-ocean-500/20 border border-ocean-500/30"
                  style={{ borderRadius: val }}
                />
                <span className="text-[9px] font-mono text-[var(--text-secondary)]">{key}</span>
                <span className="text-[8px] font-mono text-[var(--text-secondary)] opacity-60">{val}</span>
              </div>
            ))}
          </div>
        </GlassCard>
      </section>

      {/* ── New Components (Session 33) ─────────────────────────── */}
      <section>
        <h2 className="section-header">Progress Rings</h2>
        <GlassCard>
          <div className="flex flex-wrap items-center gap-8">
            <ProgressRing value={92} label="Welfare" sublabel="Grade A" />
            <ProgressRing value={67} label="ASC" sublabel="Partial" />
            <ProgressRing value={34} label="Risk" sublabel="High" />
            <ProgressRing value={100} label="Perfect" size={60} strokeWidth={4} />
            <ProgressRing value={0} label="Empty" size={60} strokeWidth={4} />
          </div>
        </GlassCard>
      </section>

      <section>
        <h2 className="section-header">Ticker Strip</h2>
        <TickerStrip
          items={[
            { label: "SSB Spot", value: "NOK 90.55", change: 2.3, trend: "up" },
            { label: "Avg Lice", value: "0.092", change: -5.1, trend: "down" },
            { label: "Feed Index", value: "112.4", change: 0.8, trend: "up" },
            { label: "NOK/USD", value: "10.42", change: -0.3, trend: "down" },
            { label: "Biomass", value: "886kt", change: 1.2, trend: "up" },
            { label: "ESG Avg", value: "72.1", trend: "flat" },
          ]}
        />
      </section>

      <section>
        <h2 className="section-header">Animated Gauges</h2>
        <GlassCard>
          <div className="flex flex-wrap items-center gap-8">
            <AnimatedGauge value={85} label="Welfare Index" unit="%" />
            <AnimatedGauge value={42} label="Anomaly Score" unit="pts" />
            <AnimatedGauge value={15} label="Critical Risk" unit="%" />
          </div>
        </GlassCard>
      </section>

      <section>
        <h2 className="section-header">Mini Heatmap</h2>
        <GlassCard>
          <div className="flex flex-wrap gap-8">
            <div>
              <p className="text-xs text-[var(--text-secondary)] mb-2">Lice by PA (4 weeks)</p>
              <MiniHeatmap
                data={[
                  [0.08, 0.12, 0.15, 0.09],
                  [0.22, 0.35, 0.41, 0.28],
                  [0.05, 0.07, 0.06, 0.04],
                  [0.18, 0.25, 0.30, 0.22],
                  [0.45, 0.52, 0.61, 0.55],
                ]}
                rowLabels={["PA 1", "PA 2", "PA 3", "PA 4", "PA 5"]}
                colLabels={["W10", "W11", "W12", "W13"]}
                colorScale="lice"
                showValues
              />
            </div>
            <div>
              <p className="text-xs text-[var(--text-secondary)] mb-2">Temperature (default)</p>
              <MiniHeatmap
                data={[
                  [6.2, 7.1, 8.0, 9.2],
                  [5.8, 6.5, 7.4, 8.6],
                  [4.1, 4.8, 5.9, 7.0],
                ]}
                rowLabels={["North", "Mid", "South"]}
                colLabels={["Jan", "Feb", "Mar", "Apr"]}
                colorScale="temperature"
              />
            </div>
          </div>
        </GlassCard>
      </section>

      <section>
        <h2 className="section-header">Bento Grid</h2>
        <BentoGrid columns={4} gap={16} items={[
          { id: "1", colSpan: 2, rowSpan: 1, children: <GlassCard accent="ocean"><p className="text-sm font-semibold">Wide Card (2 cols)</p><p className="text-xs text-[var(--text-secondary)]">Spans 2 columns in the bento layout</p></GlassCard> },
          { id: "2", colSpan: 1, rowSpan: 1, children: <GlassCard accent="salmon"><p className="text-sm font-semibold">Standard</p></GlassCard> },
          { id: "3", colSpan: 1, rowSpan: 1, children: <GlassCard accent="emerald"><p className="text-sm font-semibold">Standard</p></GlassCard> },
          { id: "4", colSpan: 1, rowSpan: 1, children: <GlassCard accent="violet"><p className="text-sm font-semibold">Compact</p></GlassCard> },
          { id: "5", colSpan: 3, rowSpan: 1, children: <GlassCard accent="amber"><p className="text-sm font-semibold">Extra Wide Card (3 cols)</p><p className="text-xs text-[var(--text-secondary)]">Spans 3 columns — great for charts or tables</p></GlassCard> },
        ]} />
      </section>

      {/* ── Motion Tokens (Session 39) ───────────────────────── */}
      <section>
        <h2 className="section-header">Motion Tokens (Session 39)</h2>
        <p className="text-xs text-[var(--text-secondary)] mb-3">
          4 durations &times; 4 easings. Wired to Tailwind <code className="font-mono">duration-{"{token}"}</code> +
          <code className="font-mono"> ease-{"{token}"}-token</code>. Consumed by framer-motion via CSS vars.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <GlassCard accent="violet">
            <p className="text-sm font-semibold mb-3">Durations</p>
            <div className="space-y-2">
              {[
                { name: "instant", ms: 60, desc: "Micro-feedback" },
                { name: "fast", ms: 120, desc: "Hover, focus" },
                { name: "base", ms: 200, desc: "Standard fade" },
                { name: "slow", ms: 320, desc: "Modal enter" },
                { name: "slower", ms: 480, desc: "Orchestration" },
              ].map((d) => (
                <div key={d.name} className="flex items-center gap-3 p-2 rounded bg-white/[0.03]">
                  <div className="w-20 text-xs font-mono">{d.name}</div>
                  <motion.div
                    className="h-1.5 bg-[var(--accent)] rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${d.ms * 0.3}px` }}
                    transition={{ duration: d.ms / 1000, repeat: Infinity, repeatType: "reverse" }}
                  />
                  <div className="ml-auto text-[10px] text-[var(--text-secondary)] font-mono">{d.ms}ms</div>
                </div>
              ))}
            </div>
          </GlassCard>
          <GlassCard accent="emerald">
            <p className="text-sm font-semibold mb-3">Easing Curves</p>
            <div className="space-y-2">
              {[
                { name: "out", curve: "cubic-bezier(0.16, 1, 0.3, 1)", desc: "Entrance" },
                { name: "in", curve: "cubic-bezier(0.4, 0, 1, 1)", desc: "Exit" },
                { name: "inOut", curve: "cubic-bezier(0.4, 0, 0.2, 1)", desc: "Symmetric" },
                { name: "bounce", curve: "cubic-bezier(0.34, 1.56, 0.64, 1)", desc: "Playful overshoot" },
              ].map((e) => (
                <div key={e.name} className="flex items-center gap-3 p-2 rounded bg-white/[0.03]">
                  <div className="w-16 text-xs font-mono">{e.name}</div>
                  <div className="flex-1 text-[10px] text-[var(--text-secondary)] font-mono truncate">{e.curve}</div>
                  <div className="text-[10px] text-[var(--text-secondary)]">{e.desc}</div>
                </div>
              ))}
            </div>
          </GlassCard>
        </div>
      </section>

      {/* ── Elevation Scale (Session 39) ──────────────────────── */}
      <section>
        <h2 className="section-header">Elevation Scale (Session 39)</h2>
        <p className="text-xs text-[var(--text-secondary)] mb-3">
          Replaces 6 ad-hoc shadow tokens with a 5-step linear scale. 0 = flat, 5 = topmost overlay.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {[
            { level: 0, desc: "Flat, no shadow" },
            { level: 1, desc: "Hovered item" },
            { level: 2, desc: "Card, raised" },
            { level: 3, desc: "Elevated card (default Glass)" },
            { level: 4, desc: "Dialog, popover" },
            { level: 5, desc: "Modal, topmost" },
          ].map((e) => (
            <div
              key={e.level}
              className="p-5 rounded-xl bg-[var(--surface-1)] border border-white/[0.06]"
              style={{ boxShadow: `var(--elevation-${e.level})` }}
            >
              <div className="text-lg font-semibold">elevation-{e.level}</div>
              <div className="text-xs text-[var(--text-secondary)] mt-1">{e.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Glass Opacity Ladder (Session 39) ─────────────────── */}
      <section>
        <h2 className="section-header">Glass Opacity Ladder (Session 39)</h2>
        <p className="text-xs text-[var(--text-secondary)] mb-3">
          3-step canonical scale replacing 5+ ad-hoc opacities. Use via <code className="font-mono">var(--glass-base)</code>.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { name: "subtle", bg: "rgba(255,255,255,0.04)", border: "rgba(255,255,255,0.06)", desc: "Faint overlay (default Card)" },
            { name: "base", bg: "rgba(255,255,255,0.06)", border: "rgba(255,255,255,0.08)", desc: "Standard glass (GlassCard)" },
            { name: "strong", bg: "rgba(255,255,255,0.10)", border: "rgba(255,255,255,0.12)", desc: "Prominent card (hover)" },
          ].map((g) => (
            <div
              key={g.name}
              className="p-6 rounded-xl backdrop-blur-md"
              style={{ background: g.bg, border: `1px solid ${g.border}` }}
            >
              <div className="text-lg font-semibold">glass-{g.name}</div>
              <div className="text-xs text-[var(--text-secondary)] mt-1">{g.desc}</div>
              <div className="text-[10px] font-mono text-[var(--text-secondary)] mt-2">{g.bg}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Line-Height Tokens (Session 39) ────────────────────── */}
      <section>
        <h2 className="section-header">Line-Height Tokens (Session 39)</h2>
        <p className="text-xs text-[var(--text-secondary)] mb-3">
          Semantic line-heights replacing ad-hoc numeric values. Wired to Tailwind via <code className="font-mono">leading-{"{token}"}</code>.
        </p>
        <div className="grid grid-cols-1 gap-3">
          {[
            { name: "display", lh: 1.15, desc: "Hero numbers, H1" },
            { name: "heading", lh: 1.25, desc: "H2-H3" },
            { name: "ui", lh: 1.4, desc: "Buttons, labels, nav" },
            { name: "body", lh: 1.5, desc: "Paragraphs, prose" },
            { name: "tight", lh: 1.1, desc: "Dense numeric metrics" },
          ].map((l) => (
            <div key={l.name} className="p-3 rounded bg-white/[0.03] border border-white/[0.06]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono text-[var(--accent)]">leading-{l.name}</span>
                <span className="text-[10px] text-[var(--text-secondary)]">{l.lh} — {l.desc}</span>
              </div>
              <p className="text-sm" style={{ lineHeight: l.lh }}>
                The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog.
                Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt.
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Density Mode (Session 39) ─────────────────────────── */}
      <section>
        <h2 className="section-header">Density Mode (Session 39)</h2>
        <p className="text-xs text-[var(--text-secondary)] mb-3">
          Comfortable (default, farmer persona) vs Compact (trader persona with multiple dashboards).
          Toggle via the <kbd className="text-[10px] font-mono bg-white/[0.08] px-1 rounded">Rows</kbd> button in the top bar.
          Wired to <code className="font-mono">data-density</code> attribute on <code className="font-mono">&lt;html&gt;</code>.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl bg-[var(--surface-1)] border border-white/[0.06]">
            <p className="text-sm font-semibold mb-2">Comfortable</p>
            <div className="space-y-2 text-xs font-mono text-[var(--text-secondary)]">
              <div>--density-padding-sm: 8px</div>
              <div>--density-padding-md: 12px</div>
              <div>--density-padding-lg: 16px</div>
              <div>--density-row-height: 44px</div>
            </div>
          </div>
          <div className="p-4 rounded-xl bg-[var(--surface-1)] border border-white/[0.06]">
            <p className="text-sm font-semibold mb-2">Compact</p>
            <div className="space-y-2 text-xs font-mono text-[var(--text-secondary)]">
              <div>--density-padding-sm: 4px</div>
              <div>--density-padding-md: 8px</div>
              <div>--density-padding-lg: 12px</div>
              <div>--density-row-height: 32px</div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Token Stats ─────────────────────────────────────────── */}
      <section>
        <h2 className="section-header">Token Stats</h2>
        <GlassCard accent="salmon">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-kpi text-[var(--accent)]">120</p>
              <p className="text-xs text-[var(--text-secondary)]">Total Tokens</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-kpi text-[var(--accent)]">42</p>
              <p className="text-xs text-[var(--text-secondary)]">Color Tokens</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-kpi text-[var(--accent)]">14</p>
              <p className="text-xs text-[var(--text-secondary)]">UI Primitives</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-kpi text-[var(--accent)]">2</p>
              <p className="text-xs text-[var(--text-secondary)]">Themes (L/D)</p>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-white/[0.06] text-[10px] text-[var(--text-secondary)] text-center">
            Session 39: +motion (9) +elevation (6) +glass (6) +line-height (5) +density (8) +font-size (2) = <b className="text-[var(--accent)]">36 new tokens</b>
          </div>
        </GlassCard>
      </section>
    </div>
  );
}
