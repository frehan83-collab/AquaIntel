# Security & architecture one-pager (enterprise procurement)

**Purpose:** answer the first 10 security questions before a call, and be honest
about what is not yet in place.

## What AquaIntel is

A salmon-aquaculture intelligence platform: FastAPI backend (~330 API operations,
~75 engines), Next.js frontend, PostgreSQL/TimescaleDB, 12 background agents for
ingest/forecast/publication, and a published-artifact accuracy system.

## Data handling

| Topic | Position |
|---|---|
| Hosting | EU/EEA preferred; PostgreSQL + TimescaleDB; no third-country transfer without SCCs |
| Data at rest | Database-level encryption (provider-managed) + secrets in env/secret manager — **not** in the repo |
| Data in transit | TLS everywhere; API served behind a reverse proxy with HSTS |
| Secrets | `FISHINTEL_JWT_SECRET` (≥32 chars enforced in production), Stripe keys via env; production refuses to boot with a weak/missing JWT secret |
| Passwords / API keys | Passwords hashed; API keys stored as **bcrypt hashes only** (prefix kept for identification) |
| Audit | `audit_log` for auth, admin and billing-adjacent actions |

## Tenancy & access control

| Topic | Position |
|---|---|
| Auth | JWT bearer tokens; 4-tier access with one canonical entitlement table (`core/entitlements.py`) |
| Admin | `User.role == "admin"` or an email in `FISHINTEL_ADMIN_EMAILS`; registration cannot self-grant admin |
| Ownership / IDOR | User-scoped resources are checked against the **token** user id, never a body-supplied `user_id` |
| Paywall | Premium outputs return 402 with an actionable upgrade payload for accounts whose plan does not include them |
| Quotas | Per-plan daily allowance enforced per authenticated account (429 + `Retry-After`) |
| Admin surfaces | `/api/admin/*`, `/api/cache/*` are `require_admin` |

## Supply-chain / outbound safety

- Outbound webhooks: URLs validated by a **DNS-resolving SSRF guard** at creation
  *and* at every dispatch.
- No user-supplied code execution; no shell interpolation of request data.

## Data provenance (the differentiator)

Every engine response carries `data_provenance` (`is_live`, `source`, `confidence`,
`fallback_reason`). A model fallback is **never** presented as live data. Accuracy
figures appear only when a versioned artifact produced them
(`/api/accuracy/method`). Per-source freshness, including synthetic-data flags, is
public at `/api/data-freshness`.

## What is NOT in place yet (stated plainly)

| Gap | Status |
|---|---|
| SSO (SAML/OIDC) | Not implemented — on the enterprise-engineer roadmap |
| SOC 2 Type I/II | Not started — DPA/GDPR scaffold and audit log exist as the base |
| Penetration test | Not performed |
| HA/failover | Single-region compose topology; no multi-AZ story yet |
| Per-tenant data isolation | Row-level tenant scoping is being extended |
| SOC 2-aligned security annex | DPA scaffold drafted, needs counsel |

We would rather lose a deal on an honest gap list than win it on a claim we cannot
evidence. The same rule that stops us inventing a MAPE stops us inventing a
certification.
