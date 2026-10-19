# What the market pays for, and what to cut

Written 2026-10-19, after the lice feed was restored (WS-53) and the platform was actually run.
This is a commercial review, not a feature plan. The question it answers: **who pays for this, for
what, and which surfaces are costing us money by existing?**

## 1. The uncomfortable starting point

A salmon farmer already has: lice counts from their own cages (Monday), sea temperature and oxygen
from their own sensors, mortality and biomass in their own farm-management system (AKVA, ScaleAQ,
Fishtalk), a fish-health service on contract, and twenty years of judgement about when to treat and
when to slaughter. **Any surface that tells them what they already know is negative value**: it
costs attention, it is wrong more often than their own data, and it teaches them to ignore the
product.

So the test for every page is not "is it useful?" but:

> Is this something the buyer **cannot produce themselves**, or something they are **obliged to
> produce and would rather buy**?

That leaves four things, and they are not what most of the platform's 66 pages are about.

## 2. What actually gets paid for

| # | What | Who pays | Why they cannot do it themselves | Our evidence |
|---|---|---|---|---|
| 1 | **Evidence for audits and customers** — ASC readiness, CSRD/regulatory packs, EU traceability, treatment records with lineage | Farmer (compliance budget), processor | It is an obligation, not a decision; auditors want a dated record, not a dashboard | `asc-compliance`, `regulatory-reports`, `traceability`, `compliance`, WS-1/14 lineage, WS-49 receipts |
| 2 | **Market context** — spot and forward prices, feed cost, margin bridge, origin landed cost, tariff exposure | Buyer, trader, processor, investor | A farmer sees their *own* contract price; nobody sees the whole formation, the duty basis or the origin comparison | SSB 03024, Euronext, FRED basket, mandated tariff register, WS-37 duty basis |
| 3 | **Cross-boundary early warning** — disease spread from neighbouring sites, bloom risk, PA-level lice pressure | Farmer, area manager, buyer | Their own sensors stop at their own cages; the risk that closes a site comes from the next fjord | Mattilsynet cases, IMR/CMEMS chlorophyll, W41 lice by site |
| 4 | **Documents that leave the platform** — the deep-analysis runs, with a receipt | Buyer, investor, enterprise | They need to forward something defensible, not read a dashboard | WS-39/43/49/54: verified, withheld if unsupported, receipted |

Everything else is a feature looking for a payer.

## 3. The trim: 56 nav links → 33

Nav is the product's claim about itself. Fifty-six links for one differentiated data asset tells a
buyer the product is unfinished. The hidden surfaces keep working — pages and routes stay, only the
navigation changed — because deletion is an owner decision, but **advertising** them is ours.

| Surface | Verdict | Reason |
|---|---|---|
| `/signals` | **Hide** | Withdrawn equity signals (WS-20). A link to a legal notice is a liability. |
| `/investor` | **Hide** | Advertises paper trading and Monte Carlo while the equity output is withdrawn. Either repoint it to fundamentals (supply, cost curve, company volumes) or stop selling the plan. |
| `/trader` | **Hide** | Paper trading with no licensed edge and no directional calls: a demo seat. |
| `/twin` | **Hide** | Farm digital twin; the farmer's own vendor does this with better inputs. |
| `/scenarios`, `/scenarios-lab` | **Hide** | `/api/scenarios` returns 404; the lab duplicates it with no buyer. |
| `/china-demand` | **Hide** | `/api/china-demand/snapshot` returns 404. |
| `/benchmark` | **Hide** | `/api/benchmarking/companies` returns 404; `/compare` covers the need. |
| `/farmer` | **Hide** | Duplicate of `/farmer-daily`. |
| `/welfare` | **Hide** | Modelled score, overlaps `/bio-risk`; no paying audience of its own. |
| `/efficacy` | **Hide** | Marketplace seeded with 60 demo outcomes. Sell it when real outcomes exist. |
| `/causal` | **Hide** | Academic causality view. Interesting, no payer. |
| `/ras` | **Hide** | Niche with demo-only data. |
| `/command-centre` | **Hide** | Operations demo. |
| `/ml-baselines` | **Hide** | Model museum; `/accuracy` carries the honest number. |
| `/design-system` | **Hide** | Internal. |
| `/climate` | **Hide** | Overlaps `/bio-risk` and `/satellite`. |
| `/canada`, `/scotland`, `/faroe`, `/iceland` | **Hide** | Country monitors with thin data; `/global-supply` aggregates the same signal. |
| `/satellite` | **Keep**, with honesty | Verified-scene provenance only. Do not advertise coverage we do not have. |
| `/treatment`, `/harvest` | **Keep** | Cheap, and they are the pages that feed the compliance record. |
| `/chat` ("Ask the data") | **Keep** | The only surface that answers questions across *all* the data. Position it as the analyst, not a chatbot. |

The exceptions are deliberate: nothing was deleted, and the test in `tests/test_nav_trim.py` keeps
the nav honest (every link resolves, no hidden surface is linked, ≤36 links, each hidden surface has
a written reason).

## 4. Revenue-integrity problems that outrank any new feature

1. **Desk (NOK 2,990) is cheaper than Operator (NOK 4,900).** The ladder tells a farmer that the
   analyst tier is worth less than the farm tier. I fixed the *upgrade path* (WS-50: Operator now
   suggests Enterprise, never the cheaper Desk), but the price itself is an owner decision.
2. **The Investor plan (NOK 24,900) sells features that are withdrawn.** Paper trading and Monte
   Carlo profit simulation are still in the feature list while the equity surfaces are down for
   legal review. That is not a packaging problem, it is a misrepresentation.
3. **Credit packs are priced per document, and only one document is fully supported today.**
   Origin landed cost is live and dated; the lice review is live again as of WS-53; the margin
   dossier still rests on a July feed basket (WS-29b). Say which document is calibrated before
   selling the pack.
4. **Zero of three sub-processors are contracted.** Enterprise and investor procurement will stop
   there. It is an hour of legal work and the highest-value hour available.

## 5. What I would stop building

- **More farmer advice.** The decision card, the treatment optimizer and the harvest timer are the
  weakest commercial products on the platform precisely because the farmer is the expert. Keep them
  as the *input* to the compliance record, price them at zero, and stop marketing them.
- **More sensors or "intelligence" surfaces.** The platform's edge is aggregation and evidence, not
  measurement.
- **More AI surfaces.** One grounded assistant plus paid documents is the right shape; a second
  chatbot, a model museum or an "insight" feed dilutes it.
- **More country pages.** Origins belong in one comparison (`/competitiveness`), not four monitors.

## 6. What I would build next, in order

1. **Sell the compliance pack** as a named deliverable: ASC readiness + regulatory report + EU
   traceability in one export, with the receipt. That is the one thing a farmer is obliged to buy
   and cannot assemble himself.
2. **Repoint the Investor plan** to non-directional fundamentals: supply, cost curve, reported
   company volumes (WS-35), tariff and landed cost. No equity calls.
3. **Make the daily check the retention loop it was meant to be** — but with the farmer's own count
   as the input (customer-reported lineage), not our re-derivation of it.
4. **Fix the feed-level calibration** (WS-29b) so the margin dossier is honest before it is sold.

## 7. The one-sentence version

The platform is not worth paying for because it can see lice; farmers see lice. It is worth paying
for because it can show an auditor, a buyer or a board what happened, when, and on what evidence —
and because it sees the market and the neighbouring fjord, which the farmer cannot.
