# AquaIntel Demo Guide — the 3-minute golden path

> **Audience:** farm operators, processors/buyers, insurers and investors, regulators.
> **Setup:** `FISHINTEL_DEMO_MODE=true python main.py` + `cd frontend && npm run dev`
> **Read first:** `docs/COMMERCIAL_TRIM.md` (why these four surfaces and not fifty-six) and
> `docs/ADVICE_BOUNDARY.md` (what we may not say).

Demo mode seeds **synthetic** rows. The product labels them (`synthetic_only`, `demo_seed`,
`degraded` provenance), and the demo script must say so out loud. The strongest thing about this
platform in a room is that every number can be traced; the weakest thing you can do is claim
"live" while demo mode is on.

---

## Pre-demo checklist

- [ ] Backend on `:8000` (`python main.py`), frontend on `:3000`
- [ ] `curl localhost:8000/api/data-freshness` — know which sources are fresh, stale, dead,
      unknown *before* you are asked
- [ ] `curl localhost:8000/api/accuracy` — every accuracy figure you may quote lives here
- [ ] Dark mode, full screen (F11)
- [ ] Dashboard KPIs show numbers, not spinners

---

## Act 1 — Someone cannot see this from their own cages (45 s)

**Page: Dashboard** (`/`)

> "A farmer knows their own cages. They do not know the neighbouring fjord, the national price
> formation, or what an auditor will ask for next quarter. This page is the overview: the spot,
> the weekly export volume, and lice against the 0.5 regulatory line — each tagged with where it
> came from."

Point to:
- The lice trend and the 0.5 threshold (BarentsWatch, NLOD 2.0 licence, dated)
- SSB weekly volume (table 03024)
- The provenance badge on each card: green = live, amber = degraded, grey = synthetic

---

## Act 2 — Evidence an auditor accepts (60 s)

**Navigate: `/asc-compliance` → `/regulatory-reports` → `/traceability`**

> "This is the part a farm is *obliged* to produce and would rather buy: ASC readiness,
> the regulatory pack, and EU traceability, with the record of what was submitted, when, and
> on what evidence."

Point to:
- Treatment records with lineage (each row says whether the source is verified)
- The traffic-light decision (Mattilsynet/Fiskeridirektoratet, dated capacity cuts, § 8 limits)
- What the pack refuses to do: it does not invent a missing measurement, it says which is missing

**Honest line to use:** "If a number is not verified, the document says so. That is the feature."

---

## Act 3 — Early warning across a boundary (45 s)

**Navigate: `/bio-risk` → `/traffic-light` → `/satellite`**

> "The risk that closes a site usually arrives from the next fjord, not from your own sensors.
> Disease cases by area, bloom risk from satellite chlorophyll, and lice pressure by production
> area — with the scene date attached where we have one."

Point to:
- The dated decision and licence limits
- Satellite: "NO VERIFIED SCENE" is a legitimate state, not a bug — say so before they ask
- Bloom: the trend and its age

---

## Act 4 — Documents that leave the platform (30 s)

**Navigate: `/chat` → deep-analysis panel**

> "A buyer, a board or a bank does not want a dashboard, they want something they can forward.
> The workbench renders a margin dossier, an origin landed-cost sheet or a lice review, cites its
> facts, checks every digit against them, and withholds the document if a number cannot be
> supported. A withheld run costs no credit."

Point to:
- The receipt (facts, dates, sources)
- The credit balance and the price per run
- `/pricing` — the plan ladder, generated from the same entitlement table the API enforces

---

## Backup paths

| Question | Where to go |
|---|---|
| "How does this help with regulations?" | `/traffic-light` → `/asc-compliance` → `/regulatory-reports` |
| "What about disease outbreaks?" | `/disease` → `/bio-risk` |
| "Can you predict prices?" | `/price-outlook` (2–20 week path, scenario bands) → `/futures` — model output, labelled |
| "Why is my cost where it is?" | `/feed-cost` → `/competitiveness` (origin landed cost, duty basis) |
| "How does the AI work?" | `/chat` (grounded, cites facts) → `/accuracy` (the honest number) |
| "Do you cover our country?" | `/global-supply` → `/compare` → `/competitiveness` |
| "Who do you compare us to?" | `/leaders` (reported volumes, scope stated; `null` where unregistered) |

---

## Say this, never that

| Never say | Say instead |
|---|---|
| "This is live data" while demo mode is on | "This is a seeded demo; in production each card carries its source and date" |
| Any accuracy figure you have not read on `/accuracy` | "The validated figure is on the Accuracy & Method page: <the number it shows>" |
| "We predict share prices" / buy or sell a listed company | Withdrawn (WS-20). Market context only; `/api/legal/advice-boundary` states the line |
| "Real-time" for a source with no timestamp today | "Daily/weekly" and the date, or `unknown` |
| "AI model accuracy" when the model fell back | "Seasonal-naive fallback; `is_live: false` — the page shows it" |
| "We cover 7 countries in depth" | Depth is Norway; the others are aggregated in `/global-supply` |

---

## Numbers you may quote (measured, 2026-10-21)

| Metric | Value | Source |
|---|---|---|
| API surface | 362 operations across 354 paths | `docs/openapi.frozen.json` |
| Frontend pages | 46 | `frontend/src/app` |
| DB migrations | 24 (head 024) | `alembic/versions` |
| Foundation models | 3, each with an honest fallback | `/api/accuracy` reports which loaded |
| Lice data licence | BarentsWatch, NLOD 2.0 | `core/legal/data_licenses.py` |

For anything else — farm counts, company counts, source counts — read it from the live endpoint in
front of the customer (`/api/data-freshness`, `/api/leaders`, `/api/legal/data-licenses`) rather
than quoting a slide.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| Pages show spinners | Backend not running (`python main.py`) |
| No lice rows | Demo mode seeds them; check `FISHINTEL_DEMO_MODE=true` |
| A card says "no verified scene" / `unknown` | That is the product being honest — use it as the story |
| Charts blank | Refresh; check the browser console |
| First load slow | Caches warm on first load; the second is fast |
