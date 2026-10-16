# Legal foundations: advice boundary, AI Act, DPA scaffold, data licences

**Status: engineering position, pending legal review.** Nothing here is legal
advice. It exists so a lawyer reviews a *specific, structured* position instead of a
blank page — and so the code can enforce what we wrote down.

Machine-readable: `GET /api/legal/advice-boundary`, `/ai-act`, `/data-licenses`,
`/use-check`, `/performance-fee`.

## 1. Signals vs advice (the boundary that must not blur)

**We are** an information and analytics service: we publish data, indicators,
forecasts and their provenance for professional users to interpret.

**We are not**
- an investment adviser, and not licensed to give personal recommendations;
- a broker, a trading venue, or an execution service — we never route orders;
- a guarantee: forecasts are probabilistic and are published **with their measured
  error, or with no error figure at all** when none has been measured
  (`/api/accuracy/method`).

**Mandatory discloser** on every signal/forecast surface (exported as
`SIGNAL_DISCLOSER` in `core/routers/legal_routes.py`):

> Descriptive indicator, not investment advice. No personalised recommendation is
> made and no execution service is provided.

**Safeguards already in the code**

1. Indices publish their method version, component weights and provenance.
2. Accuracy figures appear only when a validated artifact produced them.
3. No output is framed as "buy/sell/hold".
4. No execution, no order routing, no discretionary management.
5. The performance fee is **deferred** (§5) — partly because a success fee on signals
   is the strongest pull toward the advice perimeter.

**Jurisdiction notes:** assessed against Norwegian and EU regimes (MiFID II
perimeter, Norwegian securities law). Other jurisdictions need separate review.
Marketing material must not present the platform as an adviser.

## 2. EU AI Act transparency notes

| System | Purpose | Transparency | Human oversight |
|---|---|---|---|
| Forecasting engines (foundation models + seasonal-naive fallback) | Probabilistic price/supply/lice forecasting | Responses state `models_used` vs `models_fallback` and set `is_live=false` whenever a fallback produced the number | No automated decision with legal effect on a person |
| RAG assistant over scientific literature | Answering questions from cited documents | Answers cite sources; no autonomous action | The user interprets and decides |
| Anomaly / risk scoring | Flagging unusual lice, production or market patterns | Scores carry provenance and are advisory signals | Flags are reviewed by the user before action |

- **Risk classification:** *limited-risk (transparency obligations)* — engineering
  assessment, **pending legal confirmation**.
- **Prohibited practices not used:** no social scoring, no biometric categorisation
  or emotion recognition, no untargeted facial scraping, no manipulation of
  vulnerabilities.
- **Data governance:** ingestion and training rights are tracked per source,
  including whether AI training is permitted at all. `fish_pool_futures` and
  `eudr_submissions` are explicitly **not** trainable.
- **Personal data:** limited to account and contact data (see §4).

## 3. Data-licence register

`core/legal/data_licenses.py` — one entry per source with `allowed_uses`,
`resale_allowed`, `attribution_required`, `ai_training_allowed` and named risks.

Two honesty rules are enforced in code:

1. **Nothing is cleared until a named reviewer signs it.** `classification_status`
   defaults to `pending_legal_review`, and `check_use()` returns `allowed: false`
   for any uncleared use (even when the licence itself would permit it) with
   `requires_legal_signoff: true`.
2. **Resale conflicts are visible.** `compliance_summary()` names every source whose
   data may **not** be resold — that list is exactly what blocks the
   *Data & Assurance* tier.

Where it stands today (honest): **8 sources registered, 0 legally cleared.**

| Source | Resale | AI training | Note |
|---|---|---|---|
| `fiskeridir_lice` | ✅ | ✅ | NLOD; attribution wording must appear in the API terms |
| `ssb_prices` | ✅ | ✅ | cite table numbers; SSB revises history |
| `nasa_mur_sst` | ✅ | ✅ | attribute "Courtesy NASA/JPL-Caltech" |
| `copernicus_marine` | ❌ | ✅ | derived indicators only; raw redistribution not permitted |
| `fish_pool_futures` | ❌ | ❌ | **blocking** for any public futures display |
| `producer_contributed` | ❌ | ✅ | aggregates only; needs an n ≥ 5 de-anonymisation threshold |
| `eudr_submissions` | ❌ | ❌ | confidential regulatory claims |
| `research_literature` | ❌ | ✅ | keep an open-access allow-list |

**Immediate legal asks:** (1) Fish Pool/Euronext display licence scope;
(2) NLOD attribution wording for the API terms; (3) the producer-data aggregation
threshold.

## 4. DPA / GDPR scaffold (template — requires legal review)

| Section | Position (to be reviewed) |
|---|---|
| Roles | AquaIntel = **processor** for customer-supplied operational data; **controller** for account/billing data |
| Data categories | Account data (name, email, company, role); billing identifiers (Stripe customer id — no card data); API keys (**bcrypt hashes** only); audit-log entries |
| Special categories | None intended. **Confirm** producer data (lice counts, treatments) cannot infer an individual person |
| Purpose limitation | Service delivery, support, security, aggregate product improvement |
| Sub-processors | Stripe (payments), hosting, model/e-mail providers — **register must be completed with DPAs on file** |
| Retention | Account data while active + 12 months; audit logs 24 months; indices/aggregates indefinitely (not personal) |
| Transfers | EU/EEA hosting preferred; any US transfer needs SCCs + a transfer impact assessment |
| Data-subject rights | Export/erasure via account endpoints; deletion must also purge API keys and audit references |
| Breach | Detect (audit log + alerting), notify per GDPR Art. 33 timelines; owner: security lead |
| AI Act link | The §2 transparency notes attach to the DPA as an annex |

**Open questions for counsel:** (a) is producer row-level data personal data where a
farm is operated by an identifiable person? (b) must the licence register be
reproduced in customer contracts? (c) what is the minimum viable security annex for
SOC 2 alignment?

## 5. Performance-fee deferral (a decision point, not a decision)

`core/legal/performance_fee.py` — `STATUS = "deferred"`, switch
`FISHINTEL_PERFORMANCE_FEE_ENABLED` (default **off**).

A success fee tied to trading signals pulls the product toward regulated advice, so
while deferred the platform **must not charge or advertise** one. All five
conditions must be met before enabling:

1. a legal opinion that a fee on informational signals is not regulated advice in
   NO/EU;
2. terms of service describing the fee basis, measurement window and clawback;
3. an auditable performance calculation (the versioned accuracy artifacts are the
   intended basis);
4. client reporting that separates the fee from any advice framing;
5. billing support for a variable fee (the catalog is fixed monthly only today).

The Investor plan is therefore priced as a **fixed monthly subscription**, and a test
asserts that no plan advertises a performance fee.

## 6. What still requires a human (not engineering)

- Legal sign-off on every `classification_status` in the register.
- The Fish Pool/Euronext display licence (blocks public futures display).
- An advice-boundary opinion for the trading-desk ICP.
- The performance-fee decision (owner: founder + external counsel).
- DPA completion and the sub-processor register.

