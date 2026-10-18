# What the AI surfaces cost, and what to charge for them

Written 2026-10-18, after two online research passes (packaging/pricing of comparable
products; the 2026 state of the art in grounded numeric QA) and the WS-38/39/40 build.
Every price below is a published figure with a source; anything not published is marked.

## 1. The measured cost side (this deployment)

| Surface | Measured cost | Where it comes from |
|---|---|---|
| One grounded chat answer (7 facts, ~1.1k in / 190 out) | **USD 0.0082** | live call, 2026-10-18 |
| One deep-analysis document (~18k in / 0.9k out) | **≈ USD 0.35** | token accounting at Sonnet-class prices |
| One digest (model unreachable) | **USD 0** | deterministic, and no credit is spent |

So the entire 100-question Operator allowance costs about **USD 0.82/user/month**. Chat
cannot be a revenue line at these prices; it is a reason to keep the seat. A document can be.

## 2. What comparable products do (published, 2026)

| Product | AI packaging | Price | Source |
|---|---|---|---|
| Kontali Edge (Norwegian salmon) | data + analyst commentary; forecasts/API quote-only, **no AI tier** | €99/mo Essentials | [kontali.com/pricing](https://www.kontali.com/pricing) |
| Bloomberg Terminal | AI bundled, no AI line | $31,980/seat/yr (reported) | [multiples.vc](https://multiples.vc/compare/pricing) |
| LSEG Workspace / FactSet / S&P Capital IQ | AI in seat | $12k–40k/user/yr (reported) | same |
| Wood Mackenzie Synoptic | "Insight Assistant" grounded in their reports, bundled | not published | [woodmac.com](https://www.woodmac.com/synoptic/) |
| Kpler AI | copilot, bundled, early access | not published | [kpler.com](https://www.kpler.com/product/commodities/kpler-ai) |
| Koyfin | AI inside tiers | $39–$299/mo | [koyfin.com/pricing](https://www.koyfin.com/pricing/) |
| Salesforce Agentforce | per action / per conversation | $0.10 per defined action; $2/conversation | [guide](https://www.jitendrazaa.com/blog/salesforce/salesforce-agentforce-credits-cost-model-complete-guide-2026/) |
| Intercom Fin | per outcome | $0.99 per AI resolution | [Bessemer](https://www.bvp.com/atlas/the-ai-pricing-and-monetization-playbook) |
| Cursor Pro | seat + dollar pool + overage at cost | $20/mo incl. $20 usage | [cursor.com](https://cursor.com/en-US/blog/june-2025-pricing) |

**The revealed preference is unambiguous: every proprietary-data incumbent bundles the
assistant into the seat and publishes no token price.** None of them sells a token markup.
Where metering exists, it meters a *unit of work* (an action, a resolution, a document), not
tokens.

Two structural facts then decide the design:
- The cost of a fixed AI capability falls roughly **13×/year** (Epoch AI, Sep 2026), so any
  price anchored to tokens becomes a visible margin grab within two quarters.
- The top 5 % of users drive ~75 % of AI usage cost (Poyar, 2025), so a flat fee with no
  ceiling funds a negative-margin tail.

## 3. What this platform now does

- **Chat is bundled.** Operator (NOK 4,900) gets 100 grounded questions/month, Desk
  (NOK 2,990) 300, Enterprise 1,000, Intelligence unlimited — a fair-use meter, not a
  product. The 402 names the allowance, the reset date and the upgrade. Measured model cost
  per plan: NOK 7 / 22 / 74 per user per month.
- **Documents are sold.** One credit = one deep-analysis run (margin dossier, origin landed
  cost, lice pressure review). Packs: 10 runs NOK 1,490 · 30 runs NOK 3,900 · 100 runs
  NOK 11,900 (NOK 149 → 119 per document) — 91–97 % gross margin against the measured
  USD 0.35 model cost, because what is sold is the synthesis, not the tokens.
- **A digest costs nothing.** When no model is reachable the run returns the verified data
  itself, labelled `mode: "digest"`, and no credit is spent.
- **Units are named in the UI**, never "tokens": questions on the plan, documents on the
  packs.

## 4. Deliberate deviations from the research recommendations

1. **"Credits" remain, but only for documents.** The research warns users dislike managing
   many credit systems; here there is exactly one unit, one balance, one page.
2. **Overage is not auto-charged yet.** The research suggests NOK 25/question overage. Doing
   that properly needs a stored payment method and dunning; until then the 402 is the honest
   boundary, and the upgrade path is one click.
3. **Annual prepaid answer packs (NOK 12,000/500) are not built.** They need the overage
   plumbing above; the packs that exist are per-document, which is the unit with a legible
   value.

## 5. The quality constraint that outranks all of it

The research on grounded numeric QA is blunt: a model asked to cite still invents numbers,
and up to 57 % of model-generated citations are post-rationalised
([arXiv 2412.18004](https://arxiv.org/abs/2412.18004)); "citations show provenance, they do
not enforce faithfulness" ([arXiv 2509.06902](https://arxiv.org/abs/2509.06902)). So every
answer is checked on the **digits**: each number is matched against the verified facts, an
unmatched one is named in the payload and badged in the UI, and the answer carries one
honest caveat sentence. That is the feature a buyer is actually paying for — not the prose.

Next quality steps, in order: a 150-question golden set with ~35 deliberate refusal cases
and a **silent-wrong-number rate of zero** as the merge gate; prompt-cache the static fact
block (cached reads are ~10 % of input price, per Anthropic); route routine questions to a
cheap model and keep the strong one for documents.
