# Design partners — running 5–8 paid 90-day pilots

The pilot infrastructure exists to be *used immediately*, not to be admired. This
is the runbook.

## What a pilot is

A **time-boxed grant of a canonical plan** (`core/entitlements.py`) to a real user,
plus the success metrics the pilot will be judged on and the data-reciprocity
terms. It is deliberately **not** a new tier — the plan table stays singular
(AGENTS.md rule 8) — and the grant goes through
`core/billing/entitlement_sync.activate()`, so a pilot is a real, auditable,
revocable entitlement rather than a checkbox in a CRM.

Target cohort: **3 desks, 2 processors, 2 producers (NO/CL), 1 insurer.**

## Runbook (admin only, `Depends(require_admin)`)

```bash
# 1) create the partner (pilot not yet granted)
POST /api/admin/partners
{ "company": "Nordlaks AS", "contact_email": "ops@nordlaks.no", "icp": "producer",
  "sector": "Salmon farming", "country": "NO", "plan_granted": "enterprise",
  "user_id": 1234, "is_paid": true, "monthly_price_nok": 14900 }

# 2) record the reciprocity terms BEFORE onboarding (so data-sharing is agreed)
POST /api/admin/partners/{id}/reciprocity
{ "shares": ["lice_counts_weekly","harvest_plan"], "cadence": "weekly",
  "agreement_ref": "DPA-2026-014" }

# 3) onboard — starts the 90-day clock and grants the entitlement
POST /api/admin/partners/{id}/onboard   { "days": 90 }

# 4) record success metrics as they happen
POST /api/admin/partners/{id}/metrics
{ "name": "forecast_adoption", "value": 6, "target": 5, "unit": "users" }

# 5) scorecard + funnel
GET /api/admin/partners          # all partners, by_status, by_icp
GET /api/admin/partners/{id}     # metric history + allowed status transitions

# 6) end the pilot
POST /api/admin/partners/{id}/status  { "status": "converted", "note": "signed annual" }
```

## Status machine (enforced — illegal transitions 409)

```
prospect ──► onboarded ──► active ──► converted   (terminal)
    │            │            │
    └────────────┴────────────┴──────► churned ──► onboarded (can re-onboard)
```

## Success metrics that actually decide the conversion

Record these for every pilot; a pilot that cannot show them does not convert.

| ICP | Metric | Example target |
|---|---|---|
| Desk | Forecast adoption / decisions informed | ≥ 5 decisions/week |
| Desk | Time saved per price review | ≥ 30 min/day |
| Processor | Contract-risk flags actioned | ≥ 3 per quarter |
| Producer | Lice treatment decisions changed (the original instrument, AI-LPI v1.0, is withdrawn by WS-19; the owner names its replacement) | ≥ 2 per cycle |
| Producer | Avoided treatment cost (NOK) | ≥ 250,000 |
| Insurer | Trigger-feed latency / attestation accepted | ≥ 1 accepted portfolio |

## Rules that keep pilots honest

1. **A pilot is a grant, not a demo.** It uses the real entitlement path, so what
   the partner sees is what a paying customer gets — including the
   `provenance`/`is_live` disclosures on every number.
2. **Pilot pricing is real.** `is_paid: true` and `monthly_price_nok` must be set
   for a design partner; unpaid evaluation is the free Insight plan, not a pilot.
3. **Data reciprocity is recorded before onboarding**, with the dataset names the
   partner supplies and the agreement reference — that is what turns producer data
   into a moat.
4. **Metrics are recorded as they happen**, not reconstructed at the end; the
   scorecard's `achieved` flag is computed from the latest observation against the
   latest target.

## Tables

`design_partners` (company, ICP, plan granted, window, status, reciprocity) and
`partner_metrics` (name, value, target, unit, note, recorded_at) — Alembic 018.
