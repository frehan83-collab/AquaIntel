# Role: Enterprise & Security Engineer (SSO + SOC 2 path)

**Type:** full-time, remote-friendly
**Reports to:** founder (technical)
**Compensation:** senior base + options

## Why this role exists

Enterprise deals stall on two things: **identity** and **evidence**. Single sign-on
(SAML/OIDC) is not implemented, SOC 2 has not started, and the honest gaps are
listed in `docs/GTM_SECURITY_ONE_PAGER.md`. This role closes them so the
Enterprise/Desk plans can be sold to larger producers, processors, banks and
insurers.

## What you will own

1. **SSO / enterprise identity** — SAML 2.0 and OIDC for the web app and API, with
   SCIM-style provisioning, group→plan mapping, and an auditable auth trail.
   Integration must respect the existing single entitlement source
   (`core/entitlements.py`) and the token-based ownership checks in `core/auth.py`.
2. **SOC 2 Type I readiness, then Type II** — control selection, evidence
   automation, policy set, vendor/sub-processor register (the DPA scaffold in
   `docs/ADVICE_BOUNDARY.md` §4 is your starting point), and an audit-friendly
   change trail. Use the existing `audit_log` rather than inventing a parallel one.
3. **Per-tenant isolation** — extend row-level tenant scoping so a partner's data
   can never leak across accounts or appear de-anonymised in a published index
   (the register recommends an n ≥ 5 aggregation threshold).
4. **Production hardening** — the gaps in `docs/PRODUCTION_TRUTH.md` "Still open":
   model-artifact shipping as a release artifact, hypertable conversion where it
   helps, HA/failover, backup/restore drills, and alerting on
   `GET /api/data-freshness` (stale/dead/critical-unknown sources).
5. **Security engineering in the codebase** — the existing invariants are
   non-negotiable: admin-only `/api/admin/*` and `/api/cache/*`, ownership checks
   against the token user id (never a body `user_id`), the DNS-resolving SSRF guard
   on every outbound webhook at creation *and* dispatch, and fail-fast production
   config (JWT secret ≥ 32 chars).

## What success looks like (first two quarters)

| Metric | Target |
|---|---|
| SSO live for ≥ 2 enterprise customers | done |
| SOC 2 Type I report in hand | done |
| Penetration test completed, highs fixed | done |
| `verify_production_truth.py` exits 0 with 0 warnings on prod | done |
| Model artifacts shipped via the release pipeline | done |
| Freshness alerting pages on any critical source | done |

## What you need

- Production FastAPI/PostgreSQL experience, including migrations (Alembic) and
  schema-drift discipline — the repo has a verifier for exactly this.
- Identity protocol depth: SAML assertions, OIDC flows, token exchange, session
  revocation.
- SOC 2 experience from the *engineering* side (controls that are actually
  automated, not screenshots).
- Comfort with a codebase that has an explicit honesty contract: you will be asked
  to make gaps *visible* rather than to make dashboards green.
- Security testing ability (SSRF, IDOR, auth-boundary tests) and a habit of writing
  the regression test with the fix.

## First 30 days

1. Read `AGENTS.md` (non-negotiable rules), `docs/PRODUCTION_TRUTH.md`,
   `docs/GTM_SECURITY_ONE_PAGER.md`, `core/auth.py`, `core/tier_quota.py`.
2. Run `python scripts/verify_production_truth.py` and
   `python scripts/smoke_security.py`; convert each finding into a tracked item.
3. Ship a design doc for SSO that maps groups → canonical plans without adding a
   second entitlement table.
4. Start the control inventory for SOC 2 Type I.

## Definition of done for the role's first deliverable

SSO is done when: an enterprise admin can provision users via their IdP, the
provisioned user lands on the correct plan **via the existing entitlement
path**, access is revocable centrally, and the change is visible in the audit log —
with tests proving each of the four.
