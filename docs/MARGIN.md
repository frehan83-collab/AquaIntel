# Margin bridge — the money view over the price and feed feeds

*WS-29, 2026-10-18. Method version `1.0.0` (`core/market/margin_bridge.py`).*

The bridge answers four questions in one payload, for one week:

1. **Where is the margin** — the price leg minus the modelled cost legs, in NOK per
   kg of harvested round weight.
2. **What moved it** — the price leg week on week (SSB weekly) and the feed leg month
   on month (FRED monthly), each labelled with its own period.
3. **How far is break-even** — and how far the feed leg would have to fall, or how
   low the FCR would have to be, to reach it.
4. **Which levers pay** — price, delivered feed price, FCR, one avoided lice
   treatment and one point of survival, each in NOK/kg with the formula behind it.

API: `GET /api/margin/bridge` and `GET /api/margin/bridge/{locality_no}`.
UI: `frontend/src/components/MarginBridge.tsx`, mounted at the top of `/feed-cost`.

---

## 1. The arithmetic

Per kg of harvested round weight:

```
margin = price − feed − fish_and_harvest − operations − capital
```

| Leg | Source | Cadence |
|---|---|---|
| `price` | SSB table 03024 weekly export price, all sizes, Norwegian border | weekly |
| `feed` | live FRED ingredient basket × the learned 1.86 ingredient-to-delivered multiplier × FCR | monthly |
| `fish_and_harvest` | Fiskeridirektoratet 2024 structure: smolt + slaughter | annual |
| `operations` | labour + other operating (includes average treatment and lice spend) + insurance | annual |
| `capital` | depreciation + net finance | annual |

`feed_ingredients` in the feed engine's `cost_breakdown` is **NOK per kg of feed**;
every other line is **NOK per kg of salmon**. The old `/feed-cost` "Margin Analysis"
panel put the first next to the price and called both per kg — that unit mismatch is
why the panel was replaced rather than restyled. The bridge never mixes the two: the
feed leg is `feed_per_kg_salmon`.

The grouped legs must re-add to the feed engine's own total. The payload carries a
`reconciliation` block and a test pins it; a cost line added or renamed without
updating `COST_LEG_GROUPS` shows up as an `other` leg **and** as a reconciliation
difference, never as a silently smaller cost.

### Feed level as a calibration check

The feed leg is a **model**: a FRED proxy basket (fishmeal, fish oil, soy, rapeseed,
wheat — with 15 % of the ingredient weight on a fixed 2.00 USD/kg "other" line) times
a multiplier learned from the 2024 official series. Its *level* therefore needs an
external check, and the payload prints one: `validation` compares the modelled feed
leg with the last audited realised feed cost (Fiskeridirektoratet 2024: 25.67 NOK/kg
salmon) and names the gap. Outside ±25 % it declares the level indicative.

**Open calibration question (WS-29b).** On 2026-10-18 the model's feed leg is
29.39 NOK/kg salmon (+14.5 % over the 2024 anchor), while market evidence points
lower: BioMar's salmon-feed price fell below NOK 15/kg in Q1 2026 (iLaks, 8 May 2026;
peak >20 in Q1 2023) and realised feed cost was ~25 NOK/kg in 2025 with −3.5 to −4.0
expected in 2026 (Fearnley via iLaks, 18 Aug 2025). If the 2026 realised figure is
~21.5, the model overstates the feed leg by roughly a third. **The deltas, the
break-even relationship and the levers are differential and survive a level error;
the level does not.** Until the multiplier is recalibrated against realised contract
prices, the level stays flagged `modelled`.

## 2. Honesty rules (enforced by `tests/test_margin_bridge.py`)

* **`margin.quality`** is `modelled` unless the caller supplies *both* the price and
  the feed numbers; only then is it `measured`. The margin leg's own `status` follows
  the same rule, so a green "measured" chip can never sit beside a `modelled`
  headline. There is no third state where model output is called measurement.
* **A leg is never "live" by accident.** The feed leg's provenance degrades, with the
  month named, when the oldest dated ingredient is older than
  `FEED_PRICE_MAX_AGE_DAYS` (45), when the basket carries no observation date, when a
  live ingredient carries none, when an ingredient fell back to a default estimate,
  **or when USD/NOK fell back to a constant** (the whole NOK base is converted at that
  rate). On the dev box the oldest FRED point is **2026-07** — 109 days old on
  2026-10-18 — so the feed leg reads "dated rather than current".
* **The price leg** is live only from SSB and only when the newest week is within
  `PRICE_MAX_WEEKS_BEHIND` (2); a cache still answering for an older week degrades
  naming the week. A caller-supplied price is `caller_supplied` and degrades on
  purpose, because the SSB week is not what the margin was computed with.
* **The change is a margin change.** Price is revenue and feed is a cost, so
  `margin_change_nok_per_kg = price_wow − feed_mom`. The first version added the two
  and reported −0.79 where the margin had moved −1.71; a test pins the subtraction.
  The feed leg's own coverage is published (`feed_weight_coverage_pct`,
  `feed_excluded_ingredients`) so a move built from 85 % of the basket says so.
* **Reconciliation is only claimed where it applies.** With a caller-supplied feed leg
  the grouped legs are no longer the modelled cost base, so `reconciliation.ok` is
  `null` with `applicable: false` instead of a false "a cost line was renamed".
* **No volume is invented.** NOK totals appear only when `annual_tonnes` (or
  `standing_tonnes`) is supplied, and the payload names the volume used.
* **Nothing biological is claimed.** Average treatment and lice spend is inside the
  modelled `operations` leg (Fiskeridirektoratet's "other operating costs", 31.3 % of
  total cost). The per-farm endpoint adds the week's § 8 lice limit (a dated official
  fact) and a lice position that is `measured` **only** from verified, current rows —
  otherwise `unknown` with the lineage reason.

## 3. Where the numbers come from

| Assumption | Value | Source |
|---|---|---|
| Feed composition | fishmeal 15 %, fish oil 10 %, soy 30 %, rapeseed 18 %, wheat 12 %, other 15 % | `feed_cost_engine.FEED_COMPOSITION` (Skretting/Cargill/BioMar published reports) |
| Ingredient → delivered feed | × 1.86 (range 1.6–2.1 over 17 years) | 2024: 19.73 NOK/kg official ÷ 10.62 NOK/kg FRED |
| FCR | 1.30 (valid range 1.21–1.35) | Fiskeridirektoratet 2024 |
| Feed share of total cost | 39.7 % | 25.67 ÷ 64.64 NOK/kg, 2024 |
| Harvest weight (for per-fish levers) | 5.0 kg | `biomass_predictor.HARVEST_WEIGHT_KG` (industry average 4.88 kg in Aug 2026 — Arctic Securities) |
| One treatment event | mechanical, 3.00 NOK/fish | `treatment_constants` (Overton et al. 2019; Mowi Handbook 2024) |

A note on "feed is 50-60 % of cost". The audited series says feed is 39.7 % of *total*
production cost and ~44 % of cost excluding depreciation, finance and slaughter. The
50-60 % figure circulates widely and is closer to feed's share of *variable* cost once
smolt is excluded. The bridge publishes the audited ratio and does not repeat the
higher one.

## 4. What a farmer should do with it

* **Read the legs, not the headline, when the badge says `modelled`.** The legs say
  which input moved; the headline depends on the calibration above.
* **Enter your own FCR, delivered feed price and price.** The badge flips to
  `measured`, the feed leg is yours, and the other legs stay the modelled industry
  values (the payload says so on the leg).
* **Use the lever table to price a decision.** "FCR −0.05 is worth 1.13 NOK/kg" is
  more actionable than "costs are high", and with `annual_tonnes` it becomes money.
