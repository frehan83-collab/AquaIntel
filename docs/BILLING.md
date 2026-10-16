# Billing & the money path

**One catalog, one entitlement write, one place to change a price.**

## The chain

```
/api/billing/catalog            core/billing/stripe_catalog.py   (canonical plans + price ids)
        │
        ▼
POST /api/billing/create-checkout-session?plan=<key>
        │                       validates the plan against core/entitlements
        ▼
Stripe Checkout  ──or──  mock URL (when STRIPE_SECRET_KEY is unset)
        │
        ▼
POST /api/billing/webhook       (real, signature-verified)   ─┐
POST /api/billing/webhook/mock  (dev/CI only)                ─┴─► core/billing/entitlement_sync.py
        │
        ▼
User.tier + Subscription row      →  TierQuotaMiddleware sees the new plan
        │
        ▼
premium route: 402 → 200
```

Every step is exercised end to end by `tests/test_billing_money_path.py`, which
needs **no Stripe credentials** — including the final assertion that a blocked
premium request succeeds after payment.

## Env vars

| Var | Required | Purpose |
|---|---|---|
| `STRIPE_SECRET_KEY` | for live billing | Without it everything runs in mock mode (`"mock": true` on every catalog entry) |
| `STRIPE_WEBHOOK_SECRET` | for live billing | Signature verification on `POST /api/billing/webhook` |
| `STRIPE_SUCCESS_URL` / `STRIPE_CANCEL_URL` | for live billing | Checkout redirects |
| `FISHINTEL_ENV` | — | `production` **disables** the mock webhook |
| `FISHINTEL_MOCK_BILLING_TOKEN` | recommended in staging | When set, `/webhook/mock` requires it in `X-Mock-Billing-Token` |

## Rules (why it is built this way)

1. **Prices come from `core/entitlements.py`.** `stripe_catalog.ensure_catalog()`
   creates/finds Stripe Products and Prices idempotently (by metadata, then by
   product + currency + amount), so re-running it never duplicates the catalog.
2. **The plan key is resolved server-side.** On webhook receipt the plan comes
   from the **price id** (authoritative) and only then from object metadata — never
   from anything the client sent. Legacy objects created before the rename still
   resolve: both `aquaintel_plan` and `openclaw_tier` are read, and both are
   written on new objects.
3. **One entitlement write.** `core/billing/entitlement_sync.activate()` /
   `revoke()` are called by the real webhook and the mock path alike, so a paid
   plan cannot land differently depending on which door the event came through.
   `activate()` also mirrors the price into `Subscription.monthly_price_nok` and
   the derived monthly API allowance.
4. **Mock mode is explicit, never silent.** Unconfigured deployments return
   `"mock": true` and `price_mock_<plan>` ids; the pricing page displays a banner
   rather than pretending these are live prices. This is the honesty rule applied
   to commerce.

## Endpoints

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /api/billing/catalog` | public | Plans, prices, `configured`, licensed tier |
| `POST /api/billing/create-checkout-session?plan=` | user | 400 for non-self-serve plans (e.g. `data`) |
| `POST /api/billing/webhook` | none (Stripe) | Signature-verified |
| `POST /api/billing/webhook/mock` | none, non-prod only | Simulates activation/cancellation |
| `GET /api/billing/subscription-status` | user | Local DB view of the subscription |
| `POST /api/billing/cancel-subscription` | user | Cancel at period end |
| `GET /api/billing/invoice-history` | user | Stripe invoices (empty in mock mode) |

## Remaining work (honest)

- **No durable usage ledger.** Quota counters are per-worker, per-UTC-day
  (in-process). Metered/overage invoicing needs a shared store first.
- **Seats/sites are declared, not enforced.**
- **`/api/billing/webhook/mock` must be blocked at the edge in production** — it
  refuses when `FISHINTEL_ENV=production`, but a misconfigured deploy would be
  exposed; put it behind the admin network policy anyway.
- **No dunning flow** — `invoice.payment_failed` is logged only.
