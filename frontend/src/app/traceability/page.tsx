"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  FileCheck, Ship, Package, AlertTriangle, Leaf,
  Plus, Search, ChevronRight, Shield, Globe2,
} from "lucide-react";
import KPICard from "@/components/KPICard";
import GlassCard from "@/components/GlassCard";
import { OcButton } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useTranslation, formatDate } from "@/lib/i18n";

type Tab = "certificates" | "lots" | "iuu" | "eudr";

export default function TraceabilityPage() {
  const { t, locale } = useTranslation();
  const [tab, setTab] = useState<Tab>("certificates");
  const [dashboard, setDashboard] = useState<any>(null);
  const [certificates, setCertificates] = useState<any[]>([]);
  const [eudr, setEudr] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // IUU form state
  const [iuuVessel, setIuuVessel] = useState("");
  const [iuuFlag, setIuuFlag] = useState("");
  const [iuuImo, setIuuImo] = useState("");
  const [iuuCatchArea, setIuuCatchArea] = useState("");
  const [iuuResult, setIuuResult] = useState<any>(null);
  const [iuuLoading, setIuuLoading] = useState(false);

  // Certificate form
  const [certVessel, setCertVessel] = useState("");
  const [certFlag, setCertFlag] = useState("Norway");
  const [certArea, setCertArea] = useState("");
  const [certQty, setCertQty] = useState("");
  const [certCreating, setCertCreating] = useState(false);

  // Lot lookup
  const [lotId, setLotId] = useState("");
  const [lotChain, setLotChain] = useState<any>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [d, c, e] = await Promise.allSettled([
        api.traceabilityDashboard(),
        api.traceabilityListCertificates(),
        api.traceabilityEUDRStatus(),
      ]);
      if (d.status === "fulfilled") setDashboard(d.value);
      if (c.status === "fulfilled") setCertificates(c.value);
      if (e.status === "fulfilled") setEudr(e.value);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleCreateCert = async () => {
    setCertCreating(true);
    try {
      await api.traceabilityCreateCertificate({
        vessel_name: certVessel,
        flag_state: certFlag,
        catch_area: certArea,
        quantity_kg: parseFloat(certQty) || 0,
      });
      setCertVessel(""); setCertArea(""); setCertQty("");
      load();
    } catch { /* empty */ }
    setCertCreating(false);
  };

  const handleIUURisk = async () => {
    setIuuLoading(true);
    try {
      const result = await api.traceabilityIUURisk({
        vessel_name: iuuVessel,
        flag_state: iuuFlag,
        imo_number: iuuImo,
        catch_area: iuuCatchArea,
      });
      setIuuResult(result);
    } catch { /* empty */ }
    setIuuLoading(false);
  };

  const handleLotLookup = async () => {
    if (!lotId) return;
    try {
      const result = await api.traceabilityChainOfCustody(lotId);
      setLotChain(result);
    } catch { setLotChain(null); }
  };

  const tabs: { key: Tab; label: string; icon: any }[] = [
    { key: "certificates", label: "Certificates", icon: FileCheck },
    { key: "lots", label: "Lot Tracking", icon: Package },
    { key: "iuu", label: "IUU Risk", icon: AlertTriangle },
    { key: "eudr", label: "EUDR", icon: Leaf },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">{t("traceability.title")}</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Catch certificates, lot tracking, IUU risk &amp; EUDR compliance
          </p>
        </div>
        <OcButton onClick={load} loading={loading}>Refresh</OcButton>
      </motion.div>

      {/* KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPICard label={t("traceability.certificates")} value={dashboard?.active_certificates ?? 0} icon={FileCheck} delay={0} />
        <KPICard label={t("traceability.lot_tracking")} value={dashboard?.lots_in_transit ?? 0} icon={Package} delay={0.05} />
        <KPICard label={t("traceability.iuu_risk")} value={dashboard?.iuu_high_risk_alerts ?? 0} icon={AlertTriangle} delay={0.1} />
        <KPICard label="EUDR Compliance" value={`${dashboard?.eudr_compliance_pct ?? 100}%`} icon={Leaf} delay={0.15} />
      </div>

      {/* Tab Switcher */}
      <div className="flex gap-1 p-1 rounded-lg bg-white/[0.03]">
        {tabs.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                tab === t.key
                  ? "bg-ocean-500/20 text-ocean-400"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Certificates Tab */}
      {tab === "certificates" && (
        <div className="space-y-4">
          <GlassCard delay={0.1} accent="ocean">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Create Catch Certificate</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <input className="bg-white/[0.06] border border-white/[0.1] rounded-md px-3 py-1.5 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]" placeholder="Vessel name" value={certVessel} onChange={(e) => setCertVessel(e.target.value)} />
              <input className="bg-white/[0.06] border border-white/[0.1] rounded-md px-3 py-1.5 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]" placeholder="Flag state" value={certFlag} onChange={(e) => setCertFlag(e.target.value)} />
              <input className="bg-white/[0.06] border border-white/[0.1] rounded-md px-3 py-1.5 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]" placeholder="Catch area (FAO)" value={certArea} onChange={(e) => setCertArea(e.target.value)} />
              <input className="bg-white/[0.06] border border-white/[0.1] rounded-md px-3 py-1.5 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]" placeholder="Quantity (kg)" value={certQty} onChange={(e) => setCertQty(e.target.value)} />
            </div>
            <OcButton className="mt-3" size="sm" onClick={handleCreateCert} loading={certCreating} leftIcon={<Plus className="w-3.5 h-3.5" />}>
              Create Certificate
            </OcButton>
          </GlassCard>

          <GlassCard delay={0.2} accent="none">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Certificates</h3>
            {certificates.length === 0 ? (
              <p className="text-xs text-[var(--text-secondary)]">No certificates yet.</p>
            ) : (
              <div className="space-y-1">
                <div className="flex text-[10px] font-medium text-[var(--text-secondary)] uppercase tracking-wider pb-1 border-b border-white/[0.06]">
                  <span className="flex-1">Certificate</span>
                  <span className="w-32">Vessel</span>
                  <span className="w-20">Flag</span>
                  <span className="w-24 text-right">Qty (kg)</span>
                  <span className="w-20 text-right">Status</span>
                </div>
                {certificates.map((c: any) => (
                  <div key={c.id} className="flex items-center text-xs py-1.5 border-b border-white/[0.03]">
                    <span className="flex-1 text-ocean-400 font-mono">{c.certificate_no}</span>
                    <span className="w-32 text-[var(--text-primary)] truncate">{c.vessel_name}</span>
                    <span className="w-20 text-[var(--text-secondary)]">{c.flag_state}</span>
                    <span className="w-24 text-right text-[var(--text-primary)]">{c.quantity_kg?.toLocaleString()}</span>
                    <span className="w-20 text-right">
                      <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${
                        c.status === "validated" ? "bg-emerald-500/10 text-emerald-400"
                          : c.status === "rejected" ? "bg-rose-500/10 text-rose-400"
                          : "bg-amber-500/10 text-amber-400"
                      }`}>{c.status}</span>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>
        </div>
      )}

      {/* Lot Tracking Tab */}
      {tab === "lots" && (
        <div className="space-y-4">
          <GlassCard delay={0.1} accent="emerald">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Chain of Custody Lookup</h3>
            <div className="flex gap-2">
              <input className="flex-1 bg-white/[0.06] border border-white/[0.1] rounded-md px-3 py-1.5 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]" placeholder="Enter Lot ID (e.g. LOT-20260331-A1B2C3D4)" value={lotId} onChange={(e) => setLotId(e.target.value)} />
              <OcButton size="sm" onClick={handleLotLookup} leftIcon={<Search className="w-3.5 h-3.5" />}>
                Lookup
              </OcButton>
            </div>
          </GlassCard>

          {lotChain && (
            <GlassCard delay={0.2} accent="none">
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2">
                Lot: <span className="font-mono text-ocean-400">{lotChain.lot_id}</span>
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mb-3">
                <div><span className="text-[var(--text-secondary)]">Product</span><div className="text-[var(--text-primary)]">{lotChain.product_type}</div></div>
                <div><span className="text-[var(--text-secondary)]">Quantity</span><div className="text-[var(--text-primary)]">{lotChain.quantity_kg?.toLocaleString()} kg</div></div>
                <div><span className="text-[var(--text-secondary)]">Holder</span><div className="text-[var(--text-primary)]">{lotChain.current_holder}</div></div>
                <div><span className="text-[var(--text-secondary)]">Status</span><div className="text-[var(--text-primary)]">{lotChain.status}</div></div>
              </div>
              <h4 className="text-xs font-medium text-[var(--text-secondary)] mb-2">Chain of Custody</h4>
              <div className="space-y-2">
                {(lotChain.chain || []).map((evt: any, i: number) => (
                  <div key={i} className="flex items-start gap-3">
                    <div className="w-2 h-2 rounded-full bg-ocean-400 mt-1.5 flex-shrink-0" />
                    <div className="text-xs">
                      <div className="text-[var(--text-primary)] font-medium">{evt.event}</div>
                      <div className="text-[var(--text-secondary)]">{evt.holder} &middot; {evt.location}</div>
                      <div className="text-[var(--text-secondary)] text-[10px]">{evt.timestamp}</div>
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>
          )}
        </div>
      )}

      {/* IUU Risk Tab */}
      {tab === "iuu" && (
        <div className="space-y-4">
          <GlassCard delay={0.1} accent="rose">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">IUU Risk Assessment</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <input className="bg-white/[0.06] border border-white/[0.1] rounded-md px-3 py-1.5 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]" placeholder="Vessel name" value={iuuVessel} onChange={(e) => setIuuVessel(e.target.value)} />
              <input className="bg-white/[0.06] border border-white/[0.1] rounded-md px-3 py-1.5 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]" placeholder="Flag state" value={iuuFlag} onChange={(e) => setIuuFlag(e.target.value)} />
              <input className="bg-white/[0.06] border border-white/[0.1] rounded-md px-3 py-1.5 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]" placeholder="IMO number" value={iuuImo} onChange={(e) => setIuuImo(e.target.value)} />
              <input className="bg-white/[0.06] border border-white/[0.1] rounded-md px-3 py-1.5 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]" placeholder="Catch area" value={iuuCatchArea} onChange={(e) => setIuuCatchArea(e.target.value)} />
            </div>
            <OcButton className="mt-3" size="sm" onClick={handleIUURisk} loading={iuuLoading} leftIcon={<Shield className="w-3.5 h-3.5" />}>
              Assess Risk
            </OcButton>
          </GlassCard>

          {iuuResult && (
            <GlassCard delay={0.2} accent={iuuResult.risk_level === "critical" ? "rose" : iuuResult.risk_level === "high" ? "amber" : "emerald"}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">{iuuResult.vessel_name}</h3>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                  iuuResult.risk_level === "critical" ? "bg-rose-500/10 text-rose-400"
                    : iuuResult.risk_level === "high" ? "bg-amber-500/10 text-amber-400"
                    : iuuResult.risk_level === "medium" ? "bg-yellow-500/10 text-yellow-400"
                    : "bg-emerald-500/10 text-emerald-400"
                }`}>
                  {iuuResult.risk_level?.toUpperCase()} &mdash; {iuuResult.risk_score}/100
                </span>
              </div>
              <div className="space-y-2">
                {Object.entries(iuuResult.factors || {}).map(([key, val]: [string, any]) => (
                  <div key={key} className="flex items-center justify-between text-xs">
                    <span className="text-[var(--text-secondary)]">{key.replace(/_/g, " ")}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                        <div className="h-full rounded-full bg-ocean-400" style={{ width: `${Math.min(val.score * 4, 100)}%` }} />
                      </div>
                      <span className="text-[var(--text-primary)] w-6 text-right">{val.score}</span>
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>
          )}
        </div>
      )}

      {/* EUDR Tab */}
      {tab === "eudr" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPICard label="Total Suppliers" value={eudr?.total_suppliers ?? 0} icon={Globe2} delay={0} />
            <KPICard label="Compliant" value={eudr?.compliant ?? 0} icon={Leaf} delay={0.05} />
            <KPICard label="Non-Compliant" value={eudr?.non_compliant ?? 0} icon={AlertTriangle} delay={0.1} />
            <KPICard label="Compliance Rate" value={`${eudr?.compliance_pct ?? 100}%`} icon={Shield} delay={0.15} />
          </div>

          <GlassCard delay={0.2} accent="emerald">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Feed Supplier Compliance</h3>
            {(!eudr?.suppliers || eudr.suppliers.length === 0) ? (
              <p className="text-xs text-[var(--text-secondary)]">No suppliers registered yet. Add feed suppliers to track EUDR compliance.</p>
            ) : (
              <div className="space-y-1">
                <div className="flex text-[10px] font-medium text-[var(--text-secondary)] uppercase tracking-wider pb-1 border-b border-white/[0.06]">
                  <span className="flex-1">Supplier</span>
                  <span className="w-20">Product</span>
                  <span className="w-24">Origin</span>
                  <span className="w-28">Cert Valid Until</span>
                  <span className="w-24 text-right">Status</span>
                </div>
                {eudr.suppliers.map((s: any) => (
                  <div key={s.id} className="flex items-center text-xs py-1.5 border-b border-white/[0.03]">
                    <span className="flex-1 text-[var(--text-primary)]">{s.supplier_name}</span>
                    <span className="w-20 text-[var(--text-secondary)]">{s.product}</span>
                    <span className="w-24 text-[var(--text-secondary)]">{s.country_of_origin}</span>
                    <span className="w-28 text-[var(--text-secondary)]">
                      {s.certification_valid_until ? formatDate(s.certification_valid_until, locale) : "\u2014"}
                    </span>
                    <span className="w-24 text-right">
                      <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${
                        s.status === "compliant" ? "bg-emerald-500/10 text-emerald-400"
                          : s.status === "non_compliant" ? "bg-rose-500/10 text-rose-400"
                          : "bg-amber-500/10 text-amber-400"
                      }`}>{s.status}</span>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>

          <GlassCard delay={0.3} accent="amber">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2">High Deforestation Risk Countries</h3>
            <p className="text-xs text-[var(--text-secondary)] mb-2">Feed sourced from these countries requires enhanced due diligence under EUDR.</p>
            <div className="flex flex-wrap gap-1.5">
              {(eudr?.high_risk_countries || []).map((c: string) => (
                <span key={c} className="px-2 py-0.5 rounded-full text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  {c}
                </span>
              ))}
            </div>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
