# Entitlements — single source of truth

**Status:** canonical since the commercial-hardening workstream, commit
"Kill the tier conflict". `core/entitlements.py` is the ONLY place a price, a
quota, a feature or the paywall boundary is defined.

## Why this exists

There used to be **two divergent tier tables**:

| Module | Tiers | Quota field | Enforced? |
|---|---|---|---|
| `core/auth.py` | 4 (free, professional, enterprise, investor) | `api_calls_per_day` | **yes** — the middleware read it |
| `core/valuechain/subscription.py` | 5 (+ intelligence) | `api_calls_limit` (monthly) | **no** |

`/api/tiers` imported **both** and returned a merged payload, so the API
contradicted itself in public. `intelligence` existed only in the second table and
therefore silently fell back to the **free** quota (100/day) for a plan priced at
NOK 39,900/month. `CHANGELOG.md` had already documented that the monthly figure
was "NOT what is enforced" — the honesty layer was papering over a product defect.

## The model

`PLANS` (7 plans) → `core/entitlements.py`:

| Key | Name | NOK/mo | API calls/day | Premium outputs | Audience |
|---|---|---|---|---|---|
| `free` | Insight | 0 | 100 | no | Analysts, journalists, evaluation |
| `operator` | Operator | 4,900 | 5,000 | no | Farm ops, lice/quota managers |
| `professional` | Desk | 2,990 | 20,000 | **yes** | Trading desks, buyers, analysts |
| `enterprise` | Enterprise | 14,900 | 50,000 | **yes** | Integrated producers |
| `investor` | Investor | 24,900 | 100,000 | **yes** | Investors and funds |
| `intelligence` | Intelligence | 39,900 | 100,000 | **yes** | AI-first customers |
| `data` | Data & Assurance | licensed (EUR 25k–150k/yr) | 250,000 | **yes** | Insurers, banks, assurance |

Rules:

1. **Per-day is the enforced unit.** The monthly figure is *derived*
   (`api_calls_per_day × 30`, or `-1` for unlimited) so the displayed and enforced
   numbers cannot diverge.
2. **Backward-compatible keys.** Issued JWTs and Stripe subscription metadata
   carry `free/professional/enterprise/investor/intelligence`, so those keys stay.
   `operator` and `data` are additive. Legacy aliases resolve through
   `normalize_plan()` (`premium|pro|desk|pilot → professional`, `growth|farm →
   operator`, `basic|starter|trial → free`, `licence|license|datapartner → data`,
   `market → enterprise`, `institutional → investor`); unknown strings fall back
   to `free`.
3. **One paywall policy.** `route_allowed(tier, path)`:
   - anonymous (`None`) → **always allowed** (public browsing is the funnel);
   - `NEVER_GATED` (auth/billing/health/tiers/entitlements/disclaimer) → allowed;
   - `PREMIUM_PREFIXES` (the curated crown-jewel outputs) → require a
     premium-capable plan;
   - everything else → allowed for any plan.
4. **One upgrade payload.** `upgrade_hint()` produces the same shape for 402
   (missing entitlement) and 429 (quota exhausted): `current_plan`,
   `suggested_plan`, `upgrade_url`, `plans_url`, plus a `tier` alias for older
   clients.

## Endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/entitlements/plans` | public | Pricing model, hierarchy, premium prefixes |
| `GET /api/entitlements/me` | optional | The caller's plan, quota, usage, upgrade path |
| `GET /api/entitlements/check?path=` | optional | Whether a path is allowed (UI affordances) |
| `GET /api/tiers`, `GET /api/auth/tiers` | public | Compatibility surfaces (now agree) |

## Enforcement

`core/tier_quota.py::TierQuotaMiddleware` — two layers with **independent
kill-switches** (a suite-wide `FISHINTEL_ENFORCE_QUOTAS=0` must not silently
disable the paywall; that trap was found by `tests/test_entitlements.py`):

| Layer | Switch | Response |
|---|---|---|
| Premium route gating (authenticated only) | `FISHINTEL_ENFORCE_ROUTE_GATING=0` | 402 + `upgrade_hint` |
| Daily quota (authenticated only) | `FISHINTEL_ENFORCE_QUOTAS=0` | 429 + `upgrade_hint` |

Anonymous traffic is never gated; `/api/auth/*`, `/api/health`, `/api/billing/*`
are exempt from both.

## Migration

`alembic/versions/016_canonical_plan_keys.py` normalises legacy tier strings in
`users.tier`, `subscriptions.tier`, `api_keys.tier` and `performance_fees.tier`
to canonical keys (aliases mapped, unknowns → `free`). Without it, a row holding
`"premium"` would be treated as unknown and silently served the free quota.

## Known limitations / next steps

- **Counters are in-process** per UTC day (per worker), not a durable ledger.
  Required next: a shared/durable usage ledger with Stripe metered invoicing
  (Step 2 of the hardening plan).
- **Prices are fallback defaults.** The pricing page and Stripe products are the
  commercial source; `price_nok_month` here is what the catalog falls back to when
  Stripe is unreachable/unconfigured.
- **Seats/sites are declared but not yet enforced** (multi-tenancy workstream).
- Tier *allow-lists* (`_PLAN_ROUTE_ALLOWLIST`) are exposed for UI/feature gating
  and future enforcement; the enforced boundary today is `PREMIUM_PREFIXES`.

## Verification

`tests/test_entitlements.py` proves: projections agree on price and quota; the
monthly figure is derived; `/api/tiers` and `/api/auth/tiers` agree;
`intelligence` no longer falls back to free; alias resolution; the paywall policy
(free blocked from every premium prefix, paid plans allowed, anonymous open,
never-gated open); 402 and 429 payloads; kill-switch behaviour.
