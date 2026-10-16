# 3-minute demo script

**Rule for the demo: show provenance, not just dashboards.** The honesty layer is
the differentiator; a competitor can copy a chart, not a published method.

## Setup (before the call)

```bash
python main.py                  # API + agents
cd frontend && npm run dev      # UI
python scripts/verify_production_truth.py   # know what is degraded today
```

Have these open in tabs: `/indices`, `/accuracy`, `/pricing`, and the response for
`/api/indices/bio-price-weekly`.

## 0:00–0:30 — the hook

> "Salmon prices move on biology before they move on paper. This shows the biology,
> the price read, and **where every number came from**."

Open `/indices`. Point at the Bio→Price Weekly card: headline, `read`, and the
**caveats list**.

## 0:30–1:15 — the two indices

- `AI-STI` — "is supply tension building?" Show the component table: names, weights,
  scores, **sources**.
- `AI-LPI` — "how hard is lice pressure nationally?"
- Point at the badge: `method v1.0.0` and `live`/`degraded`. Then say the line that
  closes deals:

> "If a source is down, the index says *degraded* and names the missing component.
> If everything is down it returns no value at all — we don't guess."

## 1:15–2:00 — the accuracy page

Open `/accuracy`.

- If metrics are published: show MAPE, coverage, `n`, and the fallback flag.
- If not (current state on this deployment): say exactly this:

> "Nothing is published yet on this box, because we won't show a MAPE we haven't
> measured on real data. Here's the command that publishes it, and here's the
> contract we validate against."

Then show `/api/data-freshness`: which sources are fresh, stale, dead, or
**synthetic-only**. "We publish our own data gaps."

## 2:00–2:30 — the money path

Open `/pricing`. Say: "These are the real plans; the paywall is enforced — try to
hit a premium output on a free account and you get a 402 with the upgrade path."

(If asked for proof: `POST /api/billing/webhook/mock` completes the flow in a demo
environment.)

## 2:30–3:00 — close with their numbers

`POST /api/gtm/roi {"icp": "producer", "inputs": {"annual_tonnes": <their figure>}}`

> "Every number here is either your input or clearly marked as an assumption, with
> the formula shown. Change one and re-run — we don't assert your market."

Then the ask: **"90-day paid pilot, 5–8 partners, success metrics agreed up front."**

## Objections (rehearsed, honest)

| Objection | Answer |
|---|---|
| "Kontali/other incumbents cover this" | "They publish research; we publish reproducible indices with a method version and a licence register. Different product, and it composes with theirs." |
| "Is your forecast accurate?" | Show `/api/accuracy`. If unpublished: "Correct — we won't claim accuracy until it's measured. That's the design." |
| "Can you resell producer data?" | "No — and the register says so. Producer data is used in aggregates only (`/api/legal/data-licenses`)." |
| "Is this investment advice?" | "No. Descriptive indicators, no recommendations, no execution: `/api/legal/advice-boundary`." |
| "SSO/SOC 2?" | Honest gap list from the one-pager, then the enterprise-engineer roadmap. |
