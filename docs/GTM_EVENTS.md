# Event playbook — AquaNor & NASF readiness

**Goal per event:** 5–8 paid pilot conversations, 2 signed 90-day pilots, 1 press-worthy
index mention. Nothing else.

## 8 weeks out

- [ ] `python scripts/verify_production_truth.py` green on the demo deployment.
- [ ] Publish the accuracy artifact from real data (`scripts/publish_accuracy.py`) —
      a demo with a *measured* MAPE is a different conversation.
- [ ] Publish at least 8 weeks of AI-STI/AI-LPI history (`POST /api/indices/publish`
      weekly) so the chart shows a series, not a dot.
- [ ] Print the one-pager (`docs/GTM_SECURITY_ONE_PAGER.md`) — one page, honest gaps.
- [ ] Booth demo rehearsed to 3 minutes (`docs/GTM_DEMO_SCRIPT.md`).

## 4 weeks out

- [ ] Target list: 20 desks, 15 processors, 20 producers (NO/CL), 5 insurers/banks.
      One row each: company, contact, ICP, why now, expected objection.
- [ ] Book 6 meetings per day of the show; leave 30% of slots free.
- [ ] LinkedIn cadence live for 4 weeks before the show (2–3 posts/week).

## Booth kit

| Item | Detail |
|---|---|
| Screen A | `/indices` — Bio→Price Weekly + component table |
| Screen B | `/accuracy` + `/api/data-freshness` — the honesty layer on display |
| Screen C | `/pricing` + ROI calculator with **their** numbers |
| One-pager | Security/architecture, with the "not in place yet" table intact |
| QR | `/pricing` and `/api/indices/bio-price-weekly` |
| Giveaway | Nothing plastic: a printed AI-LPI history chart is more memorable |

## The 90-second stand pitch

> "Salmon supply tension is measurable before it hits price. We publish two
> indices — AI-STI for supply tension, AI-LPI for lice pressure — with the method,
> the weights, and the source of every component. When a source is down the index
> says degraded instead of guessing. There's a free tier; the paid tiers unlock the
> price path and the field tool. Are you the person who owns lice and harvest
> planning?"

## Event-specific

**AquaNor (Trondheim)** — producer- and processor-heavy. Lead with the **Operator**
plan and the lice-quota/field story; book the desks you can reach in Oslo separately.

**NASF (Nordic/Atlantic seafood)** — research and sustainability audience. Lead with
the **Accurancy & Method** page and the data-licence register: "here is exactly what
we may do with each source, and what we do not claim."

## After the show (72 hours, non-negotiable)

1. Every card scanned → CRM row with the ICP and the objection raised.
2. Same-day follow-up mail with **their** ROI calculation attached.
3. Send the pilot terms within 5 working days to anyone who said yes on metrics.
4. Publish a "what we heard at {event}" post — it converts to inbound.

## What NOT to do

- Do not demo a feature that is still degraded without saying it is degraded.
- Do not promise SSO, SOC 2 or a performance fee (see
  `docs/ADVICE_BOUNDARY.md` and the one-pager gap table).
- Do not run the ROI calculator with our defaults and present the output as their
  economics.
