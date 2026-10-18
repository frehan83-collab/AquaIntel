"use client";

/**
 * MarginBridgePanel — the money view over the price and cost feeds.
 *
 * One card answers: where the margin is (price leg minus the modelled cost legs,
 * per kg), what moved it (price week on week, feed month on month), how far
 * break-even is, and which levers pay. Every leg carries its own period and status,
 * because the SSB price moves weekly and the FRED feed basket moves monthly — a
 * single "updated" stamp would be a lie about one of them.
 *
 * Honesty rules it renders, never hides:
 *  - `margin.quality` is `modelled` until the caller supplies both the price and the
 *    feed numbers; the badge flips to `measured` only then.
 *  - a leg whose provenance is not live shows its reason (e.g. the FRED basket's
 *    newest observation is three months old).
 *  - the modelled feed level is checked against the last audited realised cost and
 *    the gap is printed; the deillegalscription says the level is indicative while
 *    the deltas and the levers are not.
 */

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, RefreshCw, Scale, TrendingDown, TrendingUp } from "lucide-react";

import DataQualityBadge from "@/components/DataQualityBadge";
import GlassCard from "@/components/GlassCard";
import { api } from "@/lib/api";
import { formatNumber, useTranslation } from "@/lib/i18n";
import type { MarginBridge, MarginBridgeLeg } from "@/types/api";

const STATUS_STYLE: Record<string, string> = {
  measured: "bg-emerald-500/10 text-emerald-300",
  caller_supplied: "bg-ocean-500/10 text-ocean-300",
  modelled: "bg-amber-500/10 text-amber-300",
  structural: "bg-white/[0.06] text-[var(--text-secondary)]",
  unpriced: "bg-rose-500/10 text-rose-300",
};

function signed(value: number | null | undefined, locale: string): string {
  if (value == null || !isFinite(value)) return "\u2014";
  const text = formatNumber(Math.abs(value), locale as "en" | "no", 2);
  return value < 0 ? `\u2212${text}` : `+${text}`;
}

function statusLabel(status: string, t: (k: string) => string): string {
  const key = `margin_bridge.status_${status}`;
  const label = t(key);
  return label === key ? status.replace(/_/g, " ") : label;
}

function LegRow({ leg, locale, t }: { leg: MarginBridgeLeg; locale: string; t: (k: string) => string }) {
  const negative = (leg.nok_per_kg ?? 0) < 0;
  const isMargin = leg.kind === "margin";
  return (
    <div
      className={`flex items-center justify-between gap-3 py-1.5 ${
        isMargin ? "border-t border-white/[0.08] mt-1 pt-2 font-semibold" : ""
      }`}
      title={leg.detail ?? undefined}
    >
      <div className="min-w-0 flex items-center gap-2">
        <span className="text-[11px] text-[var(--text-primary)] truncate">{leg.label}</span>
        <span className={`text-[9px] px-1.5 py-0.5 rounded ${STATUS_STYLE[leg.status] ?? STATUS_STYLE.structural}`}>
          {statusLabel(leg.status, t)}
        </span>
        {leg.period && (
          <span className="text-[9px] text-[var(--text-secondary)] font-mono">{leg.period}</span>
        )}
      </div>
      <span
        className={`text-[11px] font-mono tabular-nums ${
          isMargin
            ? negative
              ? "text-rose-400"
              : "text-emerald-400"
            : negative
              ? "text-[var(--text-primary)]"
              : "text-emerald-300"
        }`}
      >
        {signed(leg.nok_per_kg, locale)}
        <span className="text-[9px] text-[var(--text-secondary)]"> /kg</span>
      </span>
    </div>
  );
}

export default function MarginBridgePanel({
  localityNo,
  className = "",
}: {
  localityNo?: number;
  className?: string;
}) {
  const { t, locale } = useTranslation();
  const [data, setData] = useState<MarginBridge | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showBasis, setShowBasis] = useState(false);
  const [form, setForm] = useState({ fcr: "", feed: "", spot: "", tonnes: "" });
  const [customised, setCustomised] = useState(false);

  const load = useCallback(
    async (useForm: boolean) => {
      setLoading(true);
      setError(null);
      try {
        const numeric = (value: string) => {
          const parsed = Number.parseFloat(value);
          return isFinite(parsed) && parsed > 0 ? parsed : undefined;
        };
        const payload = await api.marginBridge({
          localityNo,
          // Send only what the user typed. Seeding the inputs with the served model and
          // then submitting them would claim the industry model as "measured" on the
          // first click (WS-29 review) — placeholders show the model values instead.
          ...(useForm
            ? {
                fcr: numeric(form.fcr),
                feed: numeric(form.feed),
                spot: numeric(form.spot),
                annualTonnes: numeric(form.tonnes),
              }
            : {}),
        });
        setData(payload);
      } catch (err) {
        setError(err instanceof Error ? err.message : t("common.error_loading"));
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [localityNo],
  );

  useEffect(() => {
    void load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localityNo]);

  const apply = () => {
    const typed = Object.values(form).some((value) => value.trim() !== "");
    setCustomised(typed);
    void load(typed);
  };
  const reset = () => {
    setCustomised(false);
    setForm({ fcr: "", feed: "", spot: "", tonnes: "" });
    void load(false);
  };

  const margin = data?.margin;
  const breakEven = data?.break_even;
  const changes = data?.changes;
  const validation = data?.validation;
  const legs = data?.legs ?? [];
  const feedLeg = legs.find((leg) => leg.key === "feed");
  const priceLeg = legs.find((leg) => leg.key === "price");
  // Placeholders carry the served model's own numbers, so an empty field means "use
  // the model" and the measured/modelled badge cannot flip on an untouched form.
  const seeds: Record<string, string> = {
    fcr: feedLeg?.meta?.fcr != null ? String(feedLeg.meta.fcr) : "",
    feed: feedLeg?.meta?.delivered_feed_nok_per_kg != null
      ? String(feedLeg.meta.delivered_feed_nok_per_kg) : "",
    spot: priceLeg?.nok_per_kg != null ? String(priceLeg.nok_per_kg) : "",
    tonnes: "",
  };
  const scale = Math.max(
    Math.abs(margin?.spot_nok_per_kg ?? 0),
    Math.abs(margin?.modelled_cost_nok_per_kg ?? 0),
    1,
  );

  return (
    <GlassCard delay={0.2} accent="ocean" className={className}>
      <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <Scale className="w-4 h-4 text-ocean-400" />
          {t("margin_bridge.title")}
        </h3>
        <div className="flex items-center gap-2">
          {data?.week && (
            <span className="text-[10px] font-mono text-[var(--text-secondary)]">{data.week}</span>
          )}
          {margin && (
            <span
              className={`text-[9px] px-1.5 py-0.5 rounded ${
                margin.quality === "measured"
                  ? "bg-emerald-500/10 text-emerald-300"
                  : margin.quality === "modelled"
                    ? "bg-amber-500/10 text-amber-300"
                    : "bg-rose-500/10 text-rose-300"
              }`}
              title={margin.quality_basis}
            >
              {t(`margin_bridge.quality_${margin.quality}`)}
            </span>
          )}
          {data?.data_provenance && <DataQualityBadge provenance={data.data_provenance} />}
        </div>
      </div>

      {loading && !data ? (
        <div className="space-y-2 animate-pulse" aria-busy="true">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="h-6 rounded bg-white/[0.04]" />
          ))}
        </div>
      ) : error ? (
        <p className="text-[11px] text-rose-300">{error}</p>
      ) : data && margin ? (
        <div className="space-y-4">
          {/* Headline */}
          <div className="flex items-end justify-between gap-3">
            <div>
              <div
                className={`text-2xl font-semibold tabular-nums ${
                  (margin.nok_per_kg ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"
                }`}
              >
                {signed(margin.nok_per_kg, locale)}
                <span className="text-xs font-normal text-[var(--text-secondary)]"> NOK/kg</span>
              </div>
              <div className="text-[10px] text-[var(--text-secondary)]">
                {margin.pct != null ? `${formatNumber(margin.pct, locale, 1)} % ` : ""}
                {t("margin_bridge.over_modelled_cost")}
                {margin.modelled_cost_nok_per_kg != null &&
                  ` ${formatNumber(margin.modelled_cost_nok_per_kg, locale, 2)}`}
              </div>
            </div>
            {data.volume.annual_margin_nok != null && (
              <div className="text-right">
                <div className="text-[10px] text-[var(--text-secondary)]">
                  {t("margin_bridge.annual_result")}
                </div>
                <div className="text-sm font-mono tabular-nums text-[var(--text-primary)]">
                  {formatNumber(data.volume.annual_margin_nok / 1_000_000, locale, 1)} MNOK
                </div>
              </div>
            )}
          </div>

          {/* Spot vs modelled cost */}
          <div className="space-y-1.5">
            {[
              {
                label: t("margin_bridge.spot"),
                value: margin.spot_nok_per_kg,
                tone: "bg-emerald-500/50",
              },
              {
                label: t("margin_bridge.modelled_cost"),
                value: margin.modelled_cost_nok_per_kg,
                tone: "bg-rose-500/40",
              },
            ].map((row) => (
              <div key={row.label} className="flex items-center gap-2">
                <span className="w-24 text-[10px] text-[var(--text-secondary)]">{row.label}</span>
                <div className="flex-1 h-2 rounded-full bg-white/[0.06] overflow-hidden">
                  <div
                    className={`h-full rounded-full ${row.tone}`}
                    style={{ width: `${Math.min(100, (Math.abs(row.value ?? 0) / scale) * 100)}%` }}
                  />
                </div>
                <span className="w-16 text-right text-[10px] font-mono tabular-nums">
                  {row.value != null ? formatNumber(row.value, locale, 2) : "\u2014"}
                </span>
              </div>
            ))}
          </div>

          {/* Legs */}
          <div>
            {legs
              .filter((leg) => leg.kind !== "margin")
              .map((leg) => (
                <LegRow key={leg.key} leg={leg} locale={locale} t={t} />
              ))}
            {legs
              .filter((leg) => leg.kind === "margin")
              .map((leg) => (
                <LegRow key={leg.key} leg={leg} locale={locale} t={t} />
              ))}
          </div>

          {/* What moved */}
          <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-2.5 space-y-1">
            <div className="text-[10px] uppercase tracking-wide text-[var(--text-secondary)]">
              {t("margin_bridge.what_moved")}
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px]">
              <span className="flex items-center gap-1">
                {(changes?.price_wow_nok_per_kg ?? 0) >= 0 ? (
                  <TrendingUp className="w-3 h-3 text-emerald-400" />
                ) : (
                  <TrendingDown className="w-3 h-3 text-rose-400" />
                )}
                {t("margin_bridge.price")} {signed(changes?.price_wow_nok_per_kg, locale)}
                {changes?.price_previous_week && (
                  <span className="text-[9px] text-[var(--text-secondary)]">
                    ({changes.price_previous_week} {"\u2192"} {data.week})
                  </span>
                )}
              </span>
              <span className="flex items-center gap-1">
                {t("margin_bridge.feed")} {signed(changes?.feed_mom_nok_per_kg, locale)}
                {changes?.feed_period && (
                  <span className="text-[9px] text-[var(--text-secondary)]">
                    ({changes.feed_period})
                  </span>
                )}
              </span>
              <span className="font-mono tabular-nums">
                {"= "}
                {signed(changes?.margin_change_nok_per_kg, locale)}
                <span className="text-[9px] text-[var(--text-secondary)]">
                  {" "}
                  {t("margin_bridge.margin_change")}
                </span>
              </span>
            </div>
            <p className="text-[9px] text-[var(--text-secondary)]">{changes?.note}</p>
            {changes?.feed_weight_coverage_pct != null && changes.feed_weight_coverage_pct < 100 && (
              <p className="text-[9px] text-amber-300/80">
                {t("margin_bridge.feed_coverage")}:{" "}
                {formatNumber(changes.feed_weight_coverage_pct, locale, 0)} %
                {changes.feed_excluded_ingredients?.length
                  ? ` (${t("margin_bridge.feed_excluded")}: ${changes.feed_excluded_ingredients.join(", ")})`
                  : ""}
              </p>
            )}
          </div>

          {/* Break-even */}
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white/[0.03] border border-white/[0.06] p-2.5">
            <div className="text-[11px]">
              <span className="text-[var(--text-secondary)]">{t("margin_bridge.break_even")} </span>
              <span className="font-mono tabular-nums">
                {breakEven?.cost_nok_per_kg != null
                  ? formatNumber(breakEven.cost_nok_per_kg, locale, 2)
                  : "\u2014"}
              </span>
            </div>
            {breakEven?.feed_leg_reduction_needed_pct != null && (
              <div className="text-[10px] text-amber-300 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />
                {formatNumber(breakEven.feed_leg_reduction_needed_pct, locale, 1)} %{" "}
                {t("margin_bridge.feed_fall_to_break_even")}
              </div>
            )}
            {breakEven?.fcr_at_break_even != null && (
              <div className="text-[10px] text-[var(--text-secondary)]">
                {t("margin_bridge.fcr_at_break_even")}: {formatNumber(breakEven.fcr_at_break_even, locale, 2)}
              </div>
            )}
          </div>

          {/* Levers */}
          <div>
            <div className="text-[10px] uppercase tracking-wide text-[var(--text-secondary)] mb-1">
              {t("margin_bridge.levers")}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {data.levers.map((lever) => (
                <div
                  key={lever.key}
                  className="flex items-center justify-between gap-2 px-2 py-1 rounded-lg bg-white/[0.03] border border-white/[0.06]"
                  title={`${lever.formula} — ${lever.basis}`}
                >
                  <span className="text-[10px] text-[var(--text-primary)] truncate">{lever.label}</span>
                  <span className="text-[10px] font-mono tabular-nums text-emerald-300 whitespace-nowrap">
                    +{formatNumber(lever.nok_per_kg, locale, 2)}
                    {lever.nok_per_year != null && (
                      <span className="text-[9px] text-[var(--text-secondary)]">
                        {" "}
                        / {formatNumber(lever.nok_per_year / 1_000_000, locale, 1)} MNOK
                      </span>
                    )}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Your numbers */}
          <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-2.5">
            <div className="text-[10px] uppercase tracking-wide text-[var(--text-secondary)] mb-1.5">
              {t("margin_bridge.your_numbers")}
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
              {[
                { key: "fcr", label: t("margin_bridge.fcr"), step: "0.01", placeholder: "1.30" },
                { key: "feed", label: t("margin_bridge.feed_price"), step: "0.1", placeholder: "22.6" },
                { key: "spot", label: t("margin_bridge.your_price"), step: "0.1", placeholder: "72.6" },
                { key: "tonnes", label: t("margin_bridge.tonnes"), step: "100", placeholder: "5000" },
              ].map((field) => (
                <label key={field.key} className="block">
                  <span className="block text-[9px] text-[var(--text-secondary)] mb-0.5">
                    {field.label}
                  </span>
                  <input
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step={field.step}
                    value={form[field.key as keyof typeof form]}
                    placeholder={seeds[field.key] || field.placeholder}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, [field.key]: event.target.value }))
                    }
                    className="w-full px-2 py-1 rounded-md bg-[var(--surface-2)] border border-white/[0.08] text-[11px] font-mono tabular-nums text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-ocean-400/50"
                    aria-label={field.label}
                  />
                </label>
              ))}
            </div>
            <div className="flex items-center gap-2 mt-2">
              <button
                type="button"
                onClick={apply}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-ocean-500/15 text-ocean-300 text-[10px] hover:bg-ocean-500/25"
              >
                {t("margin_bridge.apply")}
                <ArrowRight className="w-3 h-3" />
              </button>
              <button
                type="button"
                onClick={reset}
                disabled={!customised}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-white/[0.05] text-[var(--text-secondary)] text-[10px] hover:bg-white/[0.1] disabled:opacity-40"
              >
                <RefreshCw className="w-3 h-3" />
                {t("margin_bridge.reset")}
              </button>
              <span className="text-[9px] text-[var(--text-secondary)]">
                {t("margin_bridge.measured_hint")}
              </span>
            </div>
          </div>

          {/* Basis and validation */}
          <div>
            <button
              type="button"
              onClick={() => setShowBasis((open) => !open)}
              className="text-[10px] text-ocean-300 hover:underline"
              aria-expanded={showBasis}
            >
              {showBasis ? t("margin_bridge.hide_basis") : t("margin_bridge.show_basis")}
            </button>
            {showBasis && (
              <div className="mt-1.5 space-y-1.5 text-[9px] text-[var(--text-secondary)]">
                <p>{data.method}</p>
                {validation?.available && (
                  <p
                    className={
                      validation.within_tolerance === false ? "text-amber-300" : undefined
                    }
                  >
                    {/* Print the number the gap was computed from: with caller inputs the
                        comparison is against your feed leg, not the model's. */}
                    {t("margin_bridge.validation")}:{" "}
                    {(() => {
                      const compared =
                        validation.compared === "caller_inputs"
                          ? validation.caller_feed_nok_per_kg_salmon
                          : validation.modelled_feed_nok_per_kg_salmon;
                      return compared != null
                        ? `${formatNumber(compared, locale, 2)} ${
                            validation.compared === "caller_inputs" ? "(yours) " : "(model) "
                          }`
                        : "";
                    })()}
                    {validation.official_feed_nok_per_kg_salmon != null &&
                      `vs ${formatNumber(validation.official_feed_nok_per_kg_salmon, locale, 2)} `}
                    ({validation.anchor_year}){" "}
                    {validation.gap_pct != null && `= ${signed(validation.gap_pct, locale)} %`}
                    {validation.note && (
                      <span className="block text-[var(--text-secondary)]">{validation.note}</span>
                    )}
                  </p>
                )}
                <ul className="list-disc list-inside space-y-0.5">
                  {data.assumptions.map((assumption) => (
                    <li key={assumption.key}>
                      <span className="font-mono">{assumption.key}</span> ={" "}
                      {typeof assumption.value === "object"
                        ? JSON.stringify(assumption.value)
                        : String(assumption.value)}{" "}
                      {assumption.unit} · {assumption.source}
                    </li>
                  ))}
                </ul>
                <p>{data.scope.reason}</p>
                <p>{data.volume.basis}</p>
              </div>
            )}
          </div>
        </div>
      ) : (
        <p className="text-[11px] text-[var(--text-secondary)]">{t("common.no_data")}</p>
      )}
    </GlassCard>
  );
}
