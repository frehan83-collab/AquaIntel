"use client";

import { useState, useEffect, useCallback } from "react";

export type Locale = "en" | "no";

// ── Formatting utilities (MUST be near top for reliable webpack bundling) ──
const _localeMap: Record<Locale, string> = { en: "en-US", no: "nb-NO" };

export function formatDate(date: Date | string, locale: Locale): string {
  const d = typeof date === "string" ? new Date(date) : date;
  if (isNaN(d.getTime())) return String(date);
  return d.toLocaleDateString(_localeMap[locale], { day: "numeric", month: "short", year: "numeric" });
}

export function formatNumber(n: number, locale: Locale, decimals = 0): string {
  if (n == null || !isFinite(n)) return "\u2014";
  return n.toLocaleString(_localeMap[locale], { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export function formatCurrency(n: number, locale: Locale, currency = "NOK"): string {
  if (n == null || !isFinite(n)) return "\u2014";
  return n.toLocaleString(_localeMap[locale], { style: "currency", currency, minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const STORAGE_KEY = "oc_locale";

/**
 * Translation dictionary: English and Norwegian Bokmal.
 * ~100 keys covering navigation, buttons, KPIs, status, and time strings.
 */
const translations: Record<string, Record<Locale, string>> = {
  // ── Navigation: section headers ──
  "nav.intelligence": { en: "Intelligence", no: "Etterretning" },
  "nav.markets": { en: "Markets", no: "Markeder" },
  "nav.regions": { en: "Regions", no: "Regioner" },
  "nav.operations": { en: "Operations", no: "Drift" },
  "nav.advanced": { en: "Advanced", no: "Avansert" },
  "nav.compliance": { en: "Compliance", no: "Samsvar" },
  "nav.system": { en: "System", no: "System" },

  // ── Navigation: page labels ──
  "nav.dashboard": { en: "Dashboard", no: "Dashbord" },
  "nav.daily_check": { en: "Daily Check", no: "Daglig sjekk" },
  "nav.morning_brief": { en: "Morning Brief", no: "Morgenrapport" },
  "nav.notifications": { en: "Notifications", no: "Varsler" },
  "nav.leaders_esg": { en: "Leaders & ESG", no: "Ledere og ESG" },
  "nav.peer_benchmark": { en: "Peer Benchmark", no: "Sammenligning" },
  "nav.bio_risk_map": { en: "Bio Risk Map", no: "Biorisikokart" },
  "nav.disease_intel": { en: "Disease Intel", no: "Sykdomsinfo" },
  "nav.climate_risk": { en: "Climate Risk", no: "Klimarisiko" },
  "nav.traffic_light": { en: "Traffic Light", no: "Trafikklys" },
  "nav.lice_quotas": { en: "Lice Quotas", no: "Lusekvote" },
  "nav.compare": { en: "Compare", no: "Sammenlign" },
  "nav.production_costs": { en: "Production Costs", no: "Produksjonskostnader" },
  "nav.feed_supply_chain": { en: "Feed Supply Chain", no: "Fôrforsyningskjede" },
  "nav.global_supply": { en: "Global Supply", no: "Global tilbud" },
  "nav.competitiveness": { en: "Competitiveness", no: "Konkurranseevne" },
  "nav.supply_forecast": { en: "Supply Forecast", no: "Tilbudsprognose" },
  "nav.investor_intel": { en: "Investor Intel", no: "Investorinfo" },
  "nav.trader_intel": { en: "Trader Intel", no: "Handelsinfo" },
  "nav.salmon_futures": { en: "Salmon Futures", no: "Laksefutures" },
  "nav.market_terminal": { en: "Market Terminal", no: "Markedsterminal" },
  "nav.price_predictions": { en: "Price & Predictions", no: "Pris og prognoser" },
  "nav.signals": { en: "Signals", no: "Signaler" },
  "nav.canada_bc": { en: "Canada / BC", no: "Canada / BC" },
  "nav.scotland": { en: "Scotland", no: "Skottland" },
  "nav.faroe_islands": { en: "Faroe Islands", no: "Færøyene" },
  "nav.iceland": { en: "Iceland", no: "Island" },
  "nav.china_demand": { en: "China Demand", no: "Kina-etterspørsel" },
  "nav.my_portfolio": { en: "My Portfolio", no: "Min portefølje" },
  "nav.farm_advisory": { en: "Farm Advisory", no: "Anleggsrådgivning" },
  "nav.treatment_optimizer": { en: "Treatment Optimizer", no: "Behandlingsoptimerer" },
  "nav.efficacy_market": { en: "Efficacy Market", no: "Effektmarked" },
  "nav.harvest_optimizer": { en: "Harvest Optimizer", no: "Slakteoptimerer" },
  "nav.digital_twin": { en: "Digital Twin", no: "Digital tvilling" },
  "nav.satellite_intel": { en: "Satellite Intel", no: "Satellittinfo" },
  "nav.command_centre": { en: "Command Centre", no: "Kommandosenter" },
  "nav.scenario_lab": { en: "Scenario Lab", no: "Scenariolab" },
  "nav.scenarios": { en: "Scenarios", no: "Scenarier" },
  "nav.causal_engine": { en: "Causal Engine", no: "Årsaksmotor" },
  "nav.ai_chat": { en: "AI Chat", no: "AI-chat" },
  "nav.ml_baselines": { en: "ML Baselines", no: "ML-grunnlinjer" },
  "nav.ras_tracker": { en: "RAS Tracker", no: "RAS-sporing" },
  "nav.asc_compliance": { en: "ASC Compliance", no: "ASC-samsvar" },
  "nav.eu_traceability": { en: "EU Traceability", no: "EU-sporbarhet" },
  "nav.contract_risk": { en: "Contract Risk", no: "Kontraktsrisiko" },
  "nav.insurance": { en: "Insurance", no: "Forsikring" },
  "nav.compliance_page": { en: "Compliance", no: "Samsvar" },
  "nav.admin": { en: "Admin", no: "Admin" },
  "nav.api_docs": { en: "API Docs", no: "API-dokumentasjon" },
  "nav.changelog": { en: "Changelog", no: "Endringslogg" },
  "nav.billing": { en: "Billing", no: "Fakturering" },
  "nav.privacy": { en: "Privacy", no: "Personvern" },
  "nav.settings": { en: "Settings", no: "Innstillinger" },
  "nav.webhooks": { en: "Webhooks", no: "Webhooker" },

  // ── Common buttons ──
  "btn.save": { en: "Save", no: "Lagre" },
  "btn.cancel": { en: "Cancel", no: "Avbryt" },
  "btn.delete": { en: "Delete", no: "Slett" },
  "btn.close": { en: "Close", no: "Lukk" },
  "btn.export": { en: "Export", no: "Eksporter" },
  "btn.search": { en: "Search", no: "Søk" },
  "btn.filter": { en: "Filter", no: "Filtrer" },
  "btn.apply": { en: "Apply", no: "Bruk" },
  "btn.reset": { en: "Reset", no: "Tilbakestill" },
  "btn.confirm": { en: "Confirm", no: "Bekreft" },
  "btn.submit": { en: "Submit", no: "Send inn" },
  "btn.back": { en: "Back", no: "Tilbake" },
  "btn.next": { en: "Next", no: "Neste" },
  "btn.previous": { en: "Previous", no: "Forrige" },
  "btn.view_all": { en: "View All", no: "Vis alle" },
  "btn.load_more": { en: "Load More", no: "Last flere" },
  "btn.retry": { en: "Try Again", no: "Prøv igjen" },
  "btn.mark_all_read": { en: "Mark all read", no: "Merk alle som lest" },

  // ── Domain terms ──
  "domain.lice": { en: "Lice", no: "Lakselus" },
  "domain.disease": { en: "Disease", no: "Sykdom" },
  "domain.treatment": { en: "Treatment", no: "Behandling" },
  "domain.farm": { en: "Farm", no: "Oppdrettsanlegg" },
  "domain.salmon": { en: "Salmon", no: "Laks" },
  "domain.production_area": { en: "Production Area", no: "Produksjonsområde" },
  "domain.alert": { en: "Alert", no: "Varsel" },
  "domain.notification": { en: "Notification", no: "Varsling" },
  "domain.price": { en: "Price", no: "Pris" },
  "domain.market": { en: "Market", no: "Marked" },
  "domain.supply": { en: "Supply", no: "Tilbud" },
  "domain.biomass": { en: "Biomass", no: "Biomasse" },
  "domain.mortality": { en: "Mortality", no: "Dødelighet" },
  "domain.feed": { en: "Feed", no: "For" },

  // ── Status words ──
  "status.active": { en: "Active", no: "Aktiv" },
  "status.inactive": { en: "Inactive", no: "Inaktiv" },
  "status.critical": { en: "Critical", no: "Kritisk" },
  "status.warning": { en: "Warning", no: "Advarsel" },
  "status.healthy": { en: "Healthy", no: "Frisk" },
  "status.elevated": { en: "Elevated", no: "Forhøyet" },
  "status.low": { en: "Low", no: "Lav" },
  "status.high": { en: "High", no: "Høy" },
  "status.live": { en: "Live", no: "Direkte" },
  "status.loading": { en: "Loading...", no: "Laster..." },
  "status.error": { en: "Error", no: "Feil" },
  "status.unknown": { en: "Unknown", no: "Ukjent" },

  // ── Time strings ──
  "time.just_now": { en: "Just now", no: "Akkurat nå" },
  "time.minutes_ago": { en: "m ago", no: "min siden" },
  "time.hours_ago": { en: "h ago", no: "t siden" },
  "time.days_ago": { en: "d ago", no: "d siden" },

  // ── DataTable ──
  "table.search": { en: "Search...", no: "Søk..." },
  "table.rows_per_page": { en: "Rows per page:", no: "Rader per side:" },
  "table.of": { en: "of", no: "av" },
  "table.page": { en: "Page", no: "Side" },
  "table.no_data": { en: "No data available", no: "Ingen data tilgjengelig" },
  "table.no_results": { en: "No matching pages", no: "Ingen treff" },
  "table.results": { en: "results", no: "resultater" },
  "table.result": { en: "result", no: "resultat" },
  "table.enter_to_go": { en: "Enter to go", no: "Enter for å gå" },

  // ── EmptyState ──
  "empty.title": { en: "No data available", no: "Ingen data tilgjengelig" },
  "empty.message": { en: "Check back later or adjust your filters.", no: "Kom tilbake senere eller juster filtrene." },

  // ── Alerts ──
  "alerts.title": { en: "Alerts", no: "Varsler" },
  "alerts.new": { en: "new", no: "nye" },
  "alerts.no_alerts": { en: "No alerts yet", no: "Ingen varsler enna" },
  "alerts.threshold_breaches": { en: "Threshold Breaches", no: "Terskeloverskridelser" },
  "alerts.view_all": { en: "View All Alerts", no: "Vis alle varsler" },

  // ── Sidebar search ──
  "search.pages": { en: "Search pages...", no: "Søk i sider..." },

  // ── Decision Explanation (SHAP-style feature importance) ──
  "explain.title": { en: "Decision Explanation", no: "Beslutningsforklaring" },
  "explain.factors": { en: "Contributing Factors", no: "Medvirkende faktorer" },
  "explain.summary": { en: "Summary", no: "Sammendrag" },
  "explain.importance": { en: "Importance", no: "Viktighet" },
  "explain.factor.lice_level": { en: "Lice Level", no: "Lusenivå" },
  "explain.factor.lice_trend": { en: "Lice Trend", no: "Lusetrend" },
  "explain.factor.sea_temperature": { en: "Sea Temperature", no: "Sjøtemperatur" },
  "explain.factor.gnn_prediction": { en: "GNN Prediction", no: "GNN-prediksjon" },
  "explain.factor.regulatory_distance": { en: "Regulatory Distance", no: "Regulatorisk avstand" },
  "explain.factor.season": { en: "Season", no: "Sesong" },
  "explain.action.TREAT_NOW": { en: "Treatment recommended immediately", no: "Behandling anbefalt umiddelbart" },
  "explain.action.SCHEDULE_TREATMENT": { en: "Treatment should be scheduled", no: "Behandling bør planlegges" },
  "explain.action.MONITOR": { en: "Close monitoring recommended", no: "Tett overvåkning anbefalt" },
  "explain.action.NO_ACTION": { en: "No action needed", no: "Ingen handling nødvendig" },
  "explain.lice_exceeds_limit": { en: "Lice level exceeds regulatory limit", no: "Lusenivå overstiger regulatorisk grense" },
  "explain.lice_exceeds_warning": { en: "Lice level exceeds warning threshold", no: "Lusenivå er over varselsgrensen" },
  "explain.lice_safe": { en: "Lice level is within safe range", no: "Lusenivå er innenfor trygt område" },
  "explain.trend_rising": { en: "Rising lice trend increases urgency", no: "Stigende lusetrend økerhastegrad" },
  "explain.trend_stable": { en: "Stable lice trend", no: "Stabil lusetrend" },
  "explain.trend_declining": { en: "Declining lice trend reduces urgency", no: "Synkende lusetrend reduserer hastegrad" },
  "explain.temp_high": { en: "High sea temperature accelerates lice reproduction", no: "Hoy sjøtemperatur akselererer luseproduksjon" },
  "explain.temp_moderate": { en: "Moderate sea temperature for lice growth", no: "Moderat sjøtemperatur for lusevekst" },
  "explain.temp_low": { en: "Low sea temperature slows lice reproduction", no: "Lav sjøtemperatur bremser luseproduksjon" },
  "explain.temp_unavailable": { en: "Sea temperature data unavailable", no: "Sjøtemperaturdata er utilgjengelig" },
  "explain.gnn_unavailable": { en: "GNN model unavailable", no: "GNN-modell utilgjengelig" },
  "explain.peak_season": { en: "Peak lice season", no: "Høysesong for lus" },
  "explain.low_season": { en: "Low lice season", no: "Lavsesong for lus" },

  // ── Marine Heatwave ──
  "heatwave.title": { en: "Marine Heatwave Alert", no: "Marin hetbølgevarsel" },
  "heatwave.critical": { en: "critical", no: "kritisk" },
  "heatwave.warning": { en: "warning", no: "advarsel" },
  "heatwave.watch": { en: "watch", no: "observasjon" },
  "heatwave.normal": { en: "normal", no: "normal" },
  "heatwave.description": { en: "Warm water accelerates lice reproduction and increases disease risk.", no: "Varmt vann akselererer luseproduksjon og økersykdomsrisiko." },
  "heatwave.elevated_pa": { en: "production areas with elevated sea temperatures", no: "produksjonsområder med forhøyede sjøtemperaturer" },

  // ── Treatment Resistance ──
  "resistance.title": { en: "Treatment Resistance", no: "Behandlingsresistens" },
  "resistance.high": { en: "High resistance detected", no: "Høy resistens oppdaget" },
  "resistance.rotate": { en: "Consider rotating treatment methods to maintain efficacy.", no: "Vurder å rotere behandlingsmetoder for å opprettholde effektivitet." },
  "resistance.check_map": { en: "Check the Resistance Map for details.", no: "Sjekk resistenskartet for detaljer." },

  // ── Farmer Daily ──
  "farmer.why_recommendation": { en: "Why This Recommendation", no: "Hvorfor denne anbefalingen" },
  "farmer.i_treated_today": { en: "I Treated Today", no: "Jeg behandlet i dag" },
  "farmer.log_treatment": { en: "Log Treatment", no: "Logg behandling" },
  "farmer.treatment_logged": { en: "Treatment logged successfully", no: "Behandling logget" },

  // ── Page: API Docs ──
  "page.api_docs.title": { en: "API Documentation", no: "API-dokumentasjon" },
  "page.api_docs.subtitle": { en: "Integrate FishIntel intelligence into your systems", no: "Integrer FishIntel-etterretning i dine systemer" },
  "page.api_docs.auth_section": { en: "Authentication", no: "Autentisering" },
  "page.api_docs.endpoints": { en: "Endpoints", no: "Endepunkter" },
  "page.api_docs.code_examples": { en: "Code Examples", no: "Kodeeksempler" },
  "page.api_docs.data_provenance": { en: "Data Provenance", no: "Dataopprinnelse" },
  "page.api_docs.rate_limits": { en: "Rate Limits", no: "Frekvensbegrensninger" },
  "page.api_docs.api_keys": { en: "API Keys", no: "API-nøkler" },
  "page.api_docs.generate_key": { en: "Generate New Key", no: "Generer ny nøkkel" },
  "page.api_docs.revoke_key": { en: "Revoke Key", no: "Tilbakekall nøkkel" },
  "page.api_docs.copy_key": { en: "Copy Key", no: "Kopier nøkkel" },
  "page.api_docs.copied": { en: "Copied!", no: "Kopiert!" },

  // ── Page: Changelog ──
  "page.changelog.title": { en: "Changelog", no: "Endringslogg" },
  "page.changelog.subtitle": { en: "What&apos;s new in FishIntel", no: "Hva er nytt i FishIntel" },
  "page.changelog.new": { en: "New", no: "Nytt" },
  "page.changelog.enhanced": { en: "Enhanced", no: "Forbedret" },
  "page.changelog.fixed": { en: "Fixed", no: "Fikset" },
  "page.changelog.version": { en: "Version", no: "Versjon" },
  "page.changelog.released": { en: "Released", no: "Utgitt" },

  // ── Page: Welcome / Onboarding ──
  "page.welcome.title": { en: "Welcome to FishIntel", no: "Velkommen til FishIntel" },
  "page.welcome.subtitle": { en: "The world's most advanced salmon aquaculture intelligence platform.", no: "Verdens mest avanserte plattform for lakseoppdrettsetterretning." },
  "page.welcome.choose_perspective": { en: "Choose your perspective to get a guided tour of the features that matter most to you.", no: "Velg ditt perspektiv for en omvisning av funksjonene som er viktigst for deg." },
  "page.welcome.farmer": { en: "Farmer", no: "Oppdretter" },
  "page.welcome.farmer_subtitle": { en: "Daily operations & treatment decisions", no: "Daglig drift og behandlingsbeslutninger" },
  "page.welcome.trader": { en: "Trader / Investor", no: "Handler / Investor" },
  "page.welcome.trader_subtitle": { en: "Market signals & event impact modeling", no: "Markedssignaler og hendelsesmodellering" },
  "page.welcome.analyst": { en: "Analyst", no: "Analytiker" },
  "page.welcome.analyst_subtitle": { en: "Deep intelligence & competitive research", no: "Dyp etterretning og konkurranseanalyse" },
  "page.welcome.skip_demo": { en: "Skip demo, go to Dashboard", no: "Hopp over demo, gå til dashbord" },
  "page.welcome.start_tour": { en: "Start Tour", no: "Start omvisning" },

  // ── Page: Billing ──
  "page.billing.title": { en: "Billing & Subscription", no: "Fakturering og abonnement" },
  "page.billing.subtitle": { en: "Manage your OpenClaw subscription and payment history", no: "Administrer ditt OpenClaw-abonnement og betalingshistorikk" },
  "page.billing.current_tier": { en: "Current Tier", no: "Gjeldende niwa" },
  "page.billing.monthly_price": { en: "Monthly Price", no: "Månedlig pris" },
  "page.billing.api_calls": { en: "API Calls", no: "API-kall" },
  "page.billing.status": { en: "Status", no: "Status" },
  "page.billing.upgrade": { en: "Upgrade", no: "Oppgrader" },
  "page.billing.cancel_subscription": { en: "Cancel Subscription", no: "Avbryt abonnement" },
  "page.billing.invoice_history": { en: "Invoice History", no: "Fakturahistorikk" },
  "page.billing.free_tier": { en: "Free", no: "Gratis" },
  "page.billing.refresh": { en: "Refresh", no: "Oppdater" },

  // ── Page: Webhooks Settings ──
  "page.webhooks.title": { en: "Webhook Integrations", no: "Webhook-integrasjoner" },
  "page.webhooks.subtitle": { en: "Receive FishIntel alerts in Slack, Teams, or any HTTP endpoint", no: "Motta FishIntel-varsler i Slack, Teams eller et HTTP-endepunkt" },
  "page.webhooks.add_webhook": { en: "Add Webhook", no: "Legg til webhook" },
  "page.webhooks.new_webhook": { en: "New Webhook", no: "Ny webhook" },
  "page.webhooks.name": { en: "Name", no: "Navn" },
  "page.webhooks.url": { en: "URL", no: "URL" },
  "page.webhooks.type": { en: "Type", no: "Type" },
  "page.webhooks.events": { en: "Events", no: "Hendelser" },
  "page.webhooks.test": { en: "Test", no: "Test" },
  "page.webhooks.active": { en: "Active", no: "Aktiv" },
  "page.webhooks.inactive": { en: "Inactive", no: "Inaktiv" },
  "page.webhooks.no_webhooks": { en: "No webhooks configured yet.", no: "Ingen webhooker konfigurert ennå." },
  "page.webhooks.url_required": { en: "URL is required", no: "URL er påkrevd" },
  "page.webhooks.select_event": { en: "Select at least one event", no: "Velg minst en hendelse" },
  "page.webhooks.last_triggered": { en: "Last triggered", no: "Sist utløst" },
  "page.webhooks.failure_count": { en: "Failures", no: "Feil" },

  // ── TopBar ──
  "topbar.select_role": { en: "Select role", no: "Velg rolle" },
  "topbar.farmer": { en: "Farmer", no: "Oppdretter" },
  "topbar.buyer": { en: "Buyer", no: "Kjøper" },
  "topbar.investor": { en: "Investor", no: "Investor" },
  "topbar.admin": { en: "Admin", no: "Admin" },

  // ══════════════════════════════════════════════════════════════════
  // PAGE CONTENT TRANSLATIONS — Session 28
  // Norwegian translations use industry-standard aquaculture terminology
  // from Fiskeridirektoratet, BarentsWatch, and Mattilsynet.
  // ══════════════════════════════════════════════════════════════════

  // ── Common page UI ──
  "common.loading": { en: "Loading...", no: "Laster..." },
  "common.no_data": { en: "No data available", no: "Ingen data tilgjengelig" },
  "common.error_loading": { en: "Failed to load data", no: "Kunne ikke laste data" },
  "common.last_updated": { en: "Last updated", no: "Sist oppdatert" },
  "common.data_source": { en: "Data source", no: "Datakilde" },
  "common.export_csv": { en: "Export CSV", no: "Eksporter CSV" },
  "common.export_excel": { en: "Export Excel", no: "Eksporter Excel" },
  "common.week": { en: "Week", no: "Uke" },
  "common.year": { en: "Year", no: "År" },
  "common.production_area": { en: "Production Area", no: "Produksjonsområde" },
  "common.pa": { en: "PA", no: "PO" },
  "common.company": { en: "Company", no: "Selskap" },
  "common.locality": { en: "Locality", no: "Lokalitet" },
  "common.trend": { en: "Trend", no: "Trend" },
  "common.confidence": { en: "Confidence", no: "Konfidens" },
  "common.view_details": { en: "View Details", no: "Vis detaljer" },
  "common.nok_per_kg": { en: "NOK/kg", no: "NOK/kg" },
  "common.tonnes": { en: "tonnes", no: "tonn" },
  "common.per_fish": { en: "per fish", no: "per fisk" },
  "common.select_locality": { en: "Select locality", no: "Velg lokalitet" },
  "common.search_locality": { en: "Search localities...", no: "Søk i lokaliteter..." },
  "common.all_areas": { en: "All areas", no: "Alle områder" },

  // ── Page: Dashboard ──
  "dashboard.title": { en: "Dashboard", no: "Dashbord" },
  "dashboard.overview": { en: "Platform Overview", no: "Plattformoversikt" },
  "dashboard.key_metrics": { en: "Key Metrics", no: "Nøkkeltall" },
  "dashboard.lice_avg": { en: "Avg Lice", no: "Gj.sn. lus" },
  "dashboard.spot_price": { en: "Spot Price", no: "Spotpris" },
  "dashboard.anomaly_score": { en: "Anomaly Score", no: "Anomaliscore" },
  "dashboard.feed_pressure": { en: "Feed Pressure", no: "Fôrprispress" },
  "dashboard.disease_outbreaks": { en: "Disease Outbreaks", no: "Sykdomsutbrudd" },
  "dashboard.supply_balance": { en: "Supply Balance", no: "Tilbudsbalanse" },
  "dashboard.nok_usd": { en: "NOK/USD", no: "NOK/USD" },
  "dashboard.live_intelligence": { en: "Live Intelligence", no: "Sanntidsetterretning" },
  "dashboard.regime_alerts": { en: "Regime Alerts", no: "Regimevarsler" },
  "dashboard.pairs_signals": { en: "Pairs Signals", no: "Parsignaler" },
  "dashboard.ais_vessels": { en: "AIS Vessels", no: "AIS-fartøy" },
  "dashboard.weekly_price": { en: "Weekly Price", no: "Ukentlig pris" },
  "dashboard.weekly_volume": { en: "Weekly Volume", no: "Ukentlig volum" },
  "dashboard.top_companies": { en: "Top Companies", no: "Toppselskaper" },
  "dashboard.production_stats": { en: "Production", no: "Produksjon" },
  "dashboard.customize": { en: "Customize Dashboard", no: "Tilpass dashbord" },
  "dashboard.hero_alert": { en: "Attention Required", no: "Krever oppmerksomhet" },

  // ── Page: Farmer Daily ──
  "farmer.title": { en: "Daily Check", no: "Daglig sjekk" },
  "farmer.subtitle": { en: "Your morning decision for each farm", no: "Din morgenbeslutning for hvert anlegg" },
  "farmer.action.treat_now": { en: "Treat Now", no: "Behandle nå" },
  "farmer.action.schedule": { en: "Schedule Treatment", no: "Planlegg behandling" },
  "farmer.action.monitor": { en: "Monitor", no: "Overvåk" },
  "farmer.action.no_action": { en: "No Action", no: "Ingen handling" },
  "farmer.lice_level": { en: "Lice Level", no: "Lusenivå" },
  "farmer.sea_temp": { en: "Sea Temperature", no: "Sjøtemperatur" },
  "farmer.adult_female_lice": { en: "Adult female lice", no: "Voksne hunnlus" },
  "farmer.regulatory_limit": { en: "Regulatory limit", no: "Lusegrense" },
  "farmer.treatment_cost": { en: "Treatment Cost", no: "Behandlingskostnad" },
  "farmer.cost_of_inaction": { en: "Cost of Inaction", no: "Kostnad ved utsettelse" },
  "farmer.roi": { en: "ROI", no: "Avkastning" },
  "farmer.recommended_method": { en: "Recommended Method", no: "Anbefalt metode" },
  "farmer.method.mechanical": { en: "Mechanical", no: "Mekanisk" },
  "farmer.method.thermal": { en: "Thermal", no: "Termisk" },
  "farmer.method.freshwater": { en: "Freshwater", no: "Ferskvann" },
  "farmer.method.medicinal": { en: "Medicinal", no: "Medisinsk" },
  "farmer.method.biological": { en: "Biological", no: "Biologisk" },
  "farmer.efficacy_title": { en: "Treatment Efficacy", no: "Behandlingseffektivitet" },
  "farmer.efficacy_subtitle": { en: "Crowdsourced data from Norwegian farms", no: "Innsamlede data fra norske oppdrettsanlegg" },
  "farmer.search_farms": { en: "Search farms...", no: "Søk i anlegg..." },
  "farmer.my_farms": { en: "My Farms", no: "Mine anlegg" },

  // ── Page: Disease Intelligence ──
  "disease.title": { en: "Disease Intelligence", no: "Sykdomsovervåkning" },
  "disease.active_outbreaks": { en: "Active Outbreaks", no: "Aktive utbrudd" },
  "disease.isa_cases": { en: "ISA Cases", no: "ILA-tilfeller" },
  "disease.pd_cases": { en: "PD Cases", no: "PD-tilfeller" },
  "disease.companies_affected": { en: "Companies Affected", no: "Berørte selskaper" },
  "disease.resistance_suspicions": { en: "Resistance Suspicions", no: "Mistanke om resistens" },
  "disease.global_alerts": { en: "Global Disease Alerts", no: "Globale sykdomsvarsler" },
  "disease.norway_detail": { en: "Norway Detail", no: "Norgeoversikt" },
  "disease.treatment_resistance": { en: "Treatment & Resistance", no: "Behandling og resistens" },
  "disease.company_exposure": { en: "Company Exposure", no: "Selskapseksponering" },
  "disease.source_mattilsynet": { en: "Source: Norwegian Food Safety Authority", no: "Kilde: Mattilsynet" },
  "disease.source_woah": { en: "Source: WOAH", no: "Kilde: WOAH" },

  // ── Page: Market Terminal ──
  "market.title": { en: "Market Terminal", no: "Markedsterminal" },
  "market.spot_price": { en: "Spot Price", no: "Spotpris" },
  "market.weekly_avg": { en: "Weekly Median", no: "Ukentlig median" },
  "market.price_history": { en: "Price History", no: "Prishistorikk" },
  "market.news_sentiment": { en: "News & Sentiment", no: "Nyheter og sentiment" },
  "market.harvest_intel": { en: "AIS Harvest Intelligence", no: "AIS-slakteetterretning" },
  "market.equity_prices": { en: "Equity Prices", no: "Aksjekurser" },
  "market.macro_indicators": { en: "Macro Indicators", no: "Makroindikatorer" },

  // ── Page: Trader / Investor ──
  "trader.title": { en: "Trader Intel", no: "Handelsinfo" },
  "trader.event_simulator": { en: "Event Impact Simulator", no: "Hendelsessimulator" },
  "trader.isa_outbreak": { en: "ISA Outbreak", no: "ILA-utbrudd" },
  "trader.traffic_light_change": { en: "Traffic Light Change", no: "Trafikklysendring" },
  "trader.feed_shock": { en: "Feed Price Shock", no: "Fôrprissjokk" },
  "trader.simulate": { en: "Simulate", no: "Simuler" },
  "trader.impact_results": { en: "Impact Results", no: "Konsekvensresultater" },
  "trader.biomass_loss": { en: "Biomass Loss", no: "Biomassetap" },
  "trader.revenue_impact": { en: "Revenue Impact", no: "Inntektspavirkning" },
  "trader.stock_move": { en: "Est. Stock Move", no: "Est. aksjeendring" },
  "trader.active_signals": { en: "Active Signals", no: "Aktive signaler" },
  "trader.saved_scenarios": { en: "Saved Scenarios", no: "Lagrede scenarier" },

  // ── Page: Signals ──
  "signals.title": { en: "Signals", no: "Signaler" },
  "signals.trading_signals": { en: "Trading Signals", no: "Handelssignaler" },
  "signals.early_warning": { en: "Early Warning System", no: "Tidlig varslingssystem" },
  "signals.anomaly_detection": { en: "Anomaly Detection", no: "Anomalideteksjon" },
  "signals.causal_drivers": { en: "Causal Drivers", no: "Årsaksdrivere" },
  "signals.pairs_trading": { en: "Pairs Trading", no: "Parhandel" },
  "signals.sentiment": { en: "Sentiment Signals", no: "Sentimentsignaler" },
  "signals.long": { en: "Long", no: "Lang" },
  "signals.short": { en: "Short", no: "Kort" },

  // ── Page: Leaders & ESG ──
  "leaders.title": { en: "Leaders & ESG", no: "Ledere og ESG" },
  "leaders.rank": { en: "Rank", no: "Rang" },
  "leaders.company_name": { en: "Company", no: "Selskap" },
  "leaders.lice_score": { en: "Lice Score", no: "Lusescore" },
  "leaders.esg_score": { en: "ESG Score", no: "ESG-score" },
  "leaders.production": { en: "Production", no: "Produksjon" },
  "leaders.verdict": { en: "Verdict", no: "Vurdering" },
  "leaders.outperformer": { en: "Outperformer", no: "Overprester" },
  "leaders.average": { en: "Average", no: "Gjennomsnitt" },
  "leaders.underperformer": { en: "Underperformer", no: "Underprester" },
  "leaders.disease": { en: "Disease", no: "Sykdom" },
  "leaders.clear": { en: "Clear", no: "Fri" },

  // ── Page: Competitiveness ──
  "competitiveness.title": { en: "Origin Competitiveness", no: "Opprinnelseskonkurranseevne" },
  "competitiveness.fx_adjusted": { en: "FX-adjusted cost comparison", no: "Valutajustert kostnadssammenligning" },
  "competitiveness.country": { en: "Country", no: "Land" },
  "competitiveness.cost_nok": { en: "Cost (NOK/kg)", no: "Kostnad (NOK/kg)" },
  "competitiveness.tariff": { en: "US Tariff", no: "US-toll" },
  "competitiveness.rank": { en: "Rank", no: "Rang" },
  "competitiveness.fx_rates": { en: "Exchange Rates", no: "Valutakurser" },
  "competitiveness.tariff_scenario": { en: "Tariff Scenario", no: "Tollscenario" },

  // ── Page: Supply Forecast ──
  "supply.title": { en: "Supply Forecast", no: "Tilbudsprognose" },
  "supply.smolt_to_harvest": { en: "Smolt-to-Harvest Pipeline", no: "Smolt-til-slakt" },
  "supply.monthly_supply": { en: "Monthly Supply", no: "Månedlig tilbud" },
  "supply.demand_balance": { en: "Demand Balance", no: "Etterspørselsbalanse" },
  "supply.cohorts": { en: "Active Cohorts", no: "Aktive kohorter" },
  "supply.surplus": { en: "Surplus", no: "Overskudd" },
  "supply.deficit": { en: "Deficit", no: "Underskudd" },
  "supply.balanced": { en: "Balanced", no: "Balansert" },
  "supply.harvest_weight": { en: "Harvest Weight", no: "Slaktevekt" },
  "supply.survival_rate": { en: "Survival Rate", no: "Overlevelsesrate" },
  "supply.price_path": { en: "2–20 Week Price Path", no: "Prisbane 2–20 uker" },
  "supply.spot_vs_seasonal": { en: "Spot vs seasonal", no: "Spot vs. sesong" },
  "supply.forecast_band": { en: "Empirical band", no: "Empirisk bånd" },
  "supply.backtest": { en: "Walk-forward backtest", no: "Walk-forward-backtest" },
  "supply.backtest_missing": { en: "Backtest artifact not generated in this environment (run scripts/backtest_supply_demand.py)", no: "Backtest-artefakt ikke generert i dette miljøet (kjør scripts/backtest_supply_demand.py)" },
  "supply.bands_fallback": { en: "Bands: in-sample history (too short for walk-forward calibration)", no: "Bånd: in-sample-historikk (for kort for walk-forward-kalibrering)" },
  "supply.smolt_model_tag": { en: "smolt pipeline model", no: "smolt-pipelinemodell" },

  // ── Page: Global Supply ──
  "global_supply.title": { en: "Global Supply", no: "Globalt tilbud" },
  "global_supply.production_2025": { en: "2025 Production", no: "2025-produksjon" },
  "global_supply.production_2026": { en: "2026 Estimate", no: "2026-estimat" },
  "global_supply.yoy_growth": { en: "YoY Growth", no: "Vekst år-over-år" },
  "global_supply.disruption": { en: "Disruption", no: "Forstyrrelse" },
  "global_supply.total_global": { en: "Total Global", no: "Totalt globalt" },

  // ── Page: Bio Risk Map ──
  "bio_risk.title": { en: "Biological Risk Map", no: "Biologisk risikokart" },
  "bio_risk.farm_layer": { en: "Farm Locations", no: "Anleggsplasseringer" },
  "bio_risk.disease_layer": { en: "Disease Status", no: "Sykdomsstatus" },
  "bio_risk.bloom_layer": { en: "Algal Bloom Risk", no: "Algeoppblomstringsrisiko" },
  "bio_risk.lice_layer": { en: "Lice Pressure", no: "Lusepress" },
  "bio_risk.all_countries": { en: "All Countries", no: "Alle land" },
  "bio_risk.week_offset": { en: "Week Offset", no: "Ukeforskyving" },

  // ── Page: ML Baselines / Foundation Model Arena ──
  "ml.title": { en: "Foundation Model Arena", no: "Grunnmodell-arena" },
  "ml.compare_models": { en: "Compare Models", no: "Sammenlign modeller" },
  "ml.select_series": { en: "Select Series", no: "Velg dataserie" },
  "ml.price_series": { en: "Salmon Price", no: "Laksepris" },
  "ml.lice_series": { en: "Lice Counts", no: "Lusetall" },
  "ml.temp_series": { en: "Temperature", no: "Temperatur" },
  "ml.supply_series": { en: "Supply Volume", no: "Tilbudsvolum" },
  "ml.forecast_horizon": { en: "Forecast Horizon", no: "Prognosehorisont" },
  "ml.weeks_ahead": { en: "weeks ahead", no: "uker frem" },
  "ml.model_chronos": { en: "Chronos-2 (120M)", no: "Chronos-2 (120M)" },
  "ml.model_timesfm": { en: "TimesFM 2.5 (200M)", no: "TimesFM 2.5 (200M)" },
  "ml.model_moirai": { en: "MOIRAI-2 (30M)", no: "MOIRAI-2 (30M)" },
  "ml.confidence_band": { en: "Confidence Band", no: "Konfidensintervall" },
  "ml.median_forecast": { en: "Median Forecast", no: "Medianprognose" },

  // ── Page: Climate Risk ──
  "climate.title": { en: "Climate Risk", no: "Klimarisiko" },
  "climate.heatwave_risk": { en: "Marine Heatwave Risk", no: "Marin hetbølgerisiko" },
  "climate.sst_anomaly": { en: "SST Anomaly", no: "Havtemperaturavvik" },
  "climate.bloom_risk": { en: "Bloom Risk", no: "Oppblomstringsrisiko" },
  "climate.lice_climate_risk": { en: "Lice Climate Risk", no: "Luseklimarisiko" },
  "climate.composite_risk": { en: "Composite Risk", no: "Samlet risiko" },
  "climate.projections": { en: "Climate Projections", no: "Klimaprojeksjoner" },

  // ── Page: Feed Cost ──
  "feed_cost.title": { en: "Production Costs", no: "Produksjonskostnader" },
  "feed_cost.composite_index": { en: "Composite Feed Cost Index", no: "Sammensatt fôrkostnadsindeks" },
  "feed_cost.total_cost": { en: "Total Production Cost", no: "Total produksjonskostnad" },
  "feed_cost.feed_cost": { en: "Feed Cost", no: "Fôrkostnad" },
  "feed_cost.margin": { en: "Margin", no: "Margin" },
  "feed_cost.fcr": { en: "Feed Conversion Ratio", no: "Fôrfaktor (FCR)" },
  "feed_cost.anchovy_watch": { en: "Peru Anchovy Watch", no: "Peru ansjosvakt" },
  "feed_cost.ingredient": { en: "Ingredient", no: "Ingrediens" },
  "feed_cost.fishmeal": { en: "Fishmeal", no: "Fiskemel" },
  "feed_cost.fish_oil": { en: "Fish Oil", no: "Fiskeolje" },
  "feed_cost.soy": { en: "Soybean", no: "Soya" },
  "feed_cost.rapeseed": { en: "Rapeseed", no: "Raps" },
  "feed_cost.wheat": { en: "Wheat", no: "Hvete" },

  // ── Page: Feed Supply Chain ──
  "feed_chain.title": { en: "Feed Supply Chain", no: "Fôrforsyningskjede" },
  "feed_chain.subtitle": { en: "Ingredient sourcing, EUDR compliance & cost scenarios", no: "Ingrediensinnkjøp, EUDR-samsvar og kostnadsscenarier" },
  "feed_chain.composition": { en: "Feed Composition", no: "Fôrsammensetning" },
  "feed_chain.eudr_status": { en: "EUDR Compliance", no: "EUDR-samsvar" },
  "feed_chain.cost_breakdown": { en: "Cost Breakdown", no: "Kostnadsfordeling" },
  "feed_chain.scenarios": { en: "Sourcing Scenarios", no: "Innkjøpsscenarier" },
  "feed_chain.supply_flow": { en: "Supply Chain Flow", no: "Forsyningskjedeflyt" },
  "feed_chain.current": { en: "Current Baseline", no: "Nåværende grunnlinje" },
  "feed_chain.soy_spike": { en: "Soy Price Spike", no: "Soyaprissjokk" },
  "feed_chain.insect_meal": { en: "Insect Meal Substitute", no: "Insektmel-erstatning" },
  "feed_chain.algae_oil": { en: "Algae Oil Substitute", no: "Algeolje-erstatning" },
  "feed_chain.compliant": { en: "EUDR Compliant", no: "EUDR-kompatibel" },
  "feed_chain.partial": { en: "Partial Compliance", no: "Delvis samsvar" },
  "feed_chain.non_compliant": { en: "Non-Compliant", no: "Ikke-kompatibel" },
  "feed_chain.risk_factors": { en: "Risk Factors", no: "Risikofaktorer" },
  "feed_chain.recommendation": { en: "Recommendation", no: "Anbefaling" },
  "feed_chain.total_cost": { en: "Feed Cost", no: "Fôrkostnad" },
  "feed_chain.carbon": { en: "Carbon Footprint", no: "Karbonfotavtrykk" },
  "feed_chain.soy_share": { en: "Soy Share", no: "Soyaandel" },
  "feed_chain.marine_share": { en: "Marine Share", no: "Marinandel" },
  "feed_chain.of_feed": { en: "of feed", no: "av fôr" },
  "feed_chain.deforestation_exposure": { en: "Deforestation exposure", no: "Avskogingseksponering" },

  // ── Page: Futures ──
  "futures.title": { en: "Salmon Futures", no: "Laksefutures" },
  "futures.forward_curve": { en: "Forward Curve", no: "Forwardkurve" },
  "futures.basis_analysis": { en: "Basis Analysis", no: "Basisanalyse" },
  "futures.term_structure": { en: "Term Structure", no: "Terminstruktur" },
  "futures.contango": { en: "Contango", no: "Contango" },
  "futures.backwardation": { en: "Backwardation", no: "Backwardation" },
  "futures.spot_vs_future": { en: "Spot vs Future", no: "Spot mot future" },
  "futures.synthetic_note": { en: "Synthetic forward curve based on seasonal patterns", no: "Syntetisk forwardkurve basert på sesongmønstre" },

  // ── Page: Traffic Light ──
  "traffic_light.title": { en: "Traffic Light System", no: "Trafikklyssystemet" },
  "traffic_light.current_status": { en: "Current PA Status", no: "Gjeldende PO-status" },
  "traffic_light.simulator": { en: "Traffic Light Simulator", no: "Trafikklyssimulator" },
  "traffic_light.green": { en: "Green (+6% MTB)", no: "Grønt (+6 % MTB)" },
  "traffic_light.yellow": { en: "Yellow (0% MTB)", no: "Gult (0 % MTB)" },
  "traffic_light.red": { en: "Red (-6% MTB)", no: "Rødt (-6 % MTB)" },
  "traffic_light.companies_affected": { en: "Companies Affected", no: "Berørte selskaper" },

  // ── Page: ASC Compliance ──
  "asc.title": { en: "ASC Compliance Dashboard", no: "ASC-samsvarsdashbord" },
  "asc.readiness_score": { en: "Readiness Score", no: "Klarhetsscore" },
  "asc.mandatory_date": { en: "Mandatory Date", no: "Obligatorisk dato" },
  "asc.days_remaining": { en: "Days Remaining", no: "Dager igjen" },
  "asc.checklist": { en: "Compliance Checklist", no: "Samsvarssjekkliste" },
  "asc.pass": { en: "Pass", no: "Bestått" },
  "asc.fail": { en: "Fail", no: "Ikke bestått" },
  "asc.partial": { en: "Partial", no: "Delvis" },

  // ── Page: Regulatory Reports ──
  "compliance.title": { en: "Regulatory Reports", no: "Regulatorisk rapportering" },
  "compliance.subtitle": { en: "Automated compliance report generation for Norwegian aquaculture", no: "Automatisert samsvarsrapportering for norsk akvakultur" },
  "compliance.deadlines": { en: "Upcoming Deadlines", no: "Kommende frister" },
  "compliance.generate_report": { en: "Generate Report", no: "Generer rapport" },
  "compliance.score": { en: "Compliance Score", no: "Samsvarsscore" },
  "compliance.weekly_lice": { en: "Weekly Lice Report", no: "Ukentlig luserapport" },
  "compliance.monthly_treatment": { en: "Monthly Treatment Summary", no: "Månedlig behandlingssammendrag" },
  "compliance.overdue": { en: "Overdue", no: "Forfalt" },
  "compliance.on_time": { en: "On-Time Rate", no: "Rettidig rapportering" },
  "compliance.report_generated": { en: "Report Generated", no: "Rapport generert" },
  "compliance.download": { en: "Download CSV", no: "Last ned CSV" },
  "compliance.no_deadlines": { en: "No upcoming deadlines in the next 30 days", no: "Ingen kommende frister de neste 30 dagene" },

  // ── Page: Efficacy Marketplace ──
  "efficacy.title": { en: "Treatment Efficacy Marketplace", no: "Behandlingseffektivitet" },
  "efficacy.benchmarks": { en: "Method Benchmarks", no: "Metodereferanser" },
  "efficacy.by_region": { en: "By Region", no: "Etter region" },
  "efficacy.by_season": { en: "By Season", no: "Etter sesong" },
  "efficacy.reduction_pct": { en: "Reduction %", no: "Reduksjon %" },
  "efficacy.sample_size": { en: "Sample Size", no: "Utvalgsstr." },
  "efficacy.contribute": { en: "Contribute your treatment data", no: "Bidra med dine behandlingsdata" },

  // ── Page: Fish Welfare ──
  "welfare.title": { en: "Fish Welfare Dashboard", no: "Fiskevelferd-dashbord" },
  "welfare.subtitle": { en: "Holistic welfare assessment based on SWIM framework", no: "Helhetlig velferdsvurdering basert på SWIM-rammeverket" },
  "welfare.score": { en: "Welfare Score", no: "Velferdspoeng" },
  "welfare.grade": { en: "Grade", no: "Karakter" },
  "welfare.predicted_mortality": { en: "Predicted 7-Day Mortality", no: "Forventet 7-dagers dødelighet" },
  "welfare.alert_reason": { en: "Alert", no: "Varsel" },
  "welfare.components": { en: "Component Breakdown", no: "Komponentoversikt" },
  "welfare.component.lice": { en: "Lice Burden", no: "Lusebelastning" },
  "welfare.component.thermal": { en: "Thermal Stress", no: "Termisk stress" },
  "welfare.component.mortality": { en: "Mortality Trend", no: "Dødelighetsutvikling" },
  "welfare.component.environment": { en: "Environment", no: "Miljø" },
  "welfare.component.treatment": { en: "Treatment Stress", no: "Behandlingsstress" },
  "welfare.select_farm": { en: "Select a farm to view welfare score", no: "Velg et anlegg for velferdspoeng" },
  "welfare.factors": { en: "Contributing Factors", no: "Medvirkende faktorer" },
  "welfare.search_placeholder": { en: "Search farms by name or locality number...", no: "Søk anlegg etter navn eller lokalitetsnummer..." },
  "nav.fish_welfare": { en: "Fish Welfare", no: "Fiskevelferd" },

  // ── Page: Portfolio ──
  "portfolio.title": { en: "My Farm Portfolio", no: "Min anleggsportefølje" },
  "portfolio.risk_overview": { en: "Risk Overview", no: "Risikooversikt" },
  "portfolio.farms_needing_treatment": { en: "Farms Needing Treatment", no: "Anlegg som trenger behandling" },
  "portfolio.avg_lice": { en: "Average Lice Level", no: "Gjennomsnittlig lusenivå" },
  "portfolio.risk_breakdown": { en: "Risk Breakdown", no: "Risikofordeling" },

  // ── Page: Admin ──
  "admin.title": { en: "Admin Dashboard", no: "Admin-dashbord" },
  "admin.platform_health": { en: "Platform Health", no: "Plattformhelse" },
  "admin.data_quality": { en: "Data Quality", no: "Datakvalitet" },
  "admin.cache_stats": { en: "Cache Statistics", no: "Hurtigbufferstatistikk" },
  "admin.audit_log": { en: "Audit Log", no: "Revisjonslogg" },
  "admin.export_data": { en: "Export Data", no: "Eksporter data" },

  // ── Page: Notifications ──
  "notifications.title": { en: "Notifications", no: "Varsler" },
  "notifications.unread": { en: "Unread", no: "Uleste" },
  "notifications.all": { en: "All", no: "Alle" },
  "notifications.alert_rules": { en: "Alert Rules", no: "Varslingsregler" },
  "notifications.create_rule": { en: "Create Rule", no: "Opprett regel" },
  "notifications.metric": { en: "Metric", no: "Metrikk" },
  "notifications.threshold": { en: "Threshold", no: "Terskel" },
  "notifications.operator": { en: "Operator", no: "Operator" },

  // ── Page: Morning Brief ──
  "brief.title": { en: "Morning Brief", no: "Morgenrapport" },
  "brief.market_mood": { en: "Market Mood", no: "Markedsstemning" },
  "brief.bullish": { en: "Bullish", no: "Positiv" },
  "brief.bearish": { en: "Bearish", no: "Negativ" },
  "brief.neutral": { en: "Neutral", no: "Nøytral" },
  "brief.key_risks": { en: "Key Risks", no: "Nøkkelrisikoer" },
  "brief.export_pdf": { en: "Export PDF", no: "Eksporter PDF" },

  // ── Page: Benchmark ──
  "benchmark.title": { en: "Peer Benchmark", no: "Sammenligning" },
  "benchmark.percentile": { en: "Percentile", no: "Persentil" },
  "benchmark.metric": { en: "Metric", no: "Metrikk" },
  "benchmark.industry_avg": { en: "Industry Average", no: "Bransjesnitt" },

  // ── Page: Harvest Optimizer ──
  "harvest.title": { en: "Harvest Optimizer", no: "Slakteoptimerer" },
  "harvest.optimal_week": { en: "Optimal Harvest Week", no: "Optimal slakteuke" },
  "harvest.expected_weight": { en: "Expected Weight", no: "Forventet vekt" },
  "harvest.revenue_estimate": { en: "Revenue Estimate", no: "Inntektsestimat" },

  // ── Page: Digital Twin ──
  "twin.title": { en: "Digital Twin", no: "Digital tvilling" },
  "twin.simulate": { en: "Run Simulation", no: "Kjør simulering" },
  "twin.weeks": { en: "Simulation Weeks", no: "Simuleringsperiode (uker)" },
  "twin.temp_delta": { en: "Temperature Change", no: "Temperaturendring" },

  // ── Page: Scenarios Lab ──
  "scenarios.title": { en: "Scenario Lab", no: "Scenariolab" },
  "scenarios.add_event": { en: "Add Event", no: "Legg til hendelse" },
  "scenarios.run_simulation": { en: "Run Simulation", no: "Kjør simulering" },
  "scenarios.compound_impact": { en: "Compound Impact", no: "Samlet effekt" },
  "scenarios.cascade_narrative": { en: "Cascade Narrative", no: "Kaskadefortelling" },

  // ── Page: Causal Engine ──
  "causal.title": { en: "Causal Engine", no: "Årsaksmotor" },
  "causal.granger_relationships": { en: "Granger Causality", no: "Granger-kausalitet" },
  "causal.lag_weeks": { en: "Lag (weeks)", no: "Forsinkelse (uker)" },
  "causal.correlation": { en: "Correlation", no: "Korrelasjon" },
  "causal.significant": { en: "Significant", no: "Signifikant" },

  // ── Page: Compare ──
  "compare.title": { en: "Company Comparison", no: "Selskapssammenligning" },
  "compare.select_companies": { en: "Select companies to compare", no: "Velg selskaper å sammenligne" },
  "compare.radar_chart": { en: "Radar Chart", no: "Radardiagram" },
  "compare.winner": { en: "Winner", no: "Vinner" },

  // ── Page: Canada ──
  "canada.title": { en: "Canada / British Columbia", no: "Canada / Britisk Columbia" },
  "canada.ban_countdown": { en: "BC Open Net-Pen Ban", no: "BC forbud mot åpne merder" },
  "canada.days_remaining": { en: "days remaining", no: "dager igjen" },
  "canada.bc_regions": { en: "BC Regional Lice", no: "BC regional lus" },
  "canada.dfo_source": { en: "Source: DFO Open Data", no: "Kilde: DFO åpne data" },

  // ── Country pages (generic) ──
  "country.production": { en: "Production", no: "Produksjon" },
  "country.farms": { en: "Farm Sites", no: "Oppdrettslokaliteter" },
  "country.disease_status": { en: "Disease Status", no: "Sykdomsstatus" },
  "country.sst": { en: "Sea Surface Temperature", no: "Havoverflatetemperatur" },
  "country.disease_free": { en: "Disease Free", no: "Sykdomsfri" },

  // ── Page: Lice Quota ──
  "lice_quota.title": { en: "Lice Emission Quotas", no: "Luseemisjonskvote" },
  "lice_quota.national_overview": { en: "National Overview", no: "Nasjonal oversikt" },
  "lice_quota.pa_utilization": { en: "PA Quota Utilization", no: "PO-kvoteutnyttelse" },
  "lice_quota.projected": { en: "Projected (regulation pending)", no: "Projisert (regulering pågår)" },

  // ── Page: Traceability ──
  "traceability.title": { en: "EU Traceability", no: "EU-sporbarhet" },
  "traceability.certificates": { en: "Catch Certificates", no: "Fangstattester" },
  "traceability.lot_tracking": { en: "Lot Tracking", no: "Partisporing" },
  "traceability.iuu_risk": { en: "IUU Risk Assessment", no: "IUU-risikovurdering" },
  "traceability.eudr_status": { en: "EUDR Compliance", no: "EUDR-samsvar" },
  "traceability.eudr_countdown_title": { en: "EUDR Compliance Countdown", no: "EUDR-nedtelling" },

  // ── Error messages (user-facing) ──
  "error.data_unavailable": { en: "Data temporarily unavailable", no: "Data midlertidig utilgjengelig" },
  "error.api_error": { en: "Service error — please try again", no: "Tjenestefeil — vennligst prøv igjen" },
  "error.network": { en: "Network error — check your connection", no: "Nettverksfeil — sjekk tilkoblingen" },
  "error.timeout": { en: "Request timed out", no: "Forespørselen ble tidsavbrutt" },
  "error.unauthorized": { en: "Unauthorized — please log in", no: "Ikke autorisert — vennligst logg inn" },
  "error.boundary_title": { en: "Something went wrong", no: "Noe gikk galt" },
  "error.boundary_message": { en: "This section encountered an error. Try refreshing the page.", no: "Denne seksjonen møtte en feil. Prøv å oppdatere siden." },
  "error.segment_title": { en: "This section encountered an error", no: "Denne seksjonen fikk en feil" },
  "error.segment_message": { en: "Your other data is unaffected. Try again or refresh the page.", no: "Dine andre data er upåvirket. Prøv igjen eller oppdater siden." },
  "error.try_again": { en: "Try Again", no: "Prøv igjen" },
  "loading.skeleton": { en: "Loading data...", no: "Laster data..." },

  // ── Domain terms ──
  "domain.lice_limit": { en: "Lice limit", no: "Lusegrense" },
  "domain.max_allowed_biomass": { en: "Max Allowed Biomass (MTB)", no: "Maksimalt tillatt biomasse (MTB)" },
  "domain.production_cost": { en: "Production cost", no: "Produksjonskostnad" },
  "domain.harvest": { en: "Harvest", no: "Slakting" },
  "domain.smolt": { en: "Smolt", no: "Smolt" },
  "domain.welfare": { en: "Welfare", no: "Fiskevelferd" },
  "domain.escapees": { en: "Escapees", no: "Rømming" },
  "domain.stocking_density": { en: "Stocking density", no: "Tetthet" },

  // ── Common UI actions ──
  "common.print_pdf": { en: "Export PDF", no: "Eksporter PDF" },
  "common.refresh": { en: "Refresh", no: "Oppdater" },
  "common.close": { en: "Close", no: "Lukk" },
  "common.confirm": { en: "Confirm", no: "Bekreft" },
  "common.back": { en: "Back", no: "Tilbake" },
  "common.next": { en: "Next", no: "Neste" },

  // ── Freshness indicator ──
  "freshness.live": { en: "Live data", no: "Sanntidsdata" },
  "freshness.recent": { en: "Recent data", no: "Nylige data" },
  "freshness.stale": { en: "Stale data", no: "Utdatert data" },
  "freshness.simulated": { en: "Simulated data", no: "Simulerte data" },
};

/**
 * Map of sidebar label text -> i18n key for quick lookup.
 */
export const NAV_LABEL_KEYS: Record<string, string> = {
  "Dashboard": "nav.dashboard",
  "Daily Check": "nav.daily_check",
  "Morning Brief": "nav.morning_brief",
  "Notifications": "nav.notifications",
  "Leaders & ESG": "nav.leaders_esg",
  "Peer Benchmark": "nav.peer_benchmark",
  "Bio Risk Map": "nav.bio_risk_map",
  "Disease Intel": "nav.disease_intel",
  "Climate Risk": "nav.climate_risk",
  "Traffic Light": "nav.traffic_light",
  "Lice Quotas": "nav.lice_quotas",
  "Compare": "nav.compare",
  "Production Costs": "nav.production_costs",
  "Feed Supply Chain": "nav.feed_supply_chain",
  "Global Supply": "nav.global_supply",
  "Competitiveness": "nav.competitiveness",
  "Supply Forecast": "nav.supply_forecast",
  "Investor Intel": "nav.investor_intel",
  "Trader Intel": "nav.trader_intel",
  "Salmon Futures": "nav.salmon_futures",
  "Market Terminal": "nav.market_terminal",
  "Price & Predictions": "nav.price_predictions",
  "Signals": "nav.signals",
  "Canada / BC": "nav.canada_bc",
  "Scotland": "nav.scotland",
  "Faroe Islands": "nav.faroe_islands",
  "Iceland": "nav.iceland",
  "China Demand": "nav.china_demand",
  "My Portfolio": "nav.my_portfolio",
  "Farm Advisory": "nav.farm_advisory",
  "Treatment Optimizer": "nav.treatment_optimizer",
  "Efficacy Market": "nav.efficacy_market",
  "Fish Welfare": "nav.fish_welfare",
  "Harvest Optimizer": "nav.harvest_optimizer",
  "Digital Twin": "nav.digital_twin",
  "Satellite Intel": "nav.satellite_intel",
  "Command Centre": "nav.command_centre",
  "Scenario Lab": "nav.scenario_lab",
  "Scenarios": "nav.scenarios",
  "Causal Engine": "nav.causal_engine",
  "AI Chat": "nav.ai_chat",
  "ML Baselines": "nav.ml_baselines",
  "RAS Tracker": "nav.ras_tracker",
  "ASC Compliance": "nav.asc_compliance",
  "EU Traceability": "nav.eu_traceability",
  "Contract Risk": "nav.contract_risk",
  "Insurance": "nav.insurance",
  "Compliance": "nav.compliance_page",
  "Admin": "nav.admin",
  "API Docs": "nav.api_docs",
  "Changelog": "nav.changelog",
  "Billing": "nav.billing",
  "Privacy": "nav.privacy",
  "Settings": "nav.settings",
  "Webhooks": "nav.webhooks",
};

/**
 * Map of sidebar section header text -> i18n key.
 */
export const SECTION_KEYS: Record<string, string> = {
  "Intelligence": "nav.intelligence",
  "Markets": "nav.markets",
  "Regions": "nav.regions",
  "Operations": "nav.operations",
  "Advanced": "nav.advanced",
  "Compliance": "nav.compliance",
  "System": "nav.system",
};

function getInitialLocale(): Locale {
  if (typeof window === "undefined") return "en";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "en" || stored === "no") return stored;
  return "en";
}

/**
 * Translation hook. Reads locale from localStorage (key: oc_locale, default: en).
 * Returns { t, locale, setLocale }.
 * t() falls back to English if key is not found in Norwegian.
 */
export function useTranslation() {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    setLocaleState(getInitialLocale());

    // Sync locale across all components when ANY component changes it.
    // Uses both 'storage' event (cross-tab) and custom event (same-tab).
    const handleStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY && (e.newValue === "en" || e.newValue === "no")) {
        setLocaleState(e.newValue);
      }
    };
    const handleCustom = () => {
      const v = localStorage.getItem(STORAGE_KEY);
      if (v === "en" || v === "no") setLocaleState(v);
    };
    window.addEventListener("storage", handleStorage);
    window.addEventListener("locale-changed", handleCustom);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("locale-changed", handleCustom);
    };
  }, []);

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    localStorage.setItem(STORAGE_KEY, newLocale);
    // Dispatch custom event so same-tab components re-render
    window.dispatchEvent(new Event("locale-changed"));
  }, []);

  const t = useCallback(
    (key: string): string => {
      const entry = translations[key];
      if (!entry) return key; // fallback to key itself
      return entry[locale] ?? entry.en ?? key;
    },
    [locale]
  );

  return { t, locale, setLocale } as const;
}

// Formatting utilities are defined at the top of this file (lines 8-25).
