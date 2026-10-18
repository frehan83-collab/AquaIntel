# Changelog

All notable changes to FishIntel / AquaIntel. Format follows the spirit of
Keep a Changelog; versions come from `core/version.py` (single source of truth).

## [2.6.0] — commercial hardening (in progress)

### WS-32/33/34 — the bloom and satellite surfaces stop inventing things (2026-10-18)
**Why:** an audit + a three-lens council found the algae surface would not survive a
buyer's first five minutes. `/bloom` **crashed for every user** (`api.bloomRisk()`
returns `{items, data_provenance}` and the page called `.filter()` on the envelope);
six-month-old chlorophyll wore a pulsing "Live monitoring" badge; `chl_a_trend` was
computed against the row the agent had just written (0.0 on all 123 045 rows); 842
alerts said `sent` with no SMS/email channel configured; the bio-risk disease count
called a method that does not exist (always 0, claiming Mattilsynet); the brief
reported "5108 sites at HIGH/CRITICAL bloom risk" from every row ever stored; and the
satellite page **fabricated per-farm readings with a seeded RNG** and rendered
"Action required" from them.
- **WS-32 satellite honesty.** `core/market/satellite_engine.py`: `_simulate_reading`
  deleted; a farm without a scene produces **no reading**; `SatelliteSnapshot` gained
  `n_readings_verified`, `n_readings_unverified`, `scene_dates`, `missing_reason`;
  `is_live` follows verified scenes, never `bool(credentials)`; an NDVI anomaly is
  labelled `surface_scum_or_vegetation` ("not a chlorophyll or toxicity measurement"),
  not `possible_bloom`; the catalogue drops the fabricated HAB-confirmation and
  cage-census products and marks every remaining product `validated: false`.
  `core/routers/ocean_routes.py` gives `/api/satellite/{status,products,scan,anomalies}`
  provenance — degraded with a reason when no scene exists. The page shows
  "NO VERIFIED SCENE" instead of "LIVE"/"SIMULATED MODE" and no longer prints
  "Action required" from an anomaly.
- **WS-33 bloom truth.** `core/routers/bloom_routes.py`: one `_bloom_freshness()` +
  `_bloom_provenance()` pair; live only when the newest chlorophyll observation is
  ≤ 7 days old, otherwise degraded naming the date and age; payloads carry
  `observed_at`, `age_days` and a `dataset_note` when stored rows came from a different
  CMEMS product than the client fetches (the model defaulted to the Atl 1 km L3 id while
  the client reads the global 4 km L4 one). The alert log's provenance now states it is
  a delivery record, not a measurement. The bio-risk disease count calls the real
  `fetch_disease_cases`/`get_disease_summary` pair and reports `status: unavailable`
  instead of a silent zero. `agents/bloom_agent.py` computes the trend against the
  previous **distinct** observation date (never the row it just wrote); the model
  returns `None` when no earlier observation exists and the payload says "trend
  unavailable". `core/bloom/notifications.py` records `not_configured` / `sent` +
  `delivered_at` / `failed` / `dashboard` instead of stamping `sent` before dispatch,
  and the message reads "CHLOROPHYLL WATCH … not a toxicity measurement". The brief
  counts distinct localities inside the last week and names the data age.
  **Alembic 021** adds `bloom_alerts.delivered_at`, relabels pre-fix `sent`/`delivered`
  rows `legacy_unknown` (nobody can prove they were delivered) and nulls the
  self-compared `chl_a_trend` values; the downgrade keeps both corrections.
- **WS-34 bloom context.** `core/bloom/context.py` + `GET /api/bloom/context`: the IMR
  Algestatus link with its `checked_at` and an explicit "no API" note, the documented
  regional mortality events (2019 *C. leadbeateri* 8 M fish / NOK 2.4 bn potential
  sales value; 2025 *C. leadbeateri* + *Phaeocystis* >2 M fish / ≥NOK 300 M; March 2026
  *Pseudochattonella* PO1 ~1.7 M fish) each with a source URL, and the five limits of a
  satellite chlorophyll band (biomass not toxicity; kilometre pixels; subsurface
  blooms; gap-filled product; no published Norwegian threshold or operational
  species-level forecast). The endpoint is degraded by design — it is a dated link, not
  a feed.
- **Frontend** `frontend/src/app/bloom/page.tsx` unwraps the envelope (the crash), renders
  the served provenance instead of a live badge, shows "n/a" for an unknown trend, and
  adds a "what this shows / what it cannot show" panel plus the dated advisory and event
  history. `BloomMap.tsx` accepts `chl_a_trend: number | null`.
- **Docs:** `docs/DATA_SOURCES_COST.md` — what satellite/HAB data costs (CDSE free quota,
  CMEMS free with redistribution rights, MET free, Earth Engine $500/month, Sentinel
  Hub/Planet quote-only) and which sources a paid product may display.
- Tests: `tests/test_satellite_honesty.py` (8), `tests/test_bloom_honesty.py` (17), a
  021 migration test. **Council record:** three lenses agreed to fix before adding; the
  proposed finer-grained 300 m per-farm OLCI layer was **rejected** (a cage is
  sub-pixel, the product is largely gap-filled, and the 2019 bloom was subsurface at a
  pycnocline that ocean colour cannot see).

### WS-28a/30/31 — stop writing calls, stop printing multiples, stop using Yahoo FX (2026-10-18)
- **WS-28a directional-write gate.** `core/legal/equity_signals.py` gained
  `DIRECTIONAL_WRITES_ENABLED = False` and `may_persist_directional(instrument=...)`.
  The four agents that still wrote trade directions on listed shares — signal
  generator, market hedger, prediction agent and the bloom agent's SHORT injection —
  now check it and skip, leaving an audit row or a log line. The surfaces were taken
  down in WS-20; the writers were not, so the rows would have reappeared the moment the
  agents service started. Non-equity instruments (spot, futures) are unaffected.
  `tests/test_directional_writes_gate.py` (14).
- **WS-30 ROI calculator.** `core/gtm/roi.py`: claim-like inputs (avoidable share,
  harvest-timing gain, basis improvement, affected volume share, loss-ratio
  improvement, minutes saved, admin hours) **default to zero**, the processor's
  hard-coded 0.5 became `share_of_volume_affected`, and each ICP reports the
  **break-even** value of its primary driver plus `benefit_needed_nok` — "you need this
  product to create NOK 35 880 a year to pay for itself" instead of a 228x/491x/1 693x
  multiple that a finance buyer reads as a red flag. `tests/test_gtm_roi.py` (17).
- **WS-31 licensed FX + attribution.** `core/market/fx_rates.py` (new) reads the
  official daily NOK rates from Norges Bank (open data, observation date attached);
  `feed_cost_engine` and `competitiveness_engine` now convert through it instead of
  Yahoo Finance, whose terms forbid deriving income from its data. Fallbacks are still
  recorded and degrade the payload (`usd_nok_is_fallback`, reason included). The
  attribution footer gains Norges Bank, Mattilsynet and the FRED notice the API terms
  require, and drops the Yahoo claim.
- **WS-31b — Yahoo removed from every data path.** `core/market/fx_rates.py` gained
  `rate_to_usd()`: Norges Bank quotes for USD, EUR, GBP, DKK, SEK, ISK, CAD and PLN
  (with the per-100 convention for DKK/SEK/ISK handled in one place) converted through
  the official USD/NOK rate, and a documented constant — always flagged — where no
  licensed daily source exists (CLP only). `competitiveness_engine` resolves every
  currency through it and records `_fx_observations` / `_fx_reasons`; `euronext_futures`
  takes EUR/NOK from Norges Bank; `macro_intelligence` derives NOK/EUR and USD/CNY
  (FRED `DEXCHUS`) instead of Yahoo; the feed engine's Yahoo commodity gap fill is
  deleted (FRED covers all five ingredients); and `salmon_price.get_latest_prices()`
  returns **only** the SSB spot — the Oslo equity quotes are gone, together with the
  fallback that *derived* share prices by multiplying the salmon spot by fixed
  multiples (MOWI 2.8x, SALM 3.4x …), which was a fabricated market price. The pairs
  agent now skips explicitly rather than trading on proxies, and `/api/market/equity-prices`
  serves `equity_quotes: "unavailable"` with the reason and a degraded provenance.
  Live state: USD/NOK 9.44 (observed 2026-10-16, Norges Bank), competitiveness
  `partial_fallback` naming CLP alone, macro `nok_eur` 0.0941 and `nok_cny` 1.43 from
  licensed sources. Tests: `tests/test_licensed_sources.py` (11) plus the WS-22 FX
  tests updated to the new module.
- **WS-35 — company volumes are reported facts.** `top50_engine` derived annual
  production as `n_localities * 800` and shipped it as a volume: Mowi read **113 600 t**
  against ~**332 000 t** harvested in Norway in 2025 — a 3× understatement of the largest
  producer on the analyst desk. The multiplier is retired and replaced by
  `core/market/company_facts.py`: one row per reporting entity with the year, **scope**
  (Norway vs group), figure and source URL. A company without a registered fact reports
  `production_volume_tonnes: null` with a `volume_basis` block that says so (never 0,
  which would read as a measurement), sub-entities do not repeat the group figure, and
  unknown volumes sort last. `tests/test_company_volumes.py` (11).
- **WS-29b — the realised feed anchor.** The margin bridge's feed leg is a model, and
  its last audited anchor is Fiskeridirektoratet's 2024 survey; the 2025/2026 figures are
  not published (checked 2026-10-18), so the platform does not invent them. New
  `core/market/feed_anchor.py` reads an operator-registered realised figure from
  `artifacts/feed_realised_prices.json` (template: `feed_realised_prices.example.json`)
  — NOK per kg of *harvested salmon*, 10–60, year 2008+ and not in the future — and the
  bridge prefers it to the survey, reporting `anchor_source`, `anchor_scope`,
  `anchor_is_registered` and `anchor_stale`. A malformed file is ignored with a reason
  and the payload falls back to the survey, naming it; with no anchor at all the note
  tells the operator how to register one. `tests/test_feed_anchor.py` (10).
  **Still open:** obtain a defensible realised figure, recalibrate the multiplier against
  it, bump `MARGIN_METHOD_VERSION` and republish the validation.
- **WS-36 — the smolt pipeline is checked before it is used.** `smolt_model` projects
  harvest from smolt releases × survival × yield; on 2026-10-18 its 12-month total is
  **789 987 t against the module's own 1.7 M t national reference (0.46×)**, while SSB's
  weekly export volumes imply ~120 000 t/month nationally. New `SmoltModel.validation()`
  publishes the ratio and the deviation, and `/api/supply/smolt-forecast` degrades with
  the reason ("the level is uncalibrated; use direction and seasonality only") instead of
  serving the projection under a live badge with the label "Smolt model +
  Fiskeridirektoratet". The `measurement` field states it is a model projection, not
  reported supply. `tests/test_smolt_validation.py` (8), including the calibrated branch
  so the check is about the gap, not a hard-coded verdict.
  **Open:** calibrate the release/yield constants against Fiskeridirektoratet's reported
  harvest; until then the level stays flagged.

- **WS-37 — US duty assessed on the customs value.** `competitiveness_engine` computed
  `tariff_cost = production_cost × rate`. US duty is assessed on the **transaction value**
  of the imported good (the importer's price), not the producer's cost, so the engine
  understated the duty by the exporter's margin — the kind of error a trade-compliance
  reader spots first. The rate is now charged to the best available declared value: the
  live SSB export price for Norway (USD via Norges Bank), production cost elsewhere with
  a note saying the true duty is higher by that margin. Every row carries `tariff_base`
  (`export_price` / `production_cost`), `export_price_usd`,
  `tariff_at_export_price_usd` and a `duty_base_note` that states the direction ("the
  export price is below cost" on 2026-10-18, so the cost-base figure was the higher one);
  the snapshot carries `tariff_basis`. `/competitiveness` marks export-price rows with
  `*` and prints the basis under the table. `tests/test_tariff_basis.py` (6).

- **WS-42 — a free OpenRouter chain, and what the live model taught the checker.** The
  OpenRouter catalogue was fetched live (2026-10-18): 16 free models, of which the chain now
  shipped is `google/gemma-4-26b-a4b-it:free` (tools + response_format),
  `nvidia/nemotron-3-super-120b-a12b:free` (reasoning) and `nvidia/nemotron-3.5-lightning:free`
  (1M context). The domain-specific free models (code, safety, OCR) were rejected: this surface
  needs instruction-following on a citation-constrained numeric prompt. Limits are OpenRouter's
  documented 20 req/min and 50 req/day (1,000/day after a $10 lifetime top-up).
  `LLM_FREE_MODELS` / `LLM_FREE_FALLBACK` (default on) / `LLM_PREFER_FREE` (default off); the
  client walks the chain when the paid model fails, labels the answer `is_free`, records the
  cost as zero (never priced from COST_TABLE) and names the model that failed. Verified live:
  the free model answered "MARGIN -1.69" with cost $0.0000.
  Running the golden set live was the point: the first run left 38.9 % of numbers unmatched,
  and the causes were presentation, not invention — a dropped minus sign ("a loss of 1.69"), a
  rounded 1.7, a bare "301" from the tariff basis, "18"/"90" from the model's own arithmetic.
  The checker now matches sign-insensitively, searches numbers inside cited strings (HTS codes,
  "Section 301") and masks month dates; the offline gate stays at 18/18 with 0 unmatched. The
  remaining live gap is derived arithmetic, which the next step — a single repair pass that
  re-asks without the unsupported numbers — addresses. A third live run was still running
  against the free tier's 20 req/min ceiling when this was written, so its number is not
  claimed.
  Tests: `tests/test_llm_free_fallback.py` (9); `scripts/eval_chat.py --live` added.

- **WS-41 — the panel and the gate.** The workbench existed only as an API; a paid feature
  with no button is not a product. `/chat` now carries a **Deep analysis** panel in its right
  rail: the credit balance, the three runs with what each reads, a run button, and the rendered
  document with its sources and its charge note (a digest run says it cost nothing and spends
  no credit). New client methods `workbenchCatalog`, `workbenchRun`, `creditsStatus` and the
  matching types.
  And the claim "every number is checked" now has a gate: `artifacts/chat_golden_questions.json`
  (18 questions, including four that must be refused and two that must disclose a gap) is run
  offline by `scripts/eval_chat.py` and by `tests/test_chat_eval.py`, on the deterministic path
  so it costs nothing and never drifts with a model upgrade. Measured on 2026-10-18:
  **18/18 cases, 100 % refusal accuracy, 100 % gap disclosure, 490 numbers checked, 0
  unmatched** — the silent-wrong-number rate is zero, which is the number a buyer asks about.
  The run also caught two real extractor bugs: week labels and ISO dates were being read as
  claims (`W41` → 41, `2026-07` → −07), and unit suffixes and legal citations (`m3`,
  `Section 301`) likewise; dates, week labels, units and citations are now masked, and a
  fact's `age_days` counts as a supported number because it is a fact attribute.

- **WS-39 — documents are sold, tokens are not.** `core/billing/credits_catalog.py` prices
  three packs of deep-analysis runs (10 for NOK 1,490, 30 for NOK 3,900, 100 for NOK 11,900 —
  NOK 149→119 per document, 91–97 % gross margin against the measured USD 0.35 model cost);
  `core/llm/credits.py` is an append-only ledger (`grant`/`spend`/`balance`/`history`, Alembic
  **023** `credit_ledger`) so every balance has a history and a refund is a new row;
  `core/llm/workbench.py` renders three documents — margin dossier, origin landed cost, lice
  pressure review — each grounded on the same fact block as the chat plus its engine detail;
  `POST /api/workbench/run` spends exactly one credit for a model-written document and
  **nothing** for a digest, `GET /api/workbench/catalog` lists runs/packs/balance, and
  `POST /api/billing/credits/checkout` starts a one-off purchase (documented mock without
  Stripe keys). `tests/test_workbench_credits.py` (19).
- **WS-40 — the numbers are checked, not the citations.** `core/llm/claim_check.py` extracts
  every numeric claim from an answer and matches it against the verified facts (rounding
  tolerated to 1 %, a rate matched as its percentage, Norwegian decimal commas parsed); an
  unmatched number is kept but named in the payload, badged in the UI and followed by one
  honest caveat sentence. The reasoning is the research: up to 57 % of model-generated
  citations are post-rationalised (arXiv 2412.18004) and citations do not enforce
  faithfulness (arXiv 2509.06902). Wired into both the chat and the workbench.
- **`docs/AI_PRICING.md`** records the pricing research (13 products with published prices),
  the measured cost side, and the deliberate deviations — including why chat is bundled and
  documents are metered, and why overage and annual answer packs are not built yet.
- **WS-38b — a provider failure is an error, not an answer.** `llm_client.complete()` used to
  return `LLMResponse(content="[LLM error: ...]")` with no flag, so a caller rendered the
  error as the answer (the workbench did exactly that when the box's OpenRouter balance ran
  out on 2026-10-18). `LLMResponse.error` now carries the failure with empty content, and the
  chat and workbench treat it as a failure — fallback or digest, no credit spent.

- **WS-38 — the chat became a product: grounded, metered, and convertible into an alert.**
  The chat was the one surface that bypassed the honesty layer: `/api/chat` in
  `core/api.py` string-interpolated a national lice average over **every** row (demo seeds
  included), a latest week with no age, and a hardcoded "traffic light: green < 0.2"
  sentence that is not how the Norwegian system works — then billed nothing and counted
  nothing, on a USD 100/month model budget that a dozen users could exhaust. It was also
  available to Desk (NOK 2,990) but **not** to Operator (NOK 4,900).
  **Grounded:** `core/llm/grounding.py` assembles seven facts — verified-only lice (with the
  week and its age), the § 8 limit for the current week, the SSB export price, the margin
  bridge (with the feed month and its quality verdict), satellite chlorophyll (with the
  scene date), the latest traffic-light decision and the dated US tariff — each with
  `as_of`, `source` and `live`/`degraded`/`stale`/`unavailable`, gathered concurrently so a
  dead engine degrades only its own fact. The prompt forbids numbers outside that block.
  **One path:** `core/llm/chat_service.py` replaces both old entries; `mode` says whether a
  model wrote the prose (`grounded`), the deterministic assembler did because no model was
  reachable (`grounded_fallback` — the numbers still arrive, labelled), the legal notice did
  (`refusal`, no tokens spent) or nothing (`unavailable`).
  **Metered:** Alembic **022** adds `chat_usage` (one row per user per month); each plan
  states `chat_questions_per_month` (free 0, Operator 100, Desk 300, Enterprise 1000,
  Intelligence unlimited); the route answers a structured 402 naming the allowance, the
  reset date and the upgrade, and only a model-backed answer consumes the allowance.
  **Useful:** `POST /api/chat/save-alert` turns "tell me when lice in PA 3 goes above 0.4"
  into a **running** `CustomAlertRule` (metric, operator, threshold, production area, seeded
  from the current verified value when the question gives no number) — and refuses to
  invent a metric or a threshold when the question does not support one.
  `/api/chat/usage` serves the meter; `/chat` is rebuilt around it (allowance meter,
  sources with provenance chips, "watch this", a locked state that explains the plan).
  Measured on 2026-10-18: one grounded answer = **1 070 input + 188 output tokens =
  USD 0.0082**, so 100 questions/month ≈ USD 0.8 of model cost.
  Tests: `tests/test_chat_grounding.py` (22) + `tests/test_chat_metering.py` (15).

### WS-29 — the weekly margin bridge (2026-10-18)
- **Why:** the platform held the two inputs that decide a salmon producer's week —
  the live SSB export price and the live feed ingredient basket — and never turned
  them into money with the assumptions named. `/feed-cost` showed a margin bar and
  three rows whose units disagreed (feed ingredient cost per kg of **feed** next to
  the price per kg of **salmon**), nothing said what had moved, and the feed legs
  carried no provenance at all. A farmer could not tell whether the number was a
  measurement or a model, or whether the feed price was this month's or July's.
- **NEW `core/market/margin_bridge.py`** — the bridge, method version `1.0.0`: the
  price leg minus four grouped cost legs per kg of harvested round weight, the
  week-on-week price move, the month-on-month feed move, the break-even and the feed
  or FCR improvement that would close it, and five levers (price, delivered feed
  price, FCR, one avoided lice treatment, one point of survival) each with its
  formula. It composes the existing engines rather than adding data:
  `feed_cost_engine`, `ssb_price_client`, `biomass_predictor.HARVEST_WEIGHT_KG`,
  `treatment_constants`, and `regulatory_facts` for the farm's § 8 limit. The grouped
  legs reconcile against the feed engine's total in the payload and in a test.
- **Honesty rules, all pinned by tests:** `margin.quality` is `modelled` until the
  caller supplies both the price and the feed numbers (then `measured`); the feed leg
  degrades with the month named when the FRED observation is older than 45 days, when
  the basket carries no date, or when an ingredient fell back to a default; a
  caller-supplied price is `caller_supplied` and degrades on purpose; no NOK total is
  produced without a caller-supplied volume; the modelled feed level is checked
  against the last audited realised cost and the gap is printed. The per-farm
  endpoint adds the week's lice limit (a dated official fact) and a lice position that
  is `measured` only from verified, current rows.
- **NEW `GET /api/margin/bridge` and `GET /api/margin/bridge/{locality_no}`** in
  `core/routers/feed_cost_routes.py`; `docs/openapi.frozen.json` re-frozen (two paths
  added) and the provenance baseline updated deliberately (205 baselined).
- **NEW `/feed-cost` margin bridge panel** (`MarginBridgePanel`): headline margin with
  a `measured`/`modelled` badge, the leg table with per-leg status and period,
  spot-vs-cost bars, "what moved", break-even, the lever grid, a "your numbers" row
  (FCR, delivered feed, price, tonnes) that flips the badge to `measured`, and a
  collapsible basis panel with the assumption register and the level check. It
  replaces the old one-bar "Margin Analysis" card. The ingredient rows now show the
  FRED **observation month** instead of an "EST" chip that mislabelled a live monthly
  series as an estimate.
- **CHANGED `core/market/feed_cost_engine.py`** — `IngredientPrice.observed_at` parses
  the FRED CSV date and `FeedCostSnapshot` carries `feed_prices_as_of` /
  `feed_prices_as_of_latest`; `get_latest()` exposes `feed_prices_as_of`,
  `feed_prices_age_days` and per-ingredient `observed_at`, and
  `data_freshness.feed_prices` is now the **observation** date rather than the fetch
  time. **Found on the way:** the newest FRED "global price" point is **2026-07**
  while `/feed-cost` reported the request time as the price date — a three-month-old
  observation presented as current. `feed_index_change()` is new: the weighted
  month-on-month move of the same basket with the same weights, each ingredient over
  its own two latest months, refusing to report a zero (and naming what it excluded)
  when fewer than three ingredients have two comparable points.
- **CHANGED `core/market/decision_engine.py`** — the treatment ROI values lost
  biomass at the **live SSB spot** instead of the hardcoded `95.0 NOK/kg`: against
  W41's 72.55 the constant overstated every cost of inaction by a third and
  contradicted the margin bridge on the same screen. The card now carries
  `fish_value_nok_per_kg` and `fish_value_source` (the constant's fallback is visible
  in the provenance label), and `_compute_roi` takes the value as a keyword argument
  so the property tests keep their signature.
- **Review round (same day, independent reviewer).** Seven defects the first draft
  shipped, all fixed with tests: the change total **added** the price delta (revenue)
  to the feed delta (a cost) and reported −0.79 where the margin moved −1.71 — now
  `margin_change_nok_per_kg = price_wow − feed_mom`; the margin leg was stamped
  `measured` beside a `modelled` headline; reconciliation compared the caller's feed
  leg to the engine total and cried "a cost line was renamed" (`ok` is now `null` with
  `applicable: false`); the validation block called a caller's feed leg "the modelled
  feed leg" (it now names `compared: model|caller_inputs`); a card valued at the
  constant 95.0 still served `is_live: true` (the fallback now degrades the card);
  a cache answering for a stale SSB week was labelled live (both consumers degrade
  past `PRICE_MAX_WEEKS_BEHIND = 2` and name the week); and the USD/NOK constant
  fallback was silent, so the whole NOK basket could be converted at 10.5 while the
  payload said live (recorded as `usd_nok_is_fallback` and degraded). Also: the feed
  provenance now says "oldest dated ingredient" (it stores the *oldest*, not the
  newest), an undated live ingredient blocks a live verdict, the reconciliation
  tolerance is the rounding budget rather than 1 % of the total, the feed change
  publishes its weight coverage, and the frontend no longer seeds the "your numbers"
  form with the model (one click on Apply used to flip the badge to `measured`).
- **Second review round.** Three follow-ups on the fixes: the margin change is now
  `null` unless *both* deltas are known (with only the price delta it silently
  reported the price move as the margin move); the feed change's FRED history is
  bounded (`FEED_CHANGE_TIMEOUT_S = 6` in the bridge) and `feed_index_change` caches a
  failure for 15 minutes, so a cold or rate-limited FRED window cannot make every
  request pay the retry cost; and the validation panel prints the number the gap was
  actually computed from (`model` vs `yours`) plus the note. The decision card also
  memoises the salmon value for 10 minutes (`SALMON_VALUE_TTL_S`), because a portfolio
  builds one card per farm and would otherwise repeat the fetch — and SSB's retries —
  up to 30 times.
- Tests: `tests/test_margin_bridge.py` (45) — arithmetic and reconciliation, the
  margin-change sign and its null-when-unknown rule, the break-even and lever
  formulas, every degradation path (stale/undated/defaulted basket, USD fallback,
  stale SSB week, slow feed history), the farm block's verified-only rule, the
  decision card's price leg, the feed engine's weighted month-on-month method, and the
  frozen contract. `docs/MARGIN.md` documents the method and the open calibration
  question (WS-29b: the FRED proxy basket's level versus realised contract prices).
- **Deliberately not done:** the modelled cost base stays a model — the bridge says
  so on every payload, and the level is not silently recalibrated. No new premium
  gate was added to `PREMIUM_PREFIXES` (the paywall ladder is an owner decision).

### WS-22 (part 2) — claims that outran the data (2026-10-18)
- **Why:** four payloads stated more than their inputs supported. Competitiveness
  reported `data_quality: "live"` while NOK/USD had fallen back to the hardcoded
  0.093 (about 10.75 NOK/USD); `/api/accuracy` reported
  `foundation_models_available: true` from `import torch` alone (an importable
  library is not a loaded model); `/api/disease/norway` sliced the first 20 active
  outbreaks in upstream order, so its newest visible diagnosis was 2026-06-09 while
  the geo view had 2026-09-22; and `/api/disease/alerts` named Mattilsynet in its
  provenance while querying only WOAH and Sernapesca, so it could answer "no
  significant disease outbreaks" with Norwegian ISA cases active.
- **Competitiveness:** `_fetch_fx_rates` records every currency that fell back;
  `_to_dict` reports `data_quality: partial_fallback` (`stale_fallback` when the
  Norway production cost fell back), `fx_fallbacks`, `fx_fallback_values`, a
  `fallback_reason`, and a degraded `data_provenance`. It is `live` only when no
  quote fell back. Two silent fallbacks behind that label were repaired on the way:
  both macro lookups imported `macro_intelligence_engine`, which does not exist (the
  singleton is `macro_intelligence`), so NOK/USD **always** fell back and the US spot
  was **always** the undated USD 8.50 constant; the spot fallback is now tracked
  (`us_spot_fallback`) and degrades the payload too.
- **Foundation models:** availability now comes from the library that loads each
  model (`chronos-forecasting`, `timesfm`, `uni2ts`) plus torch, with per-model
  `installed`/`loaded` detail and a note that an importable library is not proof
  that a forecast was real. `is_available()` is deliberately not called — it
  downloads weights.
- **Disease list:** `newest_first_cases()` sorts by diagnosis (then suspicion) date
  before the 20-row cap; the summary reports `active_outbreaks_shown` against
  `active_outbreaks_total`.
- **Disease alerts:** `_fetch_norway_alerts()` queries Mattilsynet (active cases as
  ongoing alerts, ISA high and trade-relevant) alongside the regime signals, **one
  alert per disease type with `cases` = active localities** (one row per locality
  inflated `active_outbreaks` and `risk_level`);
  `MattilsynetClient.last_fetch_ok` separates an empty answer from a failed one and
  survives a cache hit; every source records `ok`/`failed`/`unavailable` and the
  payload serves `sources` + `sources_failed`; `/api/disease/alerts` builds provenance
  from the sources that answered and names those that did not.
  `/api/disease/{norway,norway/geo,treatments,by-company}` share one
  `_mattilsynet_provenance()` rule: live only when Mattilsynet answered **and**
  returned rows, degraded with the reason otherwise (the geo route's empty early
  return now carries provenance too).
- **Frontend:** the competitiveness and disease pages render the served
  `data_provenance` instead of a hardcoded `quality="live"` badge; the types gain
  `partial_fallback`, `fx_fallbacks`, `sources`/`sources_failed` and
  `active_outbreaks_shown`/`_total`.
- **Contract:** deliberate OpenAPI re-freeze of one description
  (`/api/disease/alerts` said "Regime", now "Mattilsynet").
- **Tests:** `tests/test_ws22_data_claims.py` (21), including the live-NOK path the
  broken import had never exercised; `tests/test_routers.py`'s by-company provenance
  assertion is rule-based instead of network-dependent.

### WS-21 — regulatory facts as dated, sourced data (2026-10-17)
- **Why:** the served traffic-light colours came from the frozen regime detector and
  were wrong for 6 of 13 areas against the 19 June 2026 decision (its history used
  2019/2021/2023/2025, years with no decision); decision cards used a 0.5 lice limit
  all year; the reporter applied 0.2 only for PA 2-7 in weeks 16-21; a count equal to
  the limit was not a breach although § 8 says "færre enn"; weekly reports were due
  "Wednesday" (§ 10: Tuesday); US tariffs predated the July 2026 Section 301 action.
- **New `core/regulatory_facts.py`:** the five official colour decisions (2017-10-30,
  2020-02-04, 2022-06-07, 2024-03-06, 2026-06-19) with announcement and regulation
  URLs, the capacity cuts with the date each applies (§ 9: 6 months after the cut
  regulation; PO3 stays at 88.36% until about 2027-02-20), `capacity_pct` /
  `scheduled_capacity`; the § 8 limit by region and ISO week (`lice_limit`,
  `breaches_limit`; county name or number, the Nordland municipalities inside PO7 —
  Bindal, Sømna, Brønnøy — then the production area; an unknown region in a spring
  window is a precautionary limit, flagged `established: false`); dated US salmon
  tariff rows (Norway and Chile 12.5%, UK 10%, Canada 0% with a USMCA claim, Faroes
  and Iceland MFN free, from 2026-07-24; Federal Register 2026-15181).
- **Consumers:** traffic-light simulator and route serve the official decision (with
  capacity in force, a scheduled cut, the decision's sources; offered green growth is
  not counted); the frozen regime detector's colour tables read the facts
  (maintenance only); the decision engine acts on this week's limit (Norwegian time),
  judges the count against its own week's limit and reports a past breach, treats a
  breach as TREAT_NOW whatever the trend, and labels each history bar with its week's
  limit; the regulatory reporter judges each count with `assess_lice_count` (unknown
  region between 0.2 and 0.5 → indeterminate, not a breach) and reports due Tuesday;
  competitiveness takes rate and citation from one dated lookup; the lice-quota note
  says the quota system is a proposal (Meld. St. 24), not "targeted 2026-2028".
- **Frontend:** competitiveness banner and table, global supply, traffic light,
  farmer daily (bars and gauge from the limit), exposure and lice-quota pages no
  longer show retired tariffs or framework text.
- **Contract:** deliberate OpenAPI re-freeze of one description
  (`/api/compliance/report/weekly-lice/{locality_no}` stated the retired PA 2-7 rule).
- **Tests:** `tests/test_regulatory_facts.py` (72), clocks pinned through `_now`
  seams; the reporter runs on a throwaway database.
- **Verification:** facts researched and double-verified against regjeringen.no,
  lovdata.no, federalregister.gov and hts.usitc.gov (333 agents). Review: three rounds
  (4 lenses, then 2, then a final read, two refuters per finding) confirmed 21 + 15 + 7
  findings, all fixed or recorded below.
- **Recorded, not done (HANDOVER WS-21):** other flat-0.5 consumers, the simulator's
  scenario arithmetic, chat prompt/RAG facts and a chat crash, a full municipality →
  county table, the pending Section 301 court ruling.

### WS-23 (takedown) — no accuracy figure outside the registry (2026-10-17)
- **Why:** the price outlook printed "Backtested 4-week MAPE: 8.5% … 68% of actual
  prices fell within the indicated band" and a `band_trust` coverage from
  `data/models/price_backtest.json`, whose 2026-10-12 run let the 52 `demo_seed`
  SSB rows override the real history; the conformal residuals that calibrated the
  rule tier's bands came from the same run; the figure was copied into
  `price_predictions` on every GET (888 rows on the dev box, 879 with a copied
  MAPE) and re-served by `/api/market/prediction-history`. The model comparisons
  and the supply-demand engine printed their own MAPE/coverage outside the
  registry too.
- **`core/market/price_ml.py`:** the legacy artifact is never read for display
  (`_load_backtest` removed); `mape_backtest` / `band_trust` are null; the accuracy
  statement says no backtest of the running tier is in the registry and points at
  `/api/accuracy`; conformal residuals load only from an artifact that declares
  `demo_rows_used: 0`, so the rule tier's bands are honestly "not calibrated".
- **Routes:** `/api/market/price-outlook` stores at most one prediction per ISO week
  and horizon; `/api/market/prediction-history` serves `mape_backtest: null`; the
  three `/api/ml/*/model-comparison` routes withhold `mape`/`rmse`/`coverage_80`
  with a `metrics_withheld` block (new
  `accuracy_registry.withhold_unregistered_metrics`) — they scored a 4-point
  holdout on the DB's (demo) SSB rows; the supply-demand price path drops its
  "measured out-of-sample coverage ~80%" and serves its walk-forward artifact only
  when registered (`served_backtest()`). The ML Baselines page shows why metrics
  are withheld; the supply backtest text points at the registry.
- **Review fixes:** the TFT tier's statement says its bands are the model's own
  quantiles; the outlook stores no prediction on a fallback (75.0) spot;
  `price_predictions` freshness cadence is now 168 h; the lineage gate accepts only
  an integer 0; the price-outlook page says "nominal" intervals and its "Prediction
  Track Record" (which showed the forecast move as an error %, colour-coded like
  accuracy) is now a "Prediction Log" of forecast moves; `TestPriceOutlook` uses a
  throwaway store; AGENTS.md rule 1, the API-docs copy and the comparison type
  follow.
- **OpenAPI re-freeze (deliberate):** the TimesFM and MOIRAI comparison
  descriptions promised MAPE/RMSE/coverage, the outlook promised "conformal" bands
  and the demand-balance route a "validated backtest"; the frozen diff is exactly
  those four descriptions (payload shapes changed: metrics removed,
  `metrics_withheld` added). `frontend/src/types/generated.ts` was not regenerated
  (no openapi-typescript installed here; it already lagged).
- **Tests:** `tests/test_accuracy_claims.py` (12) plants artifacts shaped
  like the contaminated ones and binds the routes to a throwaway DB; 9 of the 10
  initial tests failed on the old code (the chat case is a guard: that branch
  imports a module that does not exist). Added to the fast gate.
- **Not done (the re-run half, still WS-23):** fix the loader, re-run on real SSB
  prices, publish the served model's backtest next to carry-forward with a
  Diebold-Mariano test, re-derive the residuals with `demo_rows_used: 0`, start the
  weekly forecast log. Until then no price-model accuracy figure is shown.

### WS-20 — SHORT equity signals taken down (2026-10-17)
- **Why:** anonymous `GET /api/signals` served the signal generator's directional
  calls on listed salmon shares — on the dev box 1,238 rows, every one SHORT, on
  Grieg (GSF), Lerøy (LSG), Mowi (MOWI), SalMar (SALM) and others, each with a
  per-share impact such as "Expected stock impact: -17.2% (NOK -28/share)" — and
  /trader, /signals, the dashboard and the chat showed them, against the project's
  own advice boundary. This may be an investment recommendation under the EU Market
  Abuse Regulation, Art. 3(1)(34).
- **New `core/legal/equity_signals.py`:** the one definition of the withdrawal
  (reason, notice, chat answer, advice-boundary entry with what is still under
  review).
- **API:** `GET /api/signals` serves `{"signals": [], "withdrawn": true, "since",
  "reason", "advice_boundary"}` and never reads the table (query parameters kept:
  frozen contract and limit bound); `POST /api/signals/confirm` and `/reject`
  answer 410 (confirming was the consent step the execution agent turned into a
  paper order). `/api/legal/advice-boundary` publishes `withdrawn_outputs` with an
  `under_review` list of the same-kind outputs still served, and its safeguard line
  points there. `GET /api/market/hedger-signals` serves only the hedger's
  salmon-price (`SALMON_SPOT`) rows — the hedger also writes LONG/SHORT rows on
  listed shares, which its first tick would otherwise have published.
- **Chat:** the rule-based answer says the signals are withdrawn instead of listing
  them (and no longer falls back to the pairs calls); the LLM context and the
  `/api/chat` system prompt no longer carry pending signals and tell the model never
  to say whether to buy, sell or short a listed security; the chat page and the
  fallback answer no longer advertise "active trading signals".
- **Frontend:** the /trader signals panel, the /signals pending, processed and
  order-history sections (replaced by a withdrawal notice), the dashboard's Recent
  Signals widget and ticker item, and the chat page's client-side signal answer are
  removed; `api.confirmSignal`/`rejectSignal` deleted; `api.signals()` is typed as
  the notice; the e2e visual stub and README's route table follow. Verified on the
  running dev frontend (/signals, /trader, /): no signal rendered, 0 console errors.
- **Tests:** `tests/test_signals_takedown.py` (15): seeds SHORT and LONG rows on
  GSF/LSG/MOWI/SALM into a throwaway DB bound to every reader, then checks the route
  (4 query variants), the limit bound, confirm/reject (410, row unchanged), the
  hedger route, the published advice boundary, both chat paths and the page sources.
  Added to the fast gate.
- **Review:** an independent review found no blockers; its should-fix items (the
  hedger route, the notice over-claiming, the chat still advertising signals) and
  the real nits are fixed.
- **Not done here (WS-28):** pairs positions on listed shares, per-ticker sentiment,
  `/api/orders`, the trader Event Impact Simulator's per-company stock moves, the
  agents that write directional rows (signal generator, hedger, prediction, bloom),
  the Streamlit dashboard, the admin `signals` export, the TopBar's dead
  pending-count call; and the legal opinion itself.

### WS-20 — public honesty on the landing, API docs, billing and pricing pages (2026-10-17)
- **Why:** the pages a prospect reads first carried invented testimonials (one
  credited to Nordic Investment Bank), stale typed counts ("229 API Endpoints",
  "53 Market Engines", "1,815 farms"), claims the platform does not serve ("real-time",
  "TFT price prediction", a causal "z=3.26", "418 vessels"), price tables that
  disagreed with the plan catalog, a waitlist form that confirmed sign-ups it never
  stored, and an API reference in which 10 of 53 documented endpoints did not exist,
  one with invented accuracy figures (docs/VALUE_ANALYSIS.md section 3).
- **Landing:** testimonials, stat strips and the fake waitlist removed; feature and
  hero copy rewritten to what is served; plans render from `/api/billing/catalog`
  with loading and failure states; links to Accuracy & method, the published
  indices, data sources and licences, and pricing.
- **Billing (closes WS-11):** `TIER_DETAILS` deleted, plans render from the catalog
  with a presentation-only icon map; demo mode is handled before the mock checkout
  URL (which has no page behind it); the API-calls figure shows the plan's daily
  quota instead of a never-incremented monthly counter; the enforcement note
  describes what is enforced.
- **API docs:** the 10 missing endpoints corrected or removed; the endpoint count is
  computed; samples and the Python, JavaScript and cURL examples use real response
  keys; the invented model-comparison MAPE sample removed and the holdout errors
  described as diagnostics; the disease-alerts source, AIS and efficacy descriptions
  corrected; the stale `v2.1.0` badge, the non-existent "Institutional" plan and the
  provenance explainer (freshness is the compute time, not data age) corrected.
- **Plan catalog (`core/entitlements.py`, rendered on /pricing, /billing, /landing):**
  "Real-time supply tension" → weekly; "conformal bands" → scenario bands; "SSO"
  removed (WS-6 is open); the lice-quota line says the quota system is a proposal.
- **Privacy:** the AI Act model disclosure names the models that are served.
- **Tests:** `tests/test_public_claims.py` (20): page sources and the rendered catalog
  strings carry none of the removed claims; plan prices are never typed into a page
  (derived from `PLANS`, any separator); every documented endpoint and every
  code-example path exists in `docs/openapi.frozen.json`; samples print no accuracy
  figures. The tests fail on the previous page versions.
- **Review:** an adversarial review (3 lenses, 2 verifiers per finding) confirmed 17
  findings, all addressed here or recorded as backlog; 5 split findings handled.
- **Not done (owner decisions):** one product name; the Desk/Operator price
  inversion. **Recorded:** the disease-alerts engine never queries Mattilsynet but its
  provenance says it does (WS-22); the model-comparison route prints holdout MAPE on
  four demo rows (WS-23); the OpenAPI description still says "real-time" (needs a
  deliberate re-freeze); the SHORT-signals takedown is in progress in a separate
  change.

### WS-19 — the index history is guarded before any agent runs (2026-10-17)
- **Why:** AI-STI read 100 "severe" from one component, `quota_pressure`, fed by the
  lice-quota tracker's national utilisation (238,367 % on the dev box: a lice count
  divided by constants labelled tonnes, for a quota regime that is still a
  proposal); AI-LPI v1.0 was built only on the same number and its
  `quota_headroom` was inverted (range about 27-55). The `index_publisher` agent
  would have stored a degraded AI-STI 100 every week from 2026-W43.
- **Method 2.0.0** (`core/market/indices.py`): `quota_pressure` removed from AI-STI
  (`biomass_momentum` / `harvest_pressure` keep their 0.40 : 0.35 ratio, published as
  0.5333 / 0.4667); **AI-LPI v1.0 withdrawn** — `PUBLISHED_INDICES = ("AI-STI",)`,
  `WITHDRAWN_INDICES` (AI-LPI answers `status: "withdrawn"`, `value: null` and the
  reason, never computed or stored), `SUPERSEDED_VERSIONS`; `methodology()` publishes
  `withdrawn` and `superseded_versions`. No index reads the lice-quota tracker.
- **Publication set:** `index_publication.INDEX_CODES` projects
  `PUBLISHED_INDICES`, so the agent, `status()`, `readiness()`, `publish_week()`,
  `store_digest()` and the verifier never build, store or report AI-LPI as missing.
  The Bio→Price Weekly digest carries only published indices plus a `withdrawn`
  block, its headline no longer cites lice pressure, and — because the read now
  rests on AI-STI alone — a degraded AI-STI (the biomass tracker's estimate
  fallback) adds a caveat and degrades the digest; the supply panel's provenance
  follows the tracker's own lineage instead of an unconditional live stamp.
  `GET /api/indices` lists AI-LPI as withdrawn; the `/indices` page shows its card
  with "method v1.0.0" and a "withdrawn" badge.
- **Freshness:** the `index_observations` source counts only rows that are not
  superseded (`SourceSpec.excluded_when_set`), so the withdrawn method's rows can
  no longer make the critical index store read "fresh".
- **History kept, marked:** Alembic **020** adds `superseded_by`,
  `superseded_reason`, `superseded_at` to `index_observations` and marks every
  method-1.0.0 row superseded by 2.0.0 (index-specific reason); no value, band,
  component or provenance is edited and nothing is deleted. `history()` and
  `/api/indices/{code}/history` expose the marks. On the dev box the two
  test-written 2026-W42 rows (AI-STI 100, AI-LPI 55 claiming live) are marked.
- **Tests:** `tests/test_indices.py::TestIndexGuard` (no index reads the tracker;
  AI-STI moves in its documented direction and spans 0-100, per component too;
  AI-LPI withdrawn; a real publisher tick stores only AI-STI at 2.0.0 with no quota
  input; history exposes the marks) and
  `tests/test_migrations.py::test_020_marks_method_1_observations_superseded_and_keeps_their_values`.
  The publication-mechanics tests now publish AI-STI plus a test-only second code
  so the per-index gate stays exercised; the AI-LPI lineage tests moved to the
  tracker's provenance (`test_lice_payload_is_live_only_on_its_lineage`).
- **Copy:** the Insight plan feature now reads "Public index (AI-STI) and Accuracy &
  Method"; GTM proof point, LinkedIn/event/demo scripts, the design-partner producer
  metric, freshness label and agent docstrings no longer sell AI-LPI.
- **OpenAPI re-freeze (deliberate):** response shapes changed (`status` on every
  index result, `withdrawn` on the digest, `superseded*` on history rows) and two
  route descriptions had become false ("supply + lice pressure"; "every published
  index"). `docs/openapi.frozen.json` was re-frozen; its diff is exactly those two
  descriptions (the schemas are `{}`). No path, parameter or response model changed.
- **Review:** an independent review found no blockers; its should-fix items (the
  digest's live claim, freshness over superseded rows, GTM copy, false route
  descriptions) and nits (dev-box figure in the public reason, headline wording,
  the tracker guard covering every public tracker coroutine) are fixed with tests.

### Docs — product value analysis and a reprioritised backlog (2026-10-17)
- **New `docs/VALUE_ANALYSIS.md`:** an evidence-based answer to "too many features?",
  "valuable for the market?", "what raises quality?" and "why does the UI look
  AI-made?", from five research lenses, a fact-check of the web claims (8 of 24
  refuted and corrected), an adversarial critique, and an independent per-section
  verifications of the draft (391 claims checked, 88 corrected). It separates dev-box state (no agent runs here) from code and copy
  defects that appear on any deployment.
- **Finding with an honesty-layer impact:** the price outlook's "Backtested 4-week
  MAPE: 8.5%" comes from a backtest whose loader let the 52 `demo_seed` SSB rows
  (2025) override the real history (trap 6). A same-window re-run on real prices
  gives 8.53% at 4 weeks against 8.82% for carrying the last price forward: a small,
  statistically significant edge, but the published figure, its data and its
  configuration are wrong. Recorded as WS-23.
- **Finding with a regulatory impact:** anonymous `GET /api/signals` serves 50 SHORT
  signals on listed salmon shares with per-share impact estimates, against the
  project's own advice boundary. Recorded in WS-20 as the first takedown.
- **Backlog:** `docs/HANDOVER.md` gains WS-19…WS-27 (index-history guard before any
  agent runs, public honesty, regulatory facts as dated data, buyer-checked numbers,
  accuracy against a carry-forward baseline, test isolation, cold starts, navigation
  cut, design identity), widens WS-14 (live from observation age on every visible
  route) and WS-16 (partial weeks), and supersedes WS-15's quota calibration.
  Priority now starts at WS-19; WS-3 waits for WS-23; WS-4…WS-7, WS-10, WS-13's
  SOC 2 / pen test and WS-18 are deferred until a named deal needs them. No code
  changed.

### WS-2 — the weekly indices are published on a schedule
- **Why:** `publish_week()` existed but nothing scheduled it, so
  `/api/indices/*/history` held only what test runs had written and nothing could
  say whether the current week had been published.
- **New agent `agents/index_publisher_agent.py`** (`index_publisher`, the 13th agent,
  started by `python main.py --agents-only`, i.e. the production `agents` service):
  ticks hourly, builds the digest, and stores it only when the current ISO week is
  not yet stored for every index at the current method version **and the digest is
  ready** — the unique constraint on `index_observations` is the second line of
  defence, and losing that race to another writer is reported as a duplicate, not
  a failure. A failed or incomplete publication is an error log, an
  `index_publication` audit row and a `last_failure` in `health()`, and the tick
  raises so the orchestrator counts it — never silence (paging a human is WS-9).
- **Readiness gate, per index** (`index_publication.readiness()`): an observation is
  immutable for its (index, week, version), so the first computation of a week must
  not lock in an artefact of missing inputs. An index with no value is never stored
  (the store refuses it, whoever writes); within the first 72 h of the week only a
  live value is stored; after that a degraded value is stored with its provenance
  saying why — a source outage is disclosed, never hidden. A valid AI-STI is not
  withheld because AI-LPI's source is down.
- **The admin endpoint shares the gate:** `publish_week()` applies `readiness()`, so
  `POST /api/indices/publish` answers 409 when nothing could be stored (naming why)
  and 200 with per-index `storage` otherwise; `force=true&reason=…` overrides the
  grace only (never the null rule), its intent is written to the audit log
  **before** anything is stored (503 and no store when the audit log is
  unavailable), and `forced` is true only when a grace-withheld value was actually
  stored (a duplicate is not a forced publication). One UTC normaliser
  (`core/source_lineage.to_utc`) stamps and judges every week label, so a non-UTC
  caller can never build one week and check another. The freshness cadence for the store is one
  definition: publication + readiness grace + one tick (241 h), so a designed wait
  never reads as "stale"; the verifier reports a wait inside the grace (with last
  week stored) as info, and an unmeasurable interval (fewer than two observations)
  as info rather than "ok"; a partial in-grace store (one index stored, the other
  withheld) is reported as the designed wait it is, never as "the agent has not
  run"; a future-dated row is a named `store_ahead_of_clock` warning.
- **New `core/market/index_publication.py`** — `status()` reads the *store*, not the
  scheduler: per index the latest stored week with its value and provenance
  verdict, weeks behind, the ISO-week steps between consecutive observations
  (`interval_ok` = no step > 1; wall-clock `gaps_days` are informational because
  they drift with the hourly tick), and overall `current_week_published` /
  `missing` / `degraded_current` / `skipped_weeks`. A missing or unreadable table
  reports every index as missing with the reason. One definition of the cadence
  (168 h + one tick) and the publisher hint, imported by the freshness monitor.
- **Surfaces:** `GET /api/indices` carries a `publication` block; the production-truth
  verifier adds `index_publication_current_week` (ok — naming a degraded current
  week — or warn naming the week and the missing indices) and
  `index_publication_interval` (warn naming skipped weeks).
- **Also fixed on the way:** `indices.save_observation` treats a lost insert race
  as a duplicate instead of raising; `BaseAgent` sets its status back to running
  after a tick succeeds (it stayed `error` forever).
- **Tests (+29):** the week/label/cadence contracts; honest status on a missing
  table; missing → published with method-version scoping and stored provenance;
  interval measured in ISO weeks (7 d + 30 min is fine, 2 weeks is a skipped week,
  `weeks_behind`); the agent across an injected week boundary at fixed instants
  (no wall-clock flakiness), the bare `tick()` form, the readiness gate (waiting
  within the grace, disclosed degraded store after it, never a null value), a
  store failure (raise + audit + health), a lost race, an unreadable store after a
  successful write, an incomplete store; the race-safe `save_observation`;
  `BaseAgent` status recovery; the `/api/indices` block; the orchestrator wiring
  (uncommented lines); the verifier verdicts deterministically (ok with
  degradation, warn with the store's reason, skipped-week warning).
- **Review:** four adversarial rounds (4 + 3 + 2 lenses, verifiers per finding) plus
  a final independent read confirmed 21 + 15 + 11 + 5 findings — the wall-clock interval metric, the missing readiness
  gate and then its admin-endpoint bypass, the per-digest (not per-index) gate, the
  Sunday-night test flake, a race test that faked its integrity error, the false
  "FAILED" audit on an unreadable re-read, the sticky `error` status, a freshness
  cadence that contradicted the grace, vacuous `interval_ok`, doc counts; all
  addressed above.
- **Deliberate OpenAPI re-freeze:** no new route, but `POST /api/indices/publish`
  gained the `force` and `reason` query parameters and a new description, so
  `docs/openapi.frozen.json` was re-frozen with `scripts/freeze_openapi.py` for that
  one operation (twice: parameters, then the description). The provenance ratchet (GET routes) is unchanged.

### WS-1 — the lice lineage is verifiable (`lice_records.source`)
- **Why:** `lice_records` had no `source` column, so demo seeds and reported
  BarentsWatch rows were indistinguishable and AI-LPI reported `is_live: false`
  with "lineage unverifiable" on every call — correct, but it meant the flagship
  index could never legitimately claim live. The demo seed's locality
  numbers (10001–10022) sit inside the real BarentsWatch numbering range (the lowest
  real locality on the dev DB is 10029), so a collision is possible in principle and
  demo rows must be identified by a per-row marker, never by locality.
- **One vocabulary, one module:** `core/source_lineage.py` — `barentswatch` (the
  system of record; the handover's `fiskeridir` would have misnamed it), `demo_seed`,
  `unverified` (server default). NULL, '' and anything outside the vocabulary classify
  as unverified; any value containing demo/seed/synthetic/mock/fallback is synthetic.
  The freshness monitor now imports these markers instead of carrying its own copy
  (its SQL used to omit `fallback`), and its timestamp parser is the same function.
- **Migration 019** adds `source VARCHAR(32) NOT NULL DEFAULT 'unverified'`
  (renders identically on SQLite and PostgreSQL), backfills NULLs, relabels only the
  rows provable as demo by construction (demo locality numbers × the seed year 2025)
  and **never backfills a real source** — the 185,099 bulk-loaded rows on the dev box
  have no row-level proof (audit logs only record per-tick insert counts), so they
  are `unverified`. A conftest-reconciled nullable column is repaired to the ORM
  contract; the downgrade drops the column in batch mode. SQLAlchemy Core with bound
  parameters only (the `%s` trap from 016).
- **Writers:** `agents/data_ingest.py` writes `barentswatch` on **both** branches of
  its upsert (a demo/legacy row overwritten with reported values is now real);
  `core/demo_seed.py` writes `demo_seed`; the historical backfill now counts only
  **verified** rows when deciding to skip a week, so bulk-loaded weeks get
  re-ingested instead of staying unverified forever.
- **Row-level lineage, not column presence:** `lice_quota_tracker` counts the rows it
  actually aggregated (same predicates as the data query) per production area and
  nationally — `lineage` block in every cached payload, mirrored to `last_lineage`
  (the biomass-tracker precedent). A value is live only when every used row is
  `barentswatch`, every PA contributed rows without a fetch failure, and the newest
  row is within the 168 h cadence; otherwise the tracker's provenance is **degraded
  with the reason** (the three unconditional `DataProvenance.live` stamps in that
  file are gone, including the single-locality emission path).
  `indices._lice_lineage_note()` reads that lineage; an all-demo CI database and a
  bulk-loaded dev box both stay honestly degraded.
- **Freshness + verifier:** `/api/data-freshness` now reports `verified_rows`,
  `unverified_rows` and `no_verified_rows` per source with a lineage contract, and
  lists `no_verified_rows` at report level; `verify_production_truth.py` adds the
  `freshness_no_verified_rows` warn verdict and a **critical** `lice_source_column`
  check (a DB whose migration chain never ran 019 would fail every lice insert —
  recovery: `alembic stamp 018` then `alembic upgrade head`, never stamp head).
- **Measured on this box after the change:** `[('demo_seed', 1040), ('unverified',
  185099)]`; freshness `lice_records`: synthetic 1,040 / verified 0 / unverified
  185,099, `no_verified_rows: true`; AI-LPI `is_live: false` with
  "6997/6997 lice rows used carry no verified source … newest lice observation is 2026-W15, 27 weeks old … newest lice row was fetched 4604 h ago" (and every PA named).
  That is the honest result: the lice ingest has been dead since 2026-04-07 (see
  WS-16) and no pre-WS-1 row can be relabelled without a real re-ingest.
- **Tests (+20):** migration shape + backfill/downgrade on fresh subprocess DBs;
  closed vocabulary; the lineage rules (synthetic, unverified, empty, failed PA,
  stale); deterministic freshness counts on a throwaway file DB built with the
  conftest's exact type-only DDL (so a real NULL row exists); live-DB invariants;
  endpoint contract; verifier verdicts; AI-LPI live/degraded across six lineage
  shapes; the upsert writing `barentswatch` on insert **and** update against a
  temporary async engine (never the real DB); the backfill counting verified rows
  only; tracker lineage shape, a failed-PA degradation and the single-locality path.
- **Review fixes folded in** (independent adversarial review of the diff, 19
  confirmed findings): the national merge keeps every PA's own fetch time and
  observation week, so one stale area degrades the national view; liveness is gated
  on the newest **observation week** (current or previous ISO week), not only on
  `fetched_at`, because the backfill's re-ingest bumps the write time of old weeks;
  cached payloads re-evaluate their lineage against *now* on every hit; the
  verifier checks the column's **shape** (a nullable/no-default column is the
  reconciliation shape 019 never repaired → warn with the recovery); the conftest
  reconciliation now carries the ORM's server default and NOT NULL; the freshness
  SQL `TRIM`s so it agrees with the classifier; provenance labels no longer name a
  biomass source the tracker does not read (biomass is an estimate from Table 8
  constants); the ingest logs how many rows an upsert relabelled; the accuracy
  publisher imports the shared markers. Each fix carries a test.
- No route or response model changed → no OpenAPI re-freeze; the provenance ratchet
  is unchanged (237 routes, 0 unregistered).

### Handover — takeover package for the next coding module
- **New `docs/HANDOVER.md`** — the brief an incoming module executes from: verified
  current state measured at `f04e79a` (2.6.0, 345 paths/353 operations, 1004 tests
  collected, 18 migrations, 38 routers, 77 engines, 68 frontend pages), the exact gate
  commands (including the fast 207-test slice and the two re-freeze steps), what is
  shipped per area with the doc to read, the six non-negotiables, a **13-item
  workstream backlog (WS-1…WS-13)** each with files / steps / testable acceptance
  criteria / traps, a **10-row trap table** of the bugs that actually cost time here,
  and a definition of done.
- **`docs/NEXT_STEPS_PLAN.md` marked superseded** — it was written 2026-10-12 at
  `0ba29e3` and its numbers (FastAPI 2.2.0, ~328 routes, ~650 tests, 14 migrations)
  would have misled a new module. It now carries a banner with the current verified
  figures and points at the handover.
- **`SESSION_STATE.md` refreshed** from "Sessions 33-37 / 2026-04-11" to the
  commercial-hardening sessions with the commit list; **`AGENTS.md`** and
  **`PROJECT_STATUS.md`** now point an incoming agent at `docs/HANDOVER.md` first.
- The backlog's first items are the concrete engineering follow-ups already identified:
  a `source` column on `lice_records` so AI-LPI's lineage becomes verifiable, scheduled
  weekly index publication, model-artifact shipping, Timescale hypertables, a durable
  quota ledger, SSO, tenant isolation, more accuracy artifacts, freshness alerting,
  runtime provenance measurement in CI, removing the last hardcoded tier table in the
  frontend, and enforcing the data-licence register at runtime.



### Follow-up — the accuracy artifact is now real (via a bug the live data exposed)
- **The first real walk-forward artifact is published**:
  `artifacts/accuracy/seasonal_naive_weekly_prices.json` — MAPE **13.42%**, MAE
  **11.60 NOK/kg**, out-of-sample coverage **92.1%** against an 80% nominal interval,
  n=208 year-back pairs over **2021W42..2026W41**, produced from a live SSB fetch.
  `GET /api/accuracy` now returns `published: true`.
- **A latent bug in the publisher surfaced the moment live data arrived:**
  `ssb_price_client.get_price_history` returns `"week": "W42"`, and `_series` called
  `int(row["week"])` → `ValueError`. It had never fired because the earlier run got
  zero observations (the fetch was failing), so the loop never executed. Fixed with
  an explicit `_week_number()` parser plus a regression test covering `"W42"`,
  `"w3"`, `42`, `""`, `None` and `"week"`.
- **Honesty kept, even where it is unflattering:** the artifact is marked
  `fallback_used: true` (it *is* the seasonal-naive baseline the platform falls back
  to — the floor a real model must beat, not a model score), and `docs/ACCURACY.md`
  states that 92.1% coverage against an 80% interval means the interval is
  *conservative* rather than that the forecast is good.



### Step 10 — role definitions, usable immediately
- **Three roles written to be posted as-is** in `docs/roles/`: **Commercial Lead
  (salmon trading networks)** — owns recruiting and converting 5–8 paid 90-day
  pilots, with explicit first-quarter targets and a blunt honesty requirement;
  **Enterprise & Security Engineer (SSO + SOC 2 path)** — owns SSO/SAML/OIDC,
  SOC 2 Type I→II readiness, per-tenant isolation and the production gaps
  (`docs/PRODUCTION_TRUTH.md` "Still open"), with the four-part definition of done
  for SSO; **Product Designer (field & mobile)** — owns the one-handed operator
  loop and honest offline capture, with the degraded-state design mandate.
- Each role states what success looks like in the first quarter as measurable
  targets, what the person needs, what the first 30 days are, and — deliberately —
  **what we will not ask them to do** (hide degraded data, advertise the deferred
  performance fee, write advice framing).
- `docs/roles/README.md` indexes the roles and gives the shared pre-call reading
  list plus the hiring filter: comfort with refusing to claim what we have not
  measured.

### Step 9 — GTM kit (ROI calculator in code, honest sales assets)
- **ROI calculator as real code**, not a slide: `core/gtm/roi.py` computes the case
  for four ICPs (producer, processor, desk, insurer) from formulas it publishes,
  and it **invents no market value** — every figure is either an input the customer
  supplied (`inputs_supplied`) or a clearly labelled assumption
  (`assumptions_used`), each line carrying its own `formula` and `inputs_used`.
  `GET /api/gtm/roi?icp=` shows the default case with the assumptions marked;
  `POST /api/gtm/roi` recomputes with the customer's numbers. `not_included` states
  that integration effort and unverified revenue are out of scope, and the
  disclosure says the platform asserts no market value.
- `GET /api/gtm/kit` lists the assets and the **live proof points** a seller can
  open on a call (`/api/indices`, `/api/accuracy`, `/api/data-freshness`,
  `/api/billing/catalog`, `/api/legal/data-licenses`).
- **Security & architecture one-pager** (`docs/GTM_SECURITY_ONE_PAGER.md`): data
  handling, tenancy/IDOR, SSRF guard, provenance — followed by an explicit
  **"what is NOT in place yet"** table (SSO, SOC 2, pen test, HA, per-tenant
  isolation). It states the principle: the rule that stops us inventing a MAPE stops
  us inventing a certification.
- **3-minute demo script** (`docs/GTM_DEMO_SCRIPT.md`): timed, with the exact words
  for the current "accuracy not yet published" state and a rehearsed objection table.
- **LinkedIn pack** (`docs/GTM_LINKEDIN_PACK.md`): three repeatable formats for a
  domain expert (not marketing), posting rules (never post a number you cannot
  link; never recommend), and eight seed topics.
- **Event playbook** (`docs/GTM_EVENTS.md`): AquaNor/NASF readiness checklist
  (8/4 weeks out), booth kit, the 90-second stand pitch, the 72-hour follow-up
  rule, and a "what NOT to do" list.
- **Tests:** `tests/test_gtm_roi.py` (12) — every line states its formula/inputs and
  is flagged as an assumption, defaults are reported as assumptions while supplied
  inputs are not, the maths is reproducible against hand-computed values, the module
  is checked not to embed upstream market series, validation of unknown ICPs/inputs
  and months, and the endpoint shapes.


- **The provenance boundary is now enforced, not remembered.** New
  `core/provenance_register.py` holds the **formal exempt register** (prefix →
  category + written reason; 18 entries across infrastructure, auth/billing,
  catalogue/meta, publication metadata, operational and admin) and
  `docs/provenance_baseline.json` freezes the non-exempt `/api` GET inventory:
  **238 routes → 31 exempt, 207 baselined, 0 unregistered**.
- **A ratchet so nothing can ship unnoticed:** `scripts/provenance_ratchet.py`
  (exit 1 on drift) plus `tests/test_provenance_ratchet.py`. A new data route must
  either carry provenance or be added to `EXEMPT` with a reason — a route in neither
  fails the gate, and the baseline is re-frozen only via an explicit `--update`.
- **A reusable pattern instead of per-route churn:**
  `core/market/provenance_envelope.py::with_provenance(source, degraded_reason=...)`.
  It attaches `data_provenance` to dict payloads, forces `is_live: false` when a
  degraded reason is given, leaves an existing (engine-set) envelope untouched, and
  passes non-dict results through.
- **Five more real routes carry provenance:** `/api/analytics/yoy-comparison`,
  `/api/treatment/efficacy-by-method`, `/api/feed-supply-chain/eudr-risk` (all
  honest degraded envelopes naming why they are not measurements) and
  `/api/futures/basis`, `/api/futures/term-structure` — where the decorator
  correctly *preserved* the engine's own more specific provenance
  ("SSB Seasonal Synthesis", `is_live: false`) rather than overwriting it.
- **Honest scope:** the register proves a decision was recorded, not that all 207
  baselined routes carry provenance today — the runtime measurement stays in
  `scripts/probe_liveness.py` (payload-shape classification), which the report
  documents. The ratchet prevents silent erosion; the probe reports the live
  residue.
- Docs: `docs/REPORT_LIVENESS.md` now carries the exempt register table, the
  ratchet commands and the list of routes given provenance in this step.


- **Data-licence register** `core/legal/data_licenses.py`: one entry per source with
  `allowed_uses`, `resale_allowed`, `attribution_required`, `ai_training_allowed`
  and named risks. Eight sources registered (Fiskeridir lice, SSB prices, Copernicus,
  NASA MUR SST, Fish Pool/Euronext futures, producer-contributed data, EUDR
  submissions, research literature).
- **It refuses to invent legal conclusions**: every entry defaults to
  `classification_status="pending_legal_review"`, and `check_use()` returns
  `allowed: false` (with `requires_legal_signoff: true`) for any use that has not
  been signed off — even when the licence would permit it. `compliance_summary()`
  therefore reports the honest state: **8 registered, 0 cleared**, and names exactly
  which sources may not be resold (that list is what blocks the Data & Assurance
  tier; `fish_pool_futures` is flagged as blocking any public futures display).
- **Signals-vs-advice boundary** published as structured data with a reusable
  `SIGNAL_DISCLOSER` string for every signal surface, explicit "what we are not"
  clauses and jurisdiction notes.
- **EU AI Act transparency notes** for the three AI systems actually in use
  (forecasting, RAG assistant, anomaly scoring) with per-system transparency,
  human-oversight and limitation-disclosure fields, an honest
  "limited-risk — pending legal confirmation" classification, and the prohibited
  practices we do not use.
- **DPA/GDPR scaffold** (roles, data categories, sub-processors, retention,
  transfers, rights, breach, AI-Act annex) plus the open questions for counsel.
- **Performance-fee deferral as an enforced flag** (`core/legal/performance_fee.py`,
  `FISHINTEL_PERFORMANCE_FEE_ENABLED` default off): the five conditions to enable it,
  the three things prohibited while deferred, and a test asserting **no plan
  advertises a performance fee**.
- **New endpoints:** `/api/legal/data-licenses` (+ `/{source}`), `/use-check`,
  `/advice-boundary`, `/ai-act`, `/performance-fee`.
- **Tests:** `tests/test_legal.py` (18) — register completeness (no duplicate keys,
  every use in the vocabulary, and every source behind a published index traceable
  to a licence entry), nothing cleared without a reviewer, uncleared-but-permitted
  uses refused, unknown source/use handling, resale conflict visibility, the
  deferral default and switch, and all endpoint shapes.
- Docs: `docs/ADVICE_BOUNDARY.md` (boundary, AI Act, DPA template, licences,
  performance fee, and what still needs a human).


- **Pilots are real entitlements, not flags.** `POST /api/admin/partners/{id}/onboard`
  grants a canonical plan through `core.billing.entitlement_sync.activate()` for a
  90-day window, so what a design partner sees is exactly what a paying customer
  gets. No new tier was added — `core/entitlements.py` stays the single plan table
  (rule 8).
- **Two new tables** (Alembic 018): `design_partners` (company, ICP, country, plan
  granted, window, status, paid/monthly price, reciprocity terms) and
  `partner_metrics` (name/value/target/unit/note).
- **Admin surfaces** (`Depends(require_admin)`): create, list (with `by_status` and
  `by_icp` funnel counts and the 5–8 pilot target), detail with the full metric
  history and the allowed status transitions, onboard, metrics, reciprocity, status.
- **Success-metric scorecards**: latest observation vs latest target per metric with
  a computed `achieved` flag — the evidence a pilot conversion is argued from.
- **Status machine enforced** (`prospect → onboarded → active → converted`, with
  `churned` and re-onboarding paths); an illegal transition is a 409, an unknown
  status a 422, and onboarding without an owning user a 422.
- **Data reciprocity** is captured *before* onboarding (dataset names, cadence,
  agreement reference, restrictions) — the mechanism that turns partner data into
  a moat rather than a one-way giveaway.
- **Tests:** `tests/test_partner_pilots.py` (18) — admin gating (anonymous and
  non-admin rejected), create validation, plan-alias normalisation (`pilot` →
  `professional`), onboarding without an owner rejected, onboarding granting a
  *real* entitlement (asserts `User.tier` changed), metric scoring, reciprocity
  requirements, and the status state machine.
- **A real bug found by the tests:** `days_remaining` was always `None` because
  SQLite returns datetimes naive, so the awareness check failed — fixed with a
  coercion helper (same class of bug that hit the freshness monitor).
- Docs: `docs/DESIGN_PARTNERS.md` — the runbook, the status machine and the
  per-ICP success metrics that decide conversion.


- **Agents are a first-class production service.** `docker-compose.prod.yml`
  declares `api` + `agents` (`python main.py --agents-only`) + `db` (TimescaleDB)
  + `web`, with required-secret guards (`:?`) so a misconfigured deploy fails at
  `up`. Previously the production image ran API-only and all 12 agents (ingest,
  forecasts, index publication) silently never executed.
- **`core/production_truth.py` + `scripts/verify_production_truth.py`** turn the
  documented gaps into checks with verdicts: production env + JWT secret length,
  agents service present, DB dialect/reachability/**migration head**, model +
  accuracy artifacts, and per-source freshness. Exit 1 on a critical failure, so it
  can gate a deploy.
- **It immediately caught a real drift:** this repository's dev DB had an EMPTY
  `alembic_version` (`DB at None, code head 017`). `tests/conftest.py` now
  reconciles missing ORM columns *and* stamps head for `create_all`-built dev/test
  DBs, while real deployments keep failing if they are behind. Re-run now reports
  `alembic_head: at head 017` with 0 failures.
- **TimescaleDB:** `docker/init-timescale.sql` creates the extension (plus helping
  indexes for the freshness queries). Hypertable conversion is deliberately *not*
  automated — it needs a real time column and a correct chunk interval, and a wrong
  conversion silently degrades plans; the verifier reports the count so "not yet
  converted" stays visible.
- **Per-source freshness dashboard:** `core/market/freshness_monitor.py` monitors
  12 sources (lice, SSB prices, export volumes, chlorophyll, bloom, futures,
  supply, price predictions, harvest timing, published indices, treatment outcomes,
  EUDR) with latest observation, staleness vs expected cadence and a concrete
  refresh hint. `GET /api/data-freshness` (public) and `/sources`. **A real bug was
  found by running it:** SQLite returns timestamps as ISO **strings**, so every
  source reported `unknown` until coercion was added.
- **Synthetic-data disclosure:** a source whose table holds only demo/seed rows is
  reported as `synthetic_only` — the dev DB's `ssb_weekly_prices` (52 demo rows) is
  correctly flagged rather than presented as live data.
- **Tests:** `tests/test_production_truth.py` (17) — agents declared in prod compose
  and the API-only topology flagged as a critical failure, production secret rules,
  alembic head = 017, artifact absence declared not hidden, freshness statuses,
  missing-table → unknown, synthetic-only flagging, timestamp coercion and the
  endpoints.
- Docs: `docs/PRODUCTION_TRUTH.md`; AGENTS.md known-gaps register updated.


- **`core/ml/accuracy_registry.py`** is the artifact store that makes the honesty
  rule operable: JSON artifacts under **`artifacts/accuracy/`** (tracked in git,
  deliberately not under the gitignored `data/`), validated against a published
  schema on both write *and* read — invalid artifacts are reported, never skipped.
- **`scripts/publish_accuracy.py`** produces a genuine artifact from a real
  walk-forward evaluation (seasonal-naive baseline on SSB weekly prices), with the
  prediction interval calibrated on the first 70% of year-back pairs and coverage
  measured **out-of-sample** on the remaining 30%.
- **A real honesty trap was found and closed:** the environment could not reach
  SSB, and the only locally persisted `ssb_weekly_prices` rows (52 of them) carry
  `source='demo_seed'` — i.e. synthetic. Publishing a MAPE from those would have
  fabricated an accuracy claim, so the script now filters on source, reports how
  many synthetic rows it ignored, and **exits non-zero writing nothing** when only
  synthetic data exists. Consequently `GET /api/accuracy` honestly returns
  `published: false` and names the command that fixes it.
- **New endpoints:** `GET /api/accuracy` (published metrics or an explicit
  not-yet-published statement), `/api/accuracy/method` (the artifact contract,
  evaluation protocol and prohibited practices), `/api/accuracy/artifacts/{id}`
  (verbatim, for audit).
- **Fallback disclosure is machine-readable**, not fine print: the response states
  the seasonal-naive fallback policy, whether foundation models are actually
  available (`torch` present) and whether a legacy gitignored `data/` artifact
  exists — noting that only the published registry may back a public claim.
- **Frontend:** public `/accuracy` page rendering published metrics, the
  not-published state with the publish command, and the fallback disclosure.
- **Tests:** `tests/test_accuracy_registry.py` (27) — schema validation (including
  each invalid-field class), publish/read-back, invalid files reported not hidden,
  empty registry claims nothing, the synthetic-source guard, determinism of the
  walk-forward maths on a known series, and every endpoint's honesty behaviour.
- Docs: `docs/ACCURACY.md`.


- **`AI-STI` (AquaIntel Salmon Transmission Index)** and **`AI-LPI` (AquaIntel Lice
  Pressure Index)** are published, versioned (method `1.0.0`) and reproducible:
  weighted component scores with published weights and scoring formulas, explicit
  component-level source attribution, and a **renormalising** aggregation — a
  component whose source is unavailable is named in `components_missing` and
  forces `provenance.is_live = false`. If *every* component is unavailable the
  index returns `value: null` instead of a fabricated number.
- **Sources are real:** Fiskeridir/SSB standing biomass and harvest (momentum vs
  year-over-year, with `raw.basis` when a year-back period is missing) and the lice
  emission-quota framework (`lice_quota_tracker.national_emission_overview`).
- **Bio→Price Weekly v1** (`core/market/bio_price_weekly.py`,
  `GET /api/indices/bio-price-weekly`): composes both indices with a supply panel
  and a live price panel into a weekly digest with an explicit
  `transmission.read`, a `caveats` list and a provenance block. `publish_week()`
  computes **and stores** both observations.
- **History is durable and immutable:** new `index_observations` table (Alembic
  017) with a unique constraint on `(index_code, week, version)`, so a published
  value cannot be silently restated and a method change is visible as a new
  version.
- **New endpoints:** `GET /api/indices`, `/ai-sti`, `/ai-lpi`,
  `/{code}/history`, `/methodology`, `/bio-price-weekly`, and admin
  `POST /api/indices/publish` (stable public permalinks `/indices/ai-sti`,
  `/indices/ai-lpi`).
- **Frontend:** public `/indices` page showing value, band, per-component weight
  and score, source, method version and a live/degraded badge with the degradation
  reason — the honesty layer made visible to a buyer.
- Docs: `docs/INDICES.md` publishes the full method, weights, bands, revision
  policy and limitations (including what is deliberately *not* yet a component).
- **Tests:** `tests/test_indices.py` (20) — method/version/weights contract, bands,
  per-component traceability, honest degradation (partial and total), idempotent
  history publishing, stable permalinks, 404 for unknown indices, and the digest's
  caveat/provenance coupling.


- **One catalog, one entitlement write.** `core/billing/stripe_catalog.py` derives
  the Stripe Products/Prices from `core/entitlements.py` (idempotent
  create-or-find), and `core/billing/entitlement_sync.py` is the single place a
  billing event becomes an entitlement — used by the real webhook **and** the
  mock path, so a paid plan cannot land differently depending on the door.
- **`stripe_billing.TIER_PRODUCTS` was a *third* tier table** (it drifted from
  `core/auth.py` and `core/valuechain/subscription.py`); it is now derived from
  the SSOT too.
- **Mock mode is explicit, never silent.** Without `STRIPE_SECRET_KEY` the catalog
  serves deterministic `price_mock_<plan>` ids with `"mock": true`, checkout
  returns a mock URL, and `POST /api/billing/webhook/mock` completes the chain
  (refused in production, token-guarded when `FISHINTEL_MOCK_BILLING_TOKEN` is
  set). The pricing page shows a banner instead of pretending prices are live.
- **Server-side plan resolution.** The webhook resolves the plan from the **price
  id** first, then metadata; both `aquaintel_plan` and the legacy `openclaw_tier`
  are read and written, so existing Stripe objects keep working.
- **New endpoints:** `GET /api/billing/catalog` (public pricing model),
  `POST /api/billing/webhook/mock`; checkout now accepts `?plan=<canonical key>`
  (legacy `?tier=` still works) and 400s on non-self-serve plans.
- **Public pricing page** `frontend/src/app/pricing/page.tsx` driven entirely by
  `/api/billing/catalog` (no hardcoded feature list), plus `api.billingCatalog()`
  and `api.billingCheckout()`.
- **Fixed a production-blocking schema drift:** the dev DB was missing
  `subscriptions.stripe_customer_id` (present in migration 002 but never applied
  to this box). `tests/conftest.py` now reconciles missing ORM columns
  automatically (the manual PRAGMA/ALTER loop AGENTS.md documents), and prints
  what it added — this is what makes the money-path tests deterministic.
- **Tests:** `tests/test_billing_money_path.py` (12) proves the full chain —
  catalog → checkout → webhook → entitlement → **the previously-blocked premium
  route now returning non-402** — plus persistence, cancellation → free,
  non-self-serve rejection, auth requirement and mock-token enforcement. No Stripe
  credentials required.
- Docs: `docs/BILLING.md`; `.env.example` gains the mock-billing vars and a note
  that the catalog is auto-created.


- **New `core/entitlements.py`** is the only definition of plans, prices, quotas,
  features and the paywall boundary. `core/auth.TIERS` and
  `core/valuechain/subscription.TIERS` are now *projections* of it.
  Before: `/api/tiers` imported **both** tables and served a merged,
  self-contradictory payload, and `intelligence` (present in one table only)
  silently ran on the **free** quota while priced at NOK 39,900/month.
- **7 canonical plans** — Insight (free), Operator, Desk (professional),
  Enterprise, Investor, Intelligence, plus the licensed Data & Assurance tier.
  The monthly limit is **derived** from the enforced per-day quota
  (`api_calls_per_day × 30`), removing the drift source. Legacy keys are kept for
  issued tokens/Stripe metadata; aliases (`premium`, `pro`, `pilot`, `growth`,
  `licence`, `market`, `institutional`, …) resolve via `normalize_plan()`.
- **Paywall enforced** for authenticated accounts on a curated
  `PREMIUM_PREFIXES` set (price outlook/forecast, futures, AIS, supply balance,
  contracts, event impact, harvest optimizer, feed supply chain, ensemble,
  compound scenarios, premium indices) → **402 + actionable upgrade payload**
  (`current_plan`, `suggested_plan`, `upgrade_url`). Anonymous browsing stays
  open — that is the funnel, and it is now the documented policy rather than an
  accident.
- **Gating and quota have independent kill-switches**
  (`FISHINTEL_ENFORCE_ROUTE_GATING`, `FISHINTEL_ENFORCE_QUOTAS`). The first
  implementation nested gating inside the quota switch, so a suite-wide
  `ENFORCE_QUOTAS=0` silently disabled the paywall — caught by the new tests and
  restructured.
- **New endpoints**: `GET /api/entitlements/plans` (public pricing model),
  `/me` (caller's plan, usage, upgrade path), `/check?path=` (UI affordances).
- **Alembic 016** normalises legacy tier strings in `users`, `subscriptions`,
  `api_keys` and `performance_fees` to canonical keys, so a row holding
  `"premium"` cannot silently fall back to the free quota.
- **Tests**: `tests/test_entitlements.py` (47 tests) proves the two projections
  agree, the monthly figure is derived, both tier endpoints agree, `intelligence`
  has its own quota, alias resolution, the paywall policy, the 402/429 payloads
  and the kill-switches. The assertions in `tests/test_tier_quota.py` that
  *pinned the conflict* were replaced.
- Docs: `docs/ENTITLEMENTS.md` (model, policy, endpoints, enforcement, migration,
  known limitations).



### Added
- `scripts/probe_liveness.py` — walks every parameterless GET route in-process
  and records the provenance it ACTUALLY returns (live / degraded / simulated /
  no_provenance / error). Writes `docs/REPORT_LIVENESS.md` +
  `docs/liveness_report.json`. Measurement, not assertion: 219 routes probed.
- `tests/test_route_liveness_contract.py` — deterministic guards for every bug
  the audit found (no network required).

### Fixed (crashes the audit surfaced — 6 defect classes across 9 endpoints, none covered by the suite)
- `core/routers/billing_routes.py` (x4): called `get_current_user(creds)` while
  the signature is `(request, credentials)`, so `credentials` stayed a `Depends`
  object — every billing endpoint raised AttributeError instead of returning 401.
- `compliance/compliance_agent.py`: `/api/audit` read non-existent
  `AuditLog.event_type` / `actor` / `detail` (500). Maps `action` / `user_id` /
  `details`.
- `core/routers/analytics_routes.py`: `/api/self-improvement/proposals` queried
  `AuditLog.event_type` and read `l.detail` (500).
- `core/routers/alerts_routes.py`: `/api/parametric/risk-profile` never awaited
  the async engine, returning a coroutine (500).
- `core/market/lice_quota_tracker.py`: queried `Locality.company`, which does not
  exist (the column is `owner_company`) — every production area silently
  returned an empty list.
- `core/market/efficacy_marketplace.py`: PostgreSQL-only
  `EXTRACT(... FROM ...)` raw SQL raised OperationalError on SQLite, so
  `/api/efficacy/*` failed in dev and CI.

### Fixed (honesty — AGENTS.md rules 1 and 3)
- `core/market/fiskeridir_biomass.py`: `_generate_fallback()` produced
  `random.uniform` placeholders with `report_year` set, so `is_live` was True and
  `get_national_summary()` reported `DataProvenance.live(..., confidence=0.95)`
  for randomly generated data presented as "Fiskeridirektoratet". Fallback
  records are now flagged `is_synthetic` and provenance is `simulated`
  (confidence 0.0) unless the ArcGIS feed really answered.
- `core/market/biomass_tracker.py`: `fetch_biomass_data()` ALWAYS returned the
  hardcoded historical-pattern estimate while its docstring claimed it fetched
  from Fiskeridirektoratet. It now prefers the real ArcGIS client and records
  which path ran; `/api/market/biomass` emits honest provenance (never `live`,
  because its supply metrics are model estimates).

### Fixed (frontend)
- `frontend/src/lib/api.ts`: the client sent NO `Authorization` header and
  nothing read the token stored at login, so user-scoped routes (billing, API
  keys, webhooks) and the per-user tier quota were unreachable from the UI. The
  stored JWT is now attached, and a 401 clears a stale token and routes to
  `/login` once. Keys exported as `AUTH_TOKEN_KEY` / `AUTH_USER_KEY`.
- `/market` gains a Biomass Supply Tracker card that labels its derived figures
  as estimates and renders the backend's own provenance reason.

### Changed (provenance coverage sweep — AGENTS.md rule 3)
- The liveness audit found **90 routes returning data with no provenance envelope
  at all**. This increment fixes the highest-value cluster: **10 `/api/market/*`
  routes** (`price-forecast`, `seasonal`, `exports`, `price-outlook/multi`,
  `futures-curve`, `ssb-price-history`, `ssb-seasonal`, `export-destinations`,
  `spot-price`, `forward-curve`) and the shared `core/market/price_feed_hub.py`
  they call. Live is claimed only when SSB actually returned rows
  (`DataProvenance.from_records`); model paths (forecasts, synthesized forward
  curves, seasonal baselines) are `degraded` with an explicit reason.
- `not covered here`: `hedger-signals` / `prediction-history` return bare arrays
  pinned by e2e contracts (`api-contracts.spec.ts`), so adding an envelope needs
  a coordinated contract change; `feed-status`, `/api/health`, `/api/metrics`,
  `/api/auth/*`, `/api/tiers`, `/api/disclaimer` are plumbing/config where a
  provenance envelope is not meaningful. The remaining backlog is listed in
  `docs/REPORT_LIVENESS.md`.


### Changed (provenance coverage sweep, increment 2 — ais / sentiment / production)
- 5 more dict-returning routes now carry provenance: `/api/ais/harvest-intelligence`
  and `/api/ais/supply-intelligence` (live only when AIS positions were actually
  ingested), `/api/sentiment/summary` and `/api/sentiment/poll` (live only when
  articles were analysed), and `/api/production/summary` (Fiskeridirektoratet
  open data). Additive keys only; a shared `_ais_provenance` helper reuses the
  `from_records` primitive.
- `scripts/probe_liveness.py` now records each response's payload shape, so the
  remaining backlog is classified rather than guessed: of the 72 provenance-less
  routes, **41 are dict-shaped** (fixable with an additive key) and **30 are
  list-shaped** (a bare array cannot carry an envelope — that is a coordinated
  contract change: frontend auto-unwrap, `e2e/api-contracts.spec.ts`, and the
  Linux-generated visual baselines the repo forbids regenerating on Windows).
- Measured: `no_provenance` 83 → 72, `live` 43 → 46, `degraded` 21 → 27.
  (Counts also move with network availability — 57 rows timed out this run.)


### Changed (provenance sweep, increment 3 — global / parametric / investor / ocean)
- 10 more dict-returning routes now carry provenance. `/api/global/{farms,lice,
  bloom-risk,disease-geo}` share a `_global_geo_provenance` helper (live only when
  at least one country monitor actually contributed a GeoJSON feature — these
  routes swallow per-source failures). `/api/ocean/forecast` is live only when
  MET.no returned forecast points. `/api/parametric/{dashboard,risk-profile}` and
  the three `/api/investor/event-impact/*` routes are `degraded` with explicit
  reasons (derived trigger/payout models and modelled counterfactuals are
  estimates, not quoted prices or observed market moves).
- `not covered here`: `/api/parametric/triggers` turns out to return a bare
  **list** (the probe had classified it as a dict), so it joins the list-shaped
  backlog along with `/api/ocean/currents/status` and `/api/ocean/waves/status`
  (client-status metadata, where a provenance envelope would be meaningless).
- Measured: `no_provenance` 72 → 65, `live` 46 → 53, `degraded` 27 → 30.

### Changed (provenance sweep, increment 4 — the remaining additive half + a latent bug)
- 12 more dict-returning routes carry provenance, closing the additive half of
  the backlog: `/api/farm-graph/{summary,map-data}`, `/api/ras/{summary,timeline}`,
  `/api/regulatory/traffic-light/{simulate,all-scenarios}`, `/api/climate/projections`,
  `/api/contracts/hedge-signals`, `/api/twin/status`, `/api/feed-cost/official-history`,
  `/api/anomaly/alerts`, `/api/self-improvement/proposals`. Model artefacts
  (networks, projections, scenarios, contract risk, detectors) are `degraded` with
  explicit reasons; the **digital twin** is honestly `simulated` (it is a
  simulation of farm cohorts, not measured data); official Fiskeridirektoratet
  series use `from_records`.
- **Bug found while probing**: `core/market/climate_risk_engine.py` queried
  `BloomRiskAssessment.sst`, but the column is `sst_value` — every climate
  projection silently degraded. Fixed.
- Measured: `no_provenance` 65 → **50**, `degraded` 30 → 42, `simulated` 1.
  (`live` reads 53 → 48 only because 60 rows timed out this run vs 52 — network
  variance, not a regression.)
- Known remaining dialect gap (documented, not fixed): the same function groups by
  SQLite-only `func.strftime("%Y-%m", ...)`, which will not compile on the
  PostgreSQL production target.

### Changed (docs truth pass)
- `PROJECT_STATUS.md`: measured counts (322 operations / 316 unique paths, 762
  tests) and real frontend versions (Next 16.4, React 19.1).
- `docs/NEXT_STEPS_PLAN.md`: clone path `AquaIntel` -> `FishIntel`.
- `docs/RESEARCH_SYNTHESIS.md`: the sync-`Session` claim is marked RESOLVED
  (0 core files import `sqlalchemy.orm.Session`).
- `docs/DEPLOYMENT.md` + `docker-compose.staging.yml`: agents run as a SEPARATE
  service (staging parity); single-container deployments otherwise never ingest
  data.


## [2.3.0] — 2026-10-13 (post-review hardening session)

### Fixed (review H1 — rate limiting was configured but never enforced)
- `core/api.py` now registers `SlowAPIMiddleware`: the `Limiter` (default
  `200/minute`, moving-window) previously existed alongside the 429
  handler but was never wired — zero routes were actually limited.
- The middleware is registered **before** `CORSMiddleware` (later
  `add_middleware` calls wrap earlier ones), so CORS stays outermost and
  429 responses still carry CORS + security + correlation headers.
- `headers_enabled=True`: `X-RateLimit-*` + `Retry-After` are now emitted
  so API clients can self-throttle.
- Default limit is env-tunable (`FISHINTEL_RATE_LIMIT`, default
  `200/minute`) — no code change needed for load testing.
- New `tests/test_rate_limit.py` (9 tests): middleware-wiring regression
  net, burst → 429, 429 body + rate-limit headers, 429 keeps outer
  middleware headers, per-key bucket isolation, `_get_rate_limit_key`
  bucketing (X-API-Key / bad-Bearer-falls-back-to-IP / anonymous IP).
- Test-suite/CI safety: `tests/conftest.py` raises the limit before
  `core.api` import (the suite makes ~240 requests from one TestClient
  IP); `FISHINTEL_RATE_LIMIT` added to the `test.yml` pytest step and the
  `frontend.yml` e2e backend. Production default stays 200/minute.

### Fixed (review H2 — tier/paywall claims without enforcement)
- New `core/tier_quota.py` + `TierQuotaMiddleware` (registered in
  `core/api.py`): `TIERS[tier]["api_calls_per_day"]` is now actually
  enforced for authenticated API usage (Bearer JWT or X-API-Key) with a
  structured 429 (`tier_quota_exceeded`, tier, quota, `Retry-After`) once
  the per-UTC-day allowance is exhausted. Per-user buckets;
  `/api/auth/*`, `/api/health`, `/api/billing/*` never consume quota;
  unknown/`<= 0` quotas mean unlimited; kill-switch
  `FISHINTEL_ENFORCE_QUOTAS=0` (on by default in production).
- Honest scope, explicitly documented everywhere: anonymous "public
  demo" traffic is NOT quota-gated (the site stays publicly browsable
  under the global rate limiter), and route-level tier gating (TIERS
  route allow-lists) is NOT enforced yet.
- Honest tier surfaces: `/api/auth/tiers` and `/api/tiers` now report
  `daily_quota_enforced: true` and `route_gating_enforced: false` per
  tier (additive; `/api/tiers` also mirrors the actually-enforced figure
  as `enforced_api_calls_per_day` — its legacy `api_calls_limit` is a
  monthly figure from `core/valuechain/subscription.py` that is NOT what
  is enforced, and tiers unknown to `core/auth.py` fall back to the free
  quota). `docs/openapi.frozen.json` re-frozen (2-line description diff
  only; no paths/schemas changed).
- Frontend `/settings` and `/billing` pages now carry an explicit
  enforcement note (quotas enforced for authenticated API usage;
  route-level gating not yet enforced during beta).
- Dead code removed: `core/auth.require_tier` (zero callers, minimum-tier
  semantics superseded by the documented allow-list model);
  `check_tier_access` kept and pinned with unit tests as the predicate
  the future paywall middleware will use.
- New `tests/test_tier_quota.py` (20 tests): wiring, free/professional
  quotas, per-user buckets, tier-alias resolution, anonymous
  pass-through, auth/health/billing exemption, invalid-credential
  pass-through, env kill-switch, tier-surface honesty flags, and the
  `check_tier_access` allow-list logic.
- CI/test-suite safety: `FISHINTEL_ENFORCE_QUOTAS=0` in
  `tests/conftest.py` + both CI workflows (same pattern as the rate
  limit); enforcement verified explicitly in the new tests.

### Fixed (review H4 — /china-demand printed "estimates shown" while nothing was shown)
- `frontend/src/app/china-demand/page.tsx`: the supplier note and the
  "Data Sources" footer now render only when a snapshot is actually on
  screen (and, for the supplier note, when supplier rows are listed) —
  no provenance claim while loading or after a total fetch failure.
- Distinct fetch-failure state (`snapshotError`): a rose banner states
  exactly what happened ("Failed to load China demand data — no figures
  are currently shown…" / on a failed refresh: "showing the previously
  loaded snapshot") with a Retry button — instead of the old false
  "SSB series unavailable; shown from curated estimates" text.
- New `frontend/e2e/china-demand-honesty.spec.ts` (4 tests, all
  /api/china/** stubbed — no backend needed): loading (gated in-flight
  fetch → no claims), fetch failure (404 → error banner, zero estimate
  claims), live snapshot (LIVE SSB claims shown), degraded snapshot
  (curated-estimate claims shown only because data IS shown).
- e2e tooling fix discovered on the way: the PWA service worker
  (`public/sw.js`) takes over all GET fetches once active and its
  fetches BYPASS `page.route` — stubbed routes silently stopped
  intercepting (observed: stubbed /api/china/demand answered 503
  "Offline" with zero route-handler hits). New
  `blockServiceWorker()` helper in `frontend/e2e/utils.ts` (stubs
  `navigator.serviceWorker.register`; PWARegister swallows the error)
  keeps route stubs reliable for stubbed specs.
- Visual baselines unaffected (`/china-demand` has no baseline; the
  stubbed-routes pattern matches `visual.spec.ts`).

### Fixed (review M1+M3 — liveness keyed on rounded tonnage, contradicting the documented invariant)
- `core/routers/country_routes.py::_china_provenance` and
  `core/market/supply_demand_engine.py::_demand_context`: the
  `or norway.get("tonnes_12m")` clauses are gone — LIVE/degraded is now
  keyed exclusively on records actually returned (`monthly_series`),
  never on a rounded tonnage that can legitimately be 0.
- `tests/test_china_provenance.py::test_live_when_tonnes_present` repinned
  to `test_tonnes_without_records_is_degraded` (tonnes alone → degraded).
- Structured `norway_exports_to_china.is_live` field added to the engine's
  snapshot (additive under `API_SCHEMA_VERSION` 1.1; mirrors the
  records-based `norway_live` in `_format_snapshot`), pinned by new engine
  tests; `docs/openapi.frozen.json` re-frozen — no diff (untyped dict).
- `frontend/src/app/china-demand/page.tsx` now consumes the structured
  `is_live` contract instead of parsing the display string
  (`String(data_source).startsWith("LIVE")`); the e2e honesty stubs carry
  the new field.
- New `TestDemandContextLiveness` in `tests/test_supply_demand_engine.py`
  (fake china engine, no network): tonnes-without-records →
  `china_live_data: false`; records returned → `true`.

### Fixed (review L1 — inconsistent None-guard; follow-up from M1)
- `supply_demand_engine._demand_context` now uses the same
  `(snap or {})` guard as the line above (the `norway` local is gone with
  the dropped clause).

### Fixed (NEW finding — /trader typing + feed composite fiction, slice 10)
- `/trader` was fully `any` (16); typed against the real endpoints.
  `priceOf` gained a small structural `CurvePointLike` type.
- **Feed-cost composite KPI was dead**: the page read
  `feedIndex.composite_index` / `.alert` — the real payload
  (`feed_cost_engine.compute_composite_index`) emits `current_index` /
  `current_date` / `volatility_alert` / `volatility_12m`. KPI now renders
  `current_index` + a volatility-alert delta.
- New client types for five previously-untyped APIs:
  `MarketSpotPrice`, `MarketForwardCurve` (+`ForwardCurvePoint`),
  `FeedCostCompositeIndex`, `EventImpactResult` (+`EventCompanyImpact`),
  `SavedScenario`; `signals()` now returns `Signal[]` (a dead
  `{signals}` fallback removed from the trader + chat pages).
- `SentimentSummary` gained the real `signals` key (`SentimentSignalRow`).
- `/trader` fully typed (16 `any`s → 0, eslint-disable removed);
  error rendering uses an `"error" in result` discriminator; dead
  `predicted_price` / `pt.label` aliases removed.
- Regression nets: 5 backend tests (`TestTraderContracts` incl. a
  save/list/delete scenario round-trip) + 4 e2e contract assertions
  (spot-price, forward-curve, composite-index real keys,
  event-impact/isa envelope). tsc clean, eslint 0 errors (6 pre-existing
  warnings), visual 4/4, targeted tests 12 passed, ruff clean, build green.

### Fixed (NEW finding — /competitiveness type fiction, slice 9)
- `CompetitivenessIndex`/`CompetitivenessOrigin` were fiction
  (`production_cost_nok_kg`, `freight_cost`, `tariff_usd_percent`,
  `total_cif_usd_kg`, `competitiveness_vs_norway`, `insights` on the
  origin row — none of these exist). The real payload (from
  `competitiveness_engine._to_dict`) carries `us_spot_usd_kg`,
  `data_quality: "live" | "stale_fallback"`, `fallback_value`,
  `source_date` and origins with `rank/flag/currency/local_cost_per_kg/
  fx_rate_to_usd/production_cost_usd/tariff_pct/tariff_cost_usd/
  freight_usd/total_delivered_usd/margin_usd/margin_pct`. Rewritten.
- `competitivenessTariffScenario` was untyped; added
  `CompetitivenessScenarioResponse` (`scenario_origins` with
  scenario_rank/delivered_cost_usd/rank_change/baseline_rank) and
  annotated the client.
- Scenario row also read a nonexistent `o.origin` (falling back to
  `o.country`) — now reads `o.country` directly.
- `/competitiveness` fully typed (15 `any`s → 0, eslint-disable removed;
  `DataTable` columns typed as `Column<CompetitivenessOrigin>`).
- Regression nets: 2 backend tests (`TestCompetitivenessContract`) + 2 e2e
  contract assertions (origin-index real keys incl. old-fiction
  must-not-exist, tariff-scenario re-ranking). Local verification:
  tsc clean, eslint 0 errors, visual 4/4, targeted tests 7 passed,
  ruff clean, build green. Warnings are pre-existing only.

### Fixed (NEW finding — /investor typing + GlobalSupply fiction, slice 8)
- The `GlobalSupply` type was fiction (`countries[].production_2025_kt`,
  `total_global_kt` — neither exists in the payload) while the page and
  KPI strip read the real `balance`, `supply_deficit_pct`,
  `norway_premium_pct`, `global_salmon_usd_kg`. Rewritten to match
  `global_supply_engine.to_dict` (incl. `GlobalSupplyCountry`).
- `DiseaseCompanyCounts` keys are lowercase (`isa`/`pd`) but the investor
  page read uppercase `ISA`/`PD` — **disease counters always rendered
  "Clear"** even when outbreaks existed. Page now reads `isa`/`pd`.
- `equityPrices`, `regimeStates`, `esgScores` were untyped; added
  `EquityPriceResponse` and `RegimeState` types (real shapes from the
  routes) and annotated the client; `esgScores` now returns
  `EsgCompanyScores`.
- `/investor` fully typed (18 `any`s → 0, eslint-disable removed);
  `DashboardSupply` is now an alias of the corrected `GlobalSupply`
  (the dashboard layer used to re-patch the fiction with optional
  overrides).
- Regression nets: 5 backend tests (`TestInvestorContracts`) + 5 e2e
  contract assertions (global-supply, disease by-company lowercase keys,
  regime states, equity prices, esg scores).
- Local verification: tsc clean, eslint 0 errors, visual 4/4,
  test_routers 56 passed, ruff clean, build green.

### Fixed (NEW finding — /brief + anomaly contract fiction, slice 7)
- `MorningBrief` / `BriefSection` types were fiction (`title`, `key_risks`,
  `market_sentiment`, `sections[].items[]`, `section_num`) while the real
  response model is `{generated_at, greeting, market_mood, top_insight,
  sections[{title, icon, headline, detail, sentiment, value}]}`. The page
  itself already read the real keys — now the types match it.
- `AnomalyScores` type was fiction (`lice_zscore`/`lice_risk`/
  `mortality_risk`/`sst_anomaly`) — the real payload is
  `{composite_score, risk_level, n_anomalies, summary, anomalies[],
  component_scores{}}` (no consumer read the fictional keys).
- `/brief` page fixes that fell out of typing:
  - the Early Warning card read `anomalyData.breakdown` (nonexistent) →
    the **Key Risks bars never rendered**; now uses the real
    `component_scores`;
  - source attribution read a nonexistent `anomalyData.sources` array →
    now derives from the real `anomalies[].source`;
  - `FeedCostLatest` type said `trend` while the payload emits
    `margin_trend` (the Feed Pressure delta never showed) — corrected.
- `/brief` fully typed (21 `any`s → 0, eslint-disable removed);
  `ScoredSection` documents the page-local `_priority` field.
- Regression nets: 2 backend tests (brief response-model keys, anomaly
  component breakdown) + 3 e2e contract assertions (brief, anomaly,
  feed-cost incl. documented 404).
- Local verification: tsc clean, eslint 0 errors, visual baselines 4/4,
  test_routers 51 passed, ruff clean, build 68/68.

### Fixed (NEW finding — /feed-supply-chain typing + hand-rolled provenance, slice 6)
- `/api/feed-supply-chain/summary` now carries the platform
  **DataProvenance** shape: it used to hand-roll
  `{source, freshness: "model_based", confidence, note}` — no `is_live`,
  no `fallback_reason`. It is honestly **degraded** (model-based
  composition with approximate commodity prices — never live), with the
  reason attached; the page footer keeps reading source/confidence.
- `/feed-supply-chain` fully typed (24 `any`s → 0, eslint-disable
  removed): new `FeedSupplyChainSummary` / `FeedCompositionRow` /
  `FeedScenarioRow` / `FeedEudrRisk` / `FeedSankey{Node,Link}` types;
  `api.feedSupplyChainSummary` typed.
- Two real display bugs fixed while typing:
  - the cost-breakdown list called `.sort()` **on the state array**
    during render, mutating the payload and re-ordering the stacked bar /
    legend above it — now sorts a copy;
  - the Sankey component read a nonexistent `data.stages` array (so stage
    labels never rendered) — labels now derive from the backend's
    documented staging (origin → ingredient → feed mill → farm).
- Regression nets: backend test pins the standardized provenance
  (`is_live: false` + `fallback_reason` + `schema_version`) and the
  payload keys; e2e assertion against the real backend.
- Local verification: tsc clean, eslint 0 errors, visual baselines 4/4,
  test_routers 49 passed, ruff clean, build 68/68.

### Fixed (NEW finding — /disease contract fiction + permanently-green PA displays, slice 5)
- `/disease` typed and corrected against the real Mattilsynet payloads:
  - The **ISA/PD KPI counters were always 0** — they matched `disease ===
    "ISA"`/`"PD"` while the API sends display names ("Infectious Salmon
    Anaemia (ISA)"). Now matched on the display names (case-insensitive).
  - **The PA 1–13 status grid and the PA heatmap could never colour a
    cell**: the outbreak payload identifies cases per *locality* and
    exposes no production-area field, so both rendered a permanently
    "Clear"/0 picture. The grid is replaced by a real **"Active Cases by
    Disease"** breakdown (from the payload's `by_disease` counts) and the
    heatmap by an explicit *Unavailable* card that states why (no PA field
    in the source) — no invented PA data.
  - Global alert rows read `a.date` (real key `report_date`) — the date
    never rendered; also `a.type` (nonexistent) removed.
  - Outbreak rows read `c.disease_type`/`c.locality`/`production_area`
    (none exist) — now the real `disease`/`locality_name`.
  - Types corrected/added: `DiseaseNorway`, `DiseaseOutbreak`,
    `DiseaseAlerts`/`DiseaseAlertRow`, `DiseaseTreatments`/
    `DiseaseTreatmentReport`; the `YoYComparison` type was fiction
    (`{current: number[], delta_pct}`) → real per-week
    `{current_year: [{week, value}], previous_year, two_years_ago}`.
  - `api.diseaseAlerts/diseaseTreatments/yoyComparison` now typed; page
    eslint-disable removed (0 `any`).
- Regression nets: 4 new backend-backed `api-contracts.spec.ts`
  assertions (norway `by_disease`+outbreak keys, alerts `report_date`,
  treatments rows, yoy week/value series).
- Local verification: tsc clean, eslint 0 errors, visual baselines 4/4,
  routers + api_routes green, build 68/68.

### Fixed (NEW finding — disease/leaders/compare contract fiction, slice 4)
- **`/api/disease/by-company` envelope corrected** (same class as
  smolt-forecast): `data_provenance` used to be injected INTO the
  per-company map — a provenance object appearing as if it were a company
  (and consumers summing over it). Now
  `{companies: {name: {total, isa, pd, other, localities}}, count,
  data_provenance}`. Consumers updated: dashboard count, `/disease`
  (its company list was silently EMPTY — it read `byCompany.companies` as
  an array and `c.company` which never existed), `/leaders`, `/investor`,
  `/compare`.
- **`LeaderEntry` type corrected**: it described a nonexistent shape
  (`company_name`/`lice_avg`/`production_tonnes`/`lice_percentile`/
  `esg_score`/`verdict`) while the real `/api/leaders/top100` rows are
  `name`/`avg_lice`/`performance_score`/`production_volume_tonnes`/… —
  `/compare` now consumes the real typed rows.
- **`/compare` fully typed** (29 `any`s → 0, eslint-disable removed):
  typed company selector props, ESG cache (`EsgCompanyScore`), disease map
  (`DiseaseCompanyCounts`), radar datasets; fixed the ESG radar/score
  reading `total_score` (the real key is `total` — the ESG radar dimension
  silently fell back to 0.5 for every company).
- New `EsgCompanyScore` type + typed `api.esgCompany`.
- Regression nets: backend test pins the disease envelope (incl. "no
  provenance object masquerading as a company") + e2e assertion against
  the real backend.
- Local verification: tsc clean, eslint 0 errors, visual baselines 4/4,
  test_routers 48 passed, ruff clean.

### Fixed (NEW finding — /price-outlook + /scenarios contract fiction, same class as A1/A2)
- `/price-outlook` sub-sections read invented fields; typed the page and
  corrected them:
  - Prediction Track Record read `date`/`actual`/`error_pct` — real rows
    (`PricePrediction`) have `created_at`/`current_spot_nok`, so every row
    showed "Actual: 0" and a garbage error %. Now reads the real keys and
    computes the error against the real actual.
  - "Price Drivers Explained" read `explanation`/`factors`/`drivers` — the
    TFT route returns `top_drivers[{feature, importance}]`, so the block
    never rendered. Now wired to the real keys (attention importance).
  - Multi-horizon table read `change_pct`/`predicted_price` — rows carry
    neither; the Change column showed 0.0% for every horizon. Now derived
    from the payload's `current_spot_nok`.
  - `PriceOutlook.scenarios` type said `Record<string, number[]>` while the
    engine emits percentile floats (p10…p90) — corrected; scenario bar
    width now comes from a typed helper.
  - `PriceOutlook` direction is `"up"|"down"|"flat"` — the page compared
    against `"bullish"`/`"bearish"` (dead branches) and passed the numeric
    `signals.combined` where a string was expected; both corrected.
- `/scenarios` local view models (`OutlookResult`/`HorizonPoint`) described
  the same fictional fields with `(h as any)` casts throughout; rebuilt on
  the real typed payloads with boundary normalisation (multi rows mapped to
  a typed view model; `confidence_interval` derived from real `bands.p80`).
  Also fixed: the biomass scenario cards read `mab`/`utilization`/
  `harvest_delta` (fiction) and multiplied the already-percentage
  `utilization_pct` by 100 (would have shown 8210%); now shows National MAB,
  Utilization and Forecast Biomass from the real keys.
- Regression nets: 4 new backend-backed `api-contracts.spec.ts` assertions
  (multi horizon rows, prediction-history list + real row keys, explain
  `top_drivers` incl. the documented 503 degraded path, futures-curve
  `price_nok` rows).
- Local verification: tsc clean, eslint 0 errors, visual baselines 4/4.

### Fixed (NEW finding — /market page contract fiction, same class as the supply fix)
- `frontend/src/app/market/page.tsx` was consuming **six** endpoints
  through invented shapes; each mismatch produced a silent-empty widget
  or a permanently-skeletoned section:
  - `/api/market/hedger-signals` returns a LIST → page read
    `{signals:[…]}` (always empty). Now consumes the list; the badge maps
    the real `direction` (HEDGE/UNHEDGE) and the bar shows real
    `strength` (0-1).
  - `/api/market/export-destinations` returns `destinations` as a DICT
    keyed by country code → page read a list (`.length` undefined →
    eternal skeleton). Converted at the boundary with computed share_pct
    from real `total_tonnes`/`total_nok_millions`.
  - `/api/ais/harvest-intelligence` real shape is
    `total_vessels/summary/harvest_signals_72h/…` → the old
    `AISHarvestIntel` type (active_vessels/recent_signals) was fiction and
    the whole AIS card rendered empty. Type corrected to
    `AISHarvestIntelligence`; card now shows Vessels Tracked, Harvesting
    Now, Treating Now, Supply Pressure + real 72h signal rows.
  - `/api/sentiment/summary` real shape (`avg_sentiment_24h`,
    `sentiment_trend`, `articles_24h`) → `SentimentSummary` type was
    fiction; card showed "Neutral / 0 articles" forever. Fixed type + card
    (score, trend, article count).
  - `/api/macro/snapshot` and `/api/macro/series/{name}`: `MacroSnapshot`
    (series/unit/source) and `MacroSeries` types were fiction; corrected
    to the real `{indices, benchmarks, yoy_changes, alerts: string[]}`
    and `{name, data:[{date,value}]}` shapes; the market Macro widget and
    dashboard types now compile against reality.
  - `SSBPriceHistory` type said `price_nok_kg/week:number` while the route
    emits `price_nok/week:"W13"` — corrected.
- AIS dashboard consumers updated: `DashboardAIS` no longer extends the
  fictional type (real `AISHarvestSignalRow[]` union, honest
  `vessel`/`farm_name` fields in the top-vessel line).
- Regression nets: 6 new backend-backed `api-contracts.spec.ts`
  assertions pin every corrected shape (price_nok rows, destinations
  dict, hedger list, AIS keys, sentiment keys, macro keys incl. the
  documented 404 degraded path).
- Local verification: tsc clean, eslint 0 errors, visual baselines
  re-verified (the /market baseline renders unchanged under the stubs).

### Fixed (NEW finding during the L5 migration — supply-forecast contract fiction)
- `/api/supply/smolt-forecast` returned a **bare list** (the old
  `isinstance(result, dict)` provenance guard could never fire) while the
  frontend type, the api-docs sample and the page all described *three
  different fictional shapes* — the smolt section silently rendered
  "No data" against the real backend. The route now returns the
  documented envelope `{pipeline[], horizon_months, total_harvest_tonnes,
  data_provenance}` (OpenAPI re-frozen, 2-line description-only diff;
  in-repo consumers verified).
- Same defect class on `/api/supply/cohort-timeline` (bare list, no
  provenance) → now `{cohorts[], count, data_provenance}`.
- `frontend/src/app/supply-forecast/page.tsx`: reads the real fields —
  the cohort volume column showed "—" for every row because it read a
  `projected_harvest_tonnes` key that cohorts don't have (now
  `harvest_tonnes`); removed other fictional fields (`intake_month`,
  `expected_harvest`, `monthly_projections`, `smolt_releases`).
- The header badge was hardcoded `source="Smolt Model" quality="live"`
  → now provenance-driven from the payload (no claim when the fetch
  fails).
- The page is fully typed (state + maps, eslint-disable removed) via new
  `SmoltPipelinePoint` / `SmoltForecastResponse` / `SmoltCohortRow` /
  `SmoltCohortTimeline` / `SmoltDemandBalance` / `SupplySummary`
  interfaces; the fictional `SmoltForecast` type is gone.
- Regression nets: backend tests pin the envelopes + pipeline point keys
  (test_routers, test_api_routes); e2e `api-contracts.spec.ts` asserts
  the envelopes against the real backend; new
  `frontend/e2e/supply-forecast-contract.spec.ts` (stubbed, no backend)
  pins that the page renders real pipeline rows, the cohort volume
  column, and a payload-driven badge — and shows no badge at all when
  the payloads fail.

### Changed (review L5/L7/L8 — bounded slices of the backlog item)
- **L5 (typing slice):** new `ChinaDemand*` interfaces in
  `frontend/src/types/api.ts` (snapshot / signals / impact / suppliers /
  momentum, incl. the `is_live` contract) mirroring the engine payloads;
  `api.chinaDemand*` client methods are now typed;
  `frontend/src/app/china-demand/page.tsx` dropped its `any` state/maps
  and eslint-disable entirely (typed state + `?? 0` narrowing helpers),
  plus removed an unused `ProvenanceWrapped` import in `api.ts`. The
  remaining ~460 `any` usages elsewhere stay on the backlog.
- **L7 (observability slice):** verified the Prometheus endpoint — it
  exists whenever the (locked) instrumentator dependency is installed,
  which is true in CI and the Docker image; new `tests/test_metrics.py`
  asserts `/api/metrics/prometheus` serves text/plain metrics and stays
  out of the frozen OpenAPI contract (skips locally if the dependency is
  absent). The china-demand snapshot log now carries the `live` flag.
- **L8 (dependency-drift note):** `requirements.txt` gained an explicit
  policy header: `>=` bounds are for local dev, `requirements.lock` is
  the reproducible set used by Docker/CI, and the exact `uv pip compile`
  command to re-generate the lock after changing the file.

### Added (review L4 — provenance contract net for the R10 bug class)
- Shared records-based provenance helper
  `core.market.data_provenance.from_records(records, ...)`: live only
  when raw records were actually returned (never on derived/rounded
  values that can legitimately be 0) — `_china_provenance` is the first
  consumer; future domains with the same "records or estimates" shape
  should reuse it instead of pasting `DataProvenance.live(...)`.
- New `tests/test_provenance_contract.py` (8 tests): recursive payload
  walker that FAILS whenever a payload with `is_live: false` contains a
  "LIVE" string anywhere — pinned on the degraded engine snapshot, the
  degraded supplier-breakdown rows, and all three degraded
  `/api/china/*` route payloads (the R10 bug left nested engine claims
  asserting LIVE while the route said degraded) — plus the helper's
  live/degraded/None semantics.

### Fixed (review L6 — docs/PLATFORM_STATUS.md was UTF-16)
- Renormalized to UTF-8 (no BOM, LF endings; 24,862 → 12,658 bytes) so
  grep/diff tooling works on it. Content unchanged.

### Fixed (review M7 + L2 — stale CHANGELOG claim + dead code)
- CHANGELOG R10 entry corrected: the badge ships `role="img"` (not
  `role="status"`) and the `title` fallback was removed in the M4 fix —
  annotated as a dated correction instead of silently rewriting history.
- `ChinaDemandEngine.get_top_suppliers` deleted (dead code, zero callers;
  the supplier breakdown is already part of `get_snapshot` via
  `/api/china/demand`).
- `get_supply_impact` docstring no longer claims "Uses LIVE SSB price
  data" unconditionally — it documents the degraded paths and that
  honest provenance is attached by the route layer.

### Fixed (review M5 — degraded snapshots pinned the platform for the full TTL)
- `ChinaDemandEngine.get_snapshot` split into a cache probe
  (`_cached_snapshot_if_fresh`) + `_fetch_snapshot_locked`:
  - **Negative-cache TTL:** degraded snapshots (no SSB 08799 records)
    now cache for 10 minutes instead of the full 2-hour data TTL, so
    recovery after an SSB outage takes minutes.
  - **Single-flight:** a lazily-created per-event-loop `asyncio.Lock`
    prevents concurrent cold calls from double-fetching the upstream
    (with a post-acquire cache re-check).
- New `tests/test_china_demand_cache.py` (5 tests, fake fetcher — no
  network): degraded TTL expiry + recovery to LIVE, LIVE keeps the 2h
  TTL, TTL ordering, and both single-flight cases (concurrent cold calls
  fetch exactly once, degraded fetch included).

### Changed (repo hygiene — review H3 + M6)
- Untracked the `.hypothesis` cache (5,178 files; already in `.gitignore`,
  so CI/repo weight drops without losing anything — the local cache stays
  on disk for pytest runs). `chore(repo)` commit `be3cea8`.
- PR #2 ("Session 38: Wire welfare/NorKyst/PACE endpoints + ErrorBoundary
  sweep", branch `claude/happy-curie`) closed as **superseded** with a
  documented evidence comment: 6-month-old conflicting branch (`mergeable:
  CONFLICTING`, master 96 commits ahead, every file in its 90-file diff
  rewritten since) whose headline features already exist in master —
  welfare SWIM scores (`/api/welfare/score/{pa}` in farm_routes), NorKyst800
  v3 (`/api/ocean/norkyst/current`) and NASA PACE
  (`/api/satellite/pace/chlorophyll`) in ocean_routes, and the
  JWT-fail-fast/auth hardening in `core/auth.py`.
- Stale remote branches deleted: `claude/happy-curie` (closed PR #2) and
  `claude/cool-cray` (PR #1, merged). Remote now tracks only `master`.

### Fixed (review M4 — DataQualityBadge mislabels + tooltip duplication)
- `qualityFromProvenance` now maps by provenance STATE, never by
  confidence thresholds: `is_live` → "Live", `source === "simulated"` →
  "Simulated", everything else → "Degraded". Previously a degraded
  payload with confidence < 0.4 was falsely labelled "Synthetic" (violet
  badge); low-confidence degraded fallbacks now say "Degraded" (server
  states: `core/market/data_provenance.py`). "Synthetic" stays reachable
  only via the explicit `quality` prop.
- Removed the native `title` attribute that duplicated the custom
  group-hover/group-focus-within tooltip (one tooltip, keyboard
  accessible); `role="img"` + `aria-label` WCAG semantics kept.
- Visible `focus-visible` ring added for the keyboard-focusable badge.
- Regression-pinned in `frontend/e2e/china-demand-honesty.spec.ts`
  (degraded stub deliberately uses confidence 0.3: badge must read
  "Degraded", never "Synthetic"; no `span[role="img"][title]` elements;
  focus-ring class present; live stub → "Live").

### Added (review M2 — untested china sub-routes)
- `tests/test_china_provenance.py` now covers
  `/api/china/demand-signals` and `/api/china/demand-impact` with both
  degraded (SSB 08799 fails → `is_live: false`, confidence 0.5,
  `fallback_reason`, payload passes through) and live (records returned →
  `is_live: true`, confidence 0.75) states — previously only the
  `/api/china/demand` snapshot route was pinned.

### Fixed (follow-up to H1 — slowapi clobbered route-provided Retry-After)
- Discovered by the full-suite CI-equivalent run:
  slowapi's `_inject_headers` (active because of H1's
  `headers_enabled=True`) OVERWRITES any existing `Retry-After` on every
  response — the 503 upstream-unavailable envelope's `Retry-After: 45`
  came back as the rate-limit window reset (`60`), and 2xx responses got
  a meaningless `Retry-After`. New `AppLimiter(Limiter)` subclass in
  `core/api.py` keeps the `X-RateLimit-*` observability headers but only
  sets `Retry-After` when the response has none already AND the
  allowance is exhausted (429s come from the exception handler, which
  sets its own). `tests/test_error_envelope.py` (the failing regression)
  is green again; new `TestRetryAfterPreservation`
  (no `Retry-After` on 2xx + 503 envelope value preserved) pins it.

## [Unreleased] — RUN-1 Sprint 4: R9 release + R10 accessibility/honesty (2026-10-13)

### Released (R9)
- `PLATFORM_VERSION` 2.2.0 → 2.3.0; `API_SCHEMA_VERSION` 1.0 → 1.1 (the
  additive response-contract change from R7, per the policy documented in
  `core/version.py`); `docs/openapi.frozen.json` re-frozen (2-line diff: the
  provenance `schema_version` default + `info.version`); `/api/health`
  verified reporting 2.3.0 locally and green in CI; all CHANGELOG
  `[Unreleased]` sections folded under the `[2.3.0]` release heading;
  GitHub release published:
  https://github.com/frehan83-collab/AquaIntel/releases/tag/v2.3.0

### Changed (R10 — bounded accessibility & honesty slice)
- `DataQualityBadge` now carries WCAG semantics: `role="img"` with an
  `aria-label` (quality, confidence, source, note) — every existing
  consumer inherits the improvement. (Correction, 2026-10-13: this entry
  originally said `role="status"` plus a `title` fallback; the shipped
  implementation used `role="img"`, and the title fallback was later
  removed as a duplicate tooltip in the M4 fix — see the post-review
  session entry at the top of this file.)
- Provenance badges added to the `/price-outlook` page (both header variants)
  and `/china-demand`.
- **Honesty fix (deep):** the three `/api/china/*` routes returned
  `DataProvenance.live("SSB + customs data")` even when the SSB 08799 export
  fetch fails, and the engine's own payload asserted `"LIVE — SSB table
  08799"` / `is_live: true` in its nested Norway fields (and the
  `/china-demand` page rendered those claims). All three layers are now
  honest: the engine downgrades the snapshot (`source`, Norway
  `data_source`, supplier `is_live`) whenever no export records came back,
  the routes return `degraded` (confidence 0.5, with the reason), and the
  page shows "SSB series unavailable — Norway shown from curated
  estimates". Liveness is keyed on records actually returned
  (`monthly_series`), never on a rounded tonnage that can legitimately be 0.
- Coverage audit (reproducible): 26 of 65 page files import
  `DataQualityBadge` (24 before this slice); the remainder are static /
  non-data pages (login, privacy, changelog, design-system, …) or noted as
  future candidates (bloom, causal, exposure, twin, predictions).

### Verified
- `ruff check` clean; new honesty regression suite `tests/test_china_provenance.py`
  8 passed (helper logic + engine nested claims + live route both ways);
  `tests/test_routers.py` + openapi contract green; `tsc --noEmit` 0 errors;
  eslint 0 errors; live curl of `/api/china/demand` shows the honest degraded
  provenance. Independent review of this slice applied in full (contradictory
  nested LIVE claims, `<div>`-in-`<p>` hydration hazard fixed by moving the
  badge root/tooltip to spans, hover-only tooltip now focusable, false
  "Degraded" before data arrival removed).


## [2.3.0] — 2026-10-13 — RUN-1 release
(Everything below under this heading was previously marked [Unreleased]:
RUN-1 Sprints 1–3 plus the P0–P2 follow-up sweeps.)

### RUN-1 Sprint 3: R7 integrated supply–demand engine + 2–20w price path (2026-10-13)

#### Added (R7 — "Holy Grail" flagship)
- `core/market/supply_demand_engine.py`: singleton engine composing the smolt
  pipeline (Norway supply + baseline demand), biomass outlook (Monte Carlo,
  seeded), global supply (Chile/Scotland/Faroe), lice pressure → harvest-delay
  adjustment, China demand momentum and SSB 03024 price history.
- **2–20 week price path** (19 weekly points): seasonal median + mean-reversion
  of the current deviation (half-life 4w) **measured from the latest PUBLISHED
  SSB week**; empirical p10–p90 bands from **walk-forward residual quantiles**
  (~80% measured out-of-sample coverage; in-sample quantiles only when history
  is too short for a walk-forward fit). Bounded heuristic overlays (labelled,
  NOT backtested): global supply-deficit tilt (0.5%/pt, cap ±5%) and
  lice-delay tilt (cap 2%), ramped in over 4 weeks. The legacy smolt
  `price_pressure` signal is deliberately NOT used as a price tilt — its
  balance is pipeline coverage, structurally ≈ −80%, so a tilt from it would
  peg constantly (would have been a fabricated signal).
- `scripts/backtest_supply_demand.py`: strict no-lookahead walk-forward
  backtest over real SSB history → `data/models/supply_demand_backtest.json`
  (gitignored, mirroring the `price_backtest.json` artifact contract; route
  surfaces `price_forecast.backtest` ONLY from the validated artifact).
  Measured 2026-10-13 (352 weeks, 248 walk-forward origins):
  **MAPE 9.08% @2w → 20.94% @20w**; walk-forward band coverage **79.3–80.0%**
  (the in-sample-quantile variant covers only 55.3–69.9% — why the engine
  ships the walk-forward calibration).
- Route `/api/supply/demand-balance` extended **additively** (contract
  `additive-v1`): every legacy field byte-identical, plus `balance_label`,
  `integration` (sources + structured fallbacks), `supply_breakdown`,
  `demand_breakdown`, `price_forecast`. `docs/openapi.frozen.json` re-frozen
  (1-line route description; the response schema was and remains `{}`).
- Frontend: `/supply-forecast` demand-balance card gains the price-path chart
  (mid + p10–p90 band), spot week + publication-lag disclosure,
  `DataQualityBadge`, backtest MAPE line, method note, and amber notices when
  the artifact is missing or bands fall back. `frontend/e2e/api-contracts.spec.ts`
  now asserts the live additive contract server-side in CI.
- 11 new engine tests (`tests/test_supply_demand_engine.py`) — offline,
  deterministic, no network/DB — including an H2 regression guard that
  horizons are referenced to the latest published week.

#### Fixed (independent review — all findings applied)
- **H1 (evidence provenance):** silent sub-engine degradation can no longer be
  advertised as live — `_safe` wraps every source (sync *and* async), biomass
  and global supply raise when they have no real result/anchor, and the China
  demand input is explicitly disclosed as industry estimates (with the
  fallback recorded and provenance `degraded`) whenever live SSB exports are
  unavailable. Structured fallback strings now carry the failure reason.
- **H2 (reference frame):** forecast horizons are now anchored to `spot_week`
  — the same reference the walk-forward calibration uses. Previously the live
  path was anchored to `today + h` while MAPE/bands described `spot + h`
  (SSB's ~2-week publication lag therefore understated uncertainty and shifted
  every displayed point). `spot_lag_weeks` + `horizon_reference` are now in
  the payload and the UI shows the lag.
- M1/M2: method note corrected (the walk-forward fallback trigger is "too
  short for a 104w train + 20w horizon", not "history < 2 years"); UI hardened
  against partial artifacts (`?? "–"`, optional `n_origins`). L-fixes:
  `bands_source` disclosed in the UI, `components_backtested` renamed to
  reflect that no component ablation exists, legacy `price_pressure` tile
  labelled with its source model, padStart/spot-week rendering consistency,
  stale comments removed.

#### Verified
- `ruff check` clean; authoritative suite (`pytest tests/`, CI-equivalent)
  **663 passed / 13 xfailed / 10 xpassed / 0 failed (231.31 s)**; `tsc --noEmit`
  and eslint 0 errors; `next build` compiled; live curl of the running route
  (legacy + additive keys, 19 weekly points, honest degraded provenance);
  Playwright api-contracts assertion added so CI's e2e-backend proves the
  additive contract server-side on every run.

### RUN-1 Sprint 2: P0-2 closed, lice read-index shipped (2026-10-13)

#### Closed (R5 — DuckDB P0-2, cross-platform evidence)
- Built `scripts/bench_lice_read.py`: the exact four `/api/lice/summary` queries
  vs DuckDB `sqlite_scanner` ATTACH vs extension-free row-loading; identical
  summaries enforced across candidates (`match=true`).
- Ran on **Linux** (`python:3.12-slim` container, DB staged in a named volume
  so the Docker-for-Windows mount bridge didn't pollute I/O) and Windows,
  186,139 rows, warm medians: **Linux sqlite 19.4 ms vs DuckDB 80.2 ms
  (4.1× slower)** vs rowload-latest 180.4 ms; **Windows 30.0 / 78.8 / 12.6 ms**.
- **Verdict: CLOSE P0-2** — the `sqlite_scanner` path loses on both platforms
  (4.1× Linux, 2.6× Windows); the row-load variant wins only on Windows
  (12.6 vs 30.0 ms) and loses on Linux (180.4 vs 19.4 ms) — no portable win,
  ≥1.5× gate unmet → **no DuckDB read path will ship**. The 2026-10-13 Windows
  extension blocker did not reproduce today, so the decision no longer
  depends on it. Full closure write-up in `docs/NEXT_STEPS_PLAN.md` §P0-2.

#### Fixed (R6 — the real read-path cost: a missing index)
- `/api/lice/summary` filters `lice_records` by `(year, week)` with **no index
  for those columns** (the only index leads with `locality_no`) → **three full
  scans** of 186k rows + a temp b-tree sort per read.
- **Alembic 015** adds `ix_lice_year_week (year, week)` (existence-guarded,
  013 pattern) and `LiceRecord` declares it for create_all parity. EXPLAIN
  QUERY PLAN: `SCAN lice_records` → `SEARCH ... USING INDEX (year=? AND
  week=?)`; bench on an indexed copy: **19–30 ms → <0.1 ms warm**.
- Latency-sweep note (same R6): the e2e-flagged slow route (Scotland snapshot
  ~25 s) is a cold-cache EXTERNAL fetch — measured **25,695 ms cold → 9 ms
  warm** with the existing `@cached(ttl=900)`; network-bound, no DB fix.

#### Verified
- `tests/test_migrations.py` green (fresh-DB `alembic upgrade head` incl. 015,
  plus a new assertion that `ix_lice_year_week` exists after the chain);
  `ruff check .` clean; py_compile on touched modules; full pytest suite
  **652 passed / 13 xfailed / 10 xpassed / 0 failed (231.39 s)**;
  frontend untouched.

### RUN-1 Sprint 1: hygiene & ratchet truth (2026-10-13)

#### Fixed (R1 — /market honesty pass)
- Dead Fish Pool surface removed (feed retired 2025): `FishPoolChart`,
  `fishPool` state, the "Fish Pool Index" + old "WoW Change" KPI cards (both
  rendered a permanent "—"), the ticker-strip entry and the header tagline
  mention ("SSB · Futures · Equity · AIS" now).
- Equity bindings corrected: `/api/market/equity-prices` returns `prices_nok`
  (not `prices`) and has **no per-ticker change field** — the MOWI KPI, the
  ticker strip (SALM/LSG/GSF/BAKKA) and the equity list were permanently
  empty, and change deltas rendered as fabricated "+0.00%". All consumers now
  read `prices_nok`; fabricated deltas removed; the equity card surfaces the
  endpoint's source string ("Yahoo Finance (~15min delay) + SSB fallback").
- "WoW Change" KPI is now real SSB week-over-week (honest "—" when
  unavailable; percent shown via KPICard's `unit` prop because its count-up
  strips "%" from value strings). New "SALM (Lerøy)" KPI. MOWI label
  escaping bug fixed (JSX attribute strings don't process `\u00f8`).
- Evidence: live headless run — KPI row all live (WoW +0.29%, MOWI 203.40,
  SALM 544.00 NOK), 52 seasonal bars, futures card + "SSB synthetic" badge
  intact, 0 console errors / 0 failed requests; tsc + eslint 0 errors;
  pytest full suite 651 passed / 13 xfailed / 10 xpassed / 0 failed.
  Independent review: no CRITICAL/HIGH; its findings applied. Visual note:
  a fresh Linux regen via `visual-baselines.yml` produced a **byte-identical**
  `/market` baseline — the committed screenshot encodes the first-visit wizard
  overlay (visual.spec policy), which dims the page beneath it, so no baseline
  commit was needed.

#### Fixed (R1b — the ruff ratchet had drifted AND was never enforced)
- Cleared **all 30 ratchet violations** repo-wide (`ruff check .` clean under
  the E9/F821/F811/F401/F841 selection): 24 unused imports (F401) + 6 dead
  locals (F841) across `agents/`, `backtest/`, `compliance/`, `dashboard/`,
  `tests/` and `main.py`. In `tests/test_engines.py` a side-effecting call
  was kept as a bare statement; the pure dead assignments were deleted.
- **`test.yml` now actually enforces the ratchet** (`uvx ruff check .`).
  `ruff.toml` claimed "ENFORCED in CI (must pass)" but no workflow ever ran
  ruff — which is exactly how the drift accumulated. Dead code cannot
  silently pile up again.
- Evidence: `ruff check .` → All checks passed; py_compile on all touched
  modules; agent import smoke; targeted pytest over every touched test file
  217 passed / 0 failed; full suite green.

#### Noted (candidates for later RUN-1 workstreams)
- **KPICard count-up quirk**: it parses numeric-looking value strings and
  drops their adornments — "+0.29%" renders "0.29", and in the `no` locale
  "0,29" parses to **0** (comma stops parseFloat). ~20 pages pass
  `%`-suffixed strings to KPICard. A component-level fix (preserve
  prefix/suffix, locale-aware parse) deserves a dedicated workstream.
- `/futures` `<title>` children-array and `/market` hydration warnings (R1c):
  **closed as not-reproducible** — four dev-mode captures (both pages, fresh
  and onboarded profiles, all console types) are clean on the R1 commit; they
  were likely resolved incidentally by earlier work. Reopen with a
  reproduction if they resurface.

### follow-up sweep: /market bindings + frontend CI triggers (2026-10-13, continued)

#### Fixed (documented post-plan follow-ups)
- **`/market` seasonal card** bound `.data` from `/api/market/ssb-seasonal`,
  but the endpoint returns `.seasonal_pattern` (week → median dict) → the card
  showed a permanent loading shimmer. Now maps the dict (keys are ISO week
  numbers) into the chart, the footer honestly says **median** (the endpoint
  computes `np.median`) and appends the `data_years` span, and an empty
  response renders an explicit "Seasonal data unavailable" state instead of
  the eternal skeleton.
- **`/market` Futures Forward Curve card** bound `.curve` from
  `/api/market/futures-curve` (that endpoint returns SSB `.history`) →
  permanently "Futures data unavailable". Repointed to the real forward curve
  `/api/futures/forward-curve` (Fish Pool live forwards → SSB seasonal
  synthesis fallback); the card badge flips to **"SSB synthetic"** when
  `is_synthetic` so a fallback curve is never labelled as Fish Pool live.
- **`/market` macro KPI cards**: `macroSeries("FRED_USDNOK")` /
  `("FRED_WTI_OIL")` are not valid series names for
  `macro_intelligence.get_series_history` (its keys are `nok_usd` /
  `brent_crude`) → both cards 404'd on every visit. Bound to the real series
  and the crude card is relabelled **Brent Crude** (the backend has no WTI
  series; labelling Brent as WTI would be dishonest), incl. the banner ticker
  ("Brent $…" instead of "WTI $…").
- `FuturesForwardCurve` type mirrored a stale contract (`contracts`/`spot_nok`/
  `fx_rate`); now mirrors the engine response (`curve`/`spot_nok_kg`/
  `spot_eur_kg`/`eur_nok_rate`/`is_live`/`is_synthetic`/`data_provenance`).
- **`/investor` Macro Environment card** — same cluster, found by the pre-commit
  review: invalid series names (`FRED_USDNOK`/`FRED_WTI_OIL`/`FRED_SOYBEAN` →
  `nok_usd`/`brent_crude`/`soybeans`), "WTI Crude Oil" labelling Brent data,
  `$/bu` on a USD/tonne series, and a `|| 0` fallback that fabricated a
  **$0.00** quote whenever a fetch failed. Labels/units now match the
  `macro_intelligence.FRED_SERIES` registry; failures render "—" with a
  "FRED series unavailable" note.

#### Changed (review hardening)
- Seasonal card heading relabelled "Weekly Average" → **"Weekly Median"**
  (`market.weekly_avg`, only consumer) — it plots the medians the footer now
  also names.
- Fish Pool badge renders only when a curve exists; anything except an
  explicit `is_synthetic === false` reads "SSB synthetic" (fail-safe — a
  payload without flags can never be presented as live Fish Pool forwards);
  the `curve` mapping is `Array.isArray`-guarded.

#### Changed (CI)
- `frontend.yml` path filters now also trigger on the backend surfaces the
  `e2e-backend` job boots against (`core/**`, `agents/**`, `config/**`,
  `alembic*`, `main.py`, dependency manifests, `scripts/ci_bootstrap_db.py`,
  `scripts/design_token_pipeline.py` and the workflow file itself) — backend-only
  changes previously skipped the backend-backed e2e entirely (documented P0-1
  follow-up).

#### Verified
- Live local rig (uvicorn + `next dev` + headless chromium on /market and
  /investor): 52/52 seasonal bars from the real SSB medians ("Weekly Median",
  footer "(2020-2026)"), forward-curve chart + KPI strip render with an honest
  "SSB synthetic" badge, NOK/USD 9.64 · Brent $83.73 · Soybeans $442.45/t
  (FRED live), **0 console errors / 0 failed requests** on both pages.
- `npx tsc --noEmit` 0 errors; eslint 0 errors (warnings tolerated);
  pytest **651 passed / 13 xfailed / 10 xpassed / 0 failed** (253 s).

### P1-5/P1-6/P1-7 audits (2026-10-13, continued)

#### Changed (P1-5 — test hygiene)
- **Removed 12 stale `xfail` markers** from `tests/test_api_routes.py`: the 11
  "Dev SQLite may lack Alembic migration 00X…" schema-lag guards (obsolete since
  the migrations-first bootstrap everywhere — they XPASS on both dev and
  fresh-seeded CI databases) and the TimesFM "may not be installed" marker (the
  engine's honest seasonal-naive fallback returns `model` + `median`, so the
  contract holds without the model stack).
- Remaining xfails kept + justified in the plan: genuine external-data guards
  (DFO/Sernapesca/Scotland/Hagstova/Iceland/FRED-live) and async-design quirks.
- Full suite evidence: **639 passed, 13 xfailed, 22 xpassed, 0 failed** on
  Windows/Python 3.14.

#### Verified (P1-6 / P1-7 — audits, no code changes)
- P1-6: `docker-compose.yml` already ships the `fishintel-agents` service
  (`--agents-only`, SIGTERM-graceful); fresh-DB `alembic upgrade head` validated
  in three places (ci_bootstrap, container entrypoint — verified live — and
  `tests/test_migrations.py`).
- P1-7: all four Tier-1 features live-verified (feed margin stack + alerts;
  ocean-forecast→lice decision wiring; computed ESG scores; AIS harvest
  intelligence with 72h signals).

### P0-3 + P0-4: instant lock extension & uv adoption (2026-10-13)

#### Added (P0-4 — uv adoption, Python pinned to 3.12)
- **`pyproject.toml`** — single dependency manifest (mirrors requirements.txt;
  optional `models` extra mirrors requirements-models.txt) with the explicit
  **Python 3.12 pin** decision (`requires-python = ">=3.12,<3.13"`,
  `.python-version`), honoring the plan's rule: local 3.14 must not silently
  become the torch-stack target (CI and Docker already ran 3.12).
- **`requirements.lock`** — generated via
  `uv pip compile pyproject.toml --python-version 3.12 --python-platform linux`
  (248 pins; fastapi locked to the verified 0.135.x line). Regeneration is
  interpreter-free and documented in AGENTS.md.
- CI (`test.yml` + the `e2e-backend` job) and the Dockerfile now install from
  the lock via `uv` (`astral-sh/setup-uv@v5` / `ghcr.io/astral-sh/uv:0.10`);
  `requirements.txt` remains for Windows dev without uv.

#### Changed (P0-3 — instant-navigation lock extended, wired into CI)
- `e2e/instant.spec.ts` now locks **11 routes** (added /brief, /farmer-daily,
  /disease, /leaders, /futures, /feed-cost, /global-supply, /notifications) —
  11/11 green on the prod rig; the rig runs blocking in the `e2e-backend` job.
- `frontend.yml`: removed the redundant tolerant backend-free e2e step from the
  build job (superseded by the blocking backend-backed job; it cost ~15+ min
  per run in expected connection-retry stalls with no added signal).

### Note (P0-2 — DuckDB)
- DuckDB read path deferred with evidence: the sqlite_scanner extension is
  blocked by a Windows application-control policy on the dev box, and the
  extension-free variant measured ~5× slower (220 ms vs 47 ms) than the
  current query path. See docs/NEXT_STEPS_PLAN.md P0-2.

### P0-1 backend-backed e2e (2026-10-13)

#### Added
- **`e2e-backend` CI job** (`frontend.yml`): spins a fresh seeded SQLite DB
  (`scripts/ci_bootstrap_db.py`) + uvicorn on :8000, then runs the API contract/
  integration specs and the app specs (navigation, golden-path, interactions)
  **blocking** on chromium, 1 worker, with a failure-report artifact.
- `scripts/ci_bootstrap_db.py` — idempotent fresh-runner DB bootstrap (schema +
  demo seed), mirrors the conftest pattern.
- `frontend/e2e/utils.ts` — `suppressOnboarding()` (pre-marks `oc_onboarded` /
  `aquaintel_tour_completed`; the first-visit wizard otherwise intercepts pointer
  events on every fresh browser profile). Visual baselines intentionally unaffected.

#### Fixed
- **`price_feed_hub._get_ssb_prices`** called non-existent
  `ssb_client.get_latest_prices` (import error) → `/api/futures/forward-curve`
  returned an empty curve forever. Now uses
  `ssb_price_client.get_price_history(n_weeks=260)` + `price_nok`→`price_nok_kg`
  normalization. Verified: 12-point synthetic curve, honest degraded provenance.
- **`ssb_price_client` week-count-agnostic cache** (found by fresh-DB e2e): an
  8-week startup fetch answered the hub's 260-week request for the whole 6 h TTL
  → "Insufficient price history" → empty curve (cached 600 s by the
  `/api/futures/forward-curve` route). Both the fresh-cache and serve-stale
  paths now require the cached request window to cover the incoming request
  (`_cache_requested`); 3 regression tests added.
- **`alembic upgrade head` aborted on fresh databases** (`013_performance_indexes`
  re-created `ix_audit_logs_user_id`/`_action` already created by
  `011_audit_logs`) — the production entrypoint migration step would have failed
  on any brand-new deploy. 013's creates/drops are now index-existence-guarded;
  verified `upgrade head` completes on an empty DB + subprocess regression test
  (`tests/test_migrations.py`).
- **`/market` page** read `.data` from `/api/market/ssb-price-history` (endpoint
  returns `.history`, field `price_nok`) → price chart + spot KPI permanently
  empty. Now mapped correctly; the header DataQualityBadge no longer fabricates
  a 90% confidence figure (classifies live/degraded without invented numbers).
- **`/trader` page** same bug class: spot KPI read `price_nok` (endpoint returns
  `price_nok_kg`) and forward-curve rows read `price_nok`/`price` (hub returns
  `projected_nok_kg`) → permanently "--". Now normalized via `priceOf()`.
- e2e specs aligned with the real contracts: `/api/metrics` JSON shape,
  `/api/market/ssb-price-history`, `/api/leaders/top30`,
  `/api/regulatory/traffic-light/current`; admin block now tests the
  anonymous-401 / non-admin-403 / admin-200 contract (mirrors
  `tests/test_api_routes.py`); fragile selectors (hidden hamburger `.first()`,
  mixed CSS+text click, strict-mode `text=Disease`, PDF-by-text) replaced with
  role/a11y-contract locators; URL race → `toHaveURL()` auto-retry.

### Session 41e (2026-10-12, autonomous run, continued)

#### Added
- **Blocking visual regression in frontend.yml** with Linux baselines for
  chromium AND mobile (Pixel 5); backend-free e2e scoped separately;
  visual-baselines workflow generates/verifies all projects.

#### Fixed
- CI step order: Playwright runs before 
pm run build (the documented
  .next collision corrupts dev assets); dev-server port pinned via
  webServer env; workflow_dispatch added to both frontend workflows.

### Session 41d (2026-10-12, autonomous run, continued)

#### Added
- **Linux visual baselines** (CI-generated + committed): `visual-baselines.yml`
  workflow_dispatch (update/verify modes, ubuntu + Node 22 + chromium);
  artifact-downloaded `*-chromium-linux.png` snapshots committed; verify run
  green. frontend.yml's e2e step now checks them on every frontend change.
- **F841 in the ruff gate**: all 36 dead locals resolved (pure expressions
  deleted; side-effecting awaits kept as bare statements; PyMC
  `with pm.Model():`). ruff.toml now enforces E9/F821/F811/F401/F841.
- `partialPrefetching: true` — App-Shell prefetch model enabled (skill's
  post-adoption step), verified by instant guard 3/3 + visual baselines 4/4.

#### Fixed
- Playwright webServer port: `env: { PORT: 3001 }` pins the dev server
  cross-platform (CI previously timed out on :3000 vs :3001) + 120 s timeout.

### Session 41c (2026-10-12, autonomous run, continued)

#### Added
- **Instant-navigation regression guard** (`e2e/instant.spec.ts` +
  `playwright.instant.config.ts`; `@next/playwright@16.4.0`): prod-rig
  `instant()` lock around initial loads of `/`, `/market`, `/traffic-light`;
  testing API env-gated (`FISHINTEL_E2E=1`) so it never ships to deployments.
  Differential: GREEN 3/3 on the prod build; RED probe with an empty document
  (non-vacuity proven).
- **5-day wave forecast** (`/api/ocean/waves/pa/{pa}/forecast`): CMEMS WAM
  daily means, separate 6h cache, deterministic simulated fallback; MCP
  `get_wave_risk(..., forecast_days)` now returns `{current, forecast}`.
  LIVE verified: PA-4 0.17/0.20/0.45/0.49/0.41 m over 5 days.
- **ruff CI gate** (`ruff.toml`: E9/F821/F811/F401) + `tests/test_module_imports.py`
  ratchet (every `core/` module must import; empty allowlist).

#### Fixed
- `_rule_based_chat_response` NameError — the LICE and SIGNAL chat answer
  branches called an unimported `get_async_session()` (found by ruff F821).
- `core/models.py` missing `asyncio` import; `admin_routes` missing
  `AsyncIterator` import (annotation defects).
- **Two engines broken since creation** (found by the new import ratchet):
  `core/ml/harvest_optimizer` (5 nonexistent names -> `THERMAL_TOLERANCE`,
  `MAX_SGR_PCT`, `_temperature_growth_factor` Q10 helper added to
  biomass_predictor) and `core/valuechain/farmer_advisory` (nonexistent
  `ShortTermForecast` -> real `StageForcast`).
- 128 unused imports removed (F401), 6 availability probes annotated.

### Session 41b (2026-10-12, autonomous run, continued)

#### Added
- **Tailwind 4.3 migration** (visually verified): `@tailwindcss/postcss`,
  `@import "tailwindcss"` + `@config` compat, v3 border-color base layer,
  class-token renames (outline-hidden ×62, rounded-xs ×12, shadow-xs ×8,
  backdrop-blur-xs ×7, shadow-sm ×1). Gate: 4 committed visual baselines.
- **Visual baselines** — `e2e/visual.spec.ts-snapshots/` (win32 chromium, 4
  routes, deterministic fixtures) + Playwright chromium 1217 installed.
- `.gitignore`: repaired corrupted UTF-16 tail; ignore frontend run artifacts;
  untracked generated root `openapi.json`.

#### Changed
- `visual-regression` skill: Session-41 war stories (baseline-first, dry-run
  renames, dev-server/build collision, separate commits for baselines vs
  migration).

### Session 41 (2026-10-12, autonomous run)

#### Added
- **Next.js 16.4 upgrade** (Turbopack builds, 68/68 routes) + ESLint 9 flat
  config (eslint-config-next@16 native arrays); CI frontend job now runs
  `tsc --noEmit` + `lint` on Node 22.
- **TanStack Query v5** — dashboard data layer (14 `useQuery` resources,
  dedupe/stale-while-revalidate/retry, same return contract).
- **ECharts 6** — `OceanAreaChart` rebuilt on echarts 6.1 with lean module
  registration and an identical props contract (dashboard + twin unchanged).
- **CMEMS wave client** (`core/market/wave_client.py`, F2) — WAM
  GLOBAL_ANALYSISFORECAST_WAV_001_027 live per-PA significant wave height +
  operational risk bands; routes `/api/ocean/waves/{status,pa/{pa}}`; MCP
  `get_wave_risk` (7 tools). Deterministic simulated fallback w/ `is_live=false`.
- **OpenAPI drift guard** — `docs/openapi.frozen.json` (314 paths) +
  `tests/test_openapi_contract.py` + `scripts/freeze_openapi.py`.
- **Deterministic visual-regression spec** `frontend/e2e/visual.spec.ts`
  (all `/api/**` stubbed) — the gate for the Tailwind 4 migration.
- `docs/AUTONOMOUS_PROGRESS.md` — full session log and next priorities.

#### Changed
- CI: Frontend Build added type-check + lint steps; Node 20 → 22 LTS.
- Generated TS client regenerated for 326 routes; eslint baseline 0 errors.

### Session 40 (2026-10-12)

#### Added
- **CI is green for the first time**: Backend Tests + Docker Build both pass on
  `master`. The trigger fix (main→master), dependency split, build-time DB
  bootstrapping, fastapi pinning and the metrics-path fix are all in this list;
  the history is in the commit log (`835cdd6`..`3e733cc`).
- `core/version.py` — single version source (PLATFORM_VERSION, API_SCHEMA_VERSION);
  provenance envelopes now carry `schema_version` (arch report §7.2).
- `requirements-models.txt` — heavy foundation-model stack split out of
  `requirements.txt` (~2 GB lighter default install and Docker image).
- Router decomposition: `misc_routes.py` → `feed_cost_routes`, `ocean_routes`,
  `macro_routes`, `causal_routes`, `ras_routes` (57 routes preserved verbatim,
  mechanically verified old ≡ new); 16 structural tests.
- `response_model` wave 1 (4 new exact schemas; typed routes 8 → 12) +
  `TYPED_ROUTE_FLOOR` CI ratchet test.
- `core/pagination.py` (PageParams/paginate) + all 11 unbounded `limit` params
  Query-bounded (le ≤ 1000 / 10000 / 50000 where justified).
- **`core/satellite/cdse_client.py`** — pure-httpx CDSE Sentinel-2 client
  (OAuth token cache + Statistical API); `sentinelhub` C-dependency stack
  retired; `config/settings.py` gains `sentinel_hub_client_*` fields.
- **`core/mcp_server.py`** — FishIntel exposed as an MCP server (6 tools:
  morning brief, price outlook, lice summary, causal insights, feed cost,
  traffic-light) for external AI agents.
- **`frontend/src/types/generated.ts`** — OpenAPI-generated TypeScript types
  (openapi-typescript 7.13); `npm run gen:api` workflow documented in
  REPORT_STACK.md.
- `scripts/firecrawl_research.py` research helper; `docs/MCP_SETUP.md`;
  project `.mcp.json`; 4 new project skills (engine-audit, release,
  satellite-research, visual-regression); ecosystem skills installed.
- Research: `docs/summit/REPORT_SATELLITE.md` (verified quotas + cost path),
  `REPORT_STACK.md` (2026 versions), `docs/raw/` source captures.

#### Fixed
- Missing-await bug class burn-down: biomass outlook/scenarios (+ scenario
  cache-key collision), GNN training data, LLM farm-network tool, federated
  benchmark (endpoints were fully dead), pairs engine overlay chain, ESG getters,
  morning brief (sync Session + wrong method + Bloom section), resistance tracker.
- **ocean_currents phantom product**: `NORSHELFS_ANALYSISFORECAST_PHY_003_058`
  does not exist in the CMEMS catalogue (verified live: norkyst/norshelf →
  NO MATCH — NorKyst800 is MET.no-only); repointed to
  `cmems_mod_glo_phy_anfc_0.083deg_P1D-m`.
- Admin exports now stream (CSV/JSON generators) — 186k-row export no longer
  materializes ~13 MB in memory; audit logs `streamed=true`.
- `/api/lice/summary` TTL-cached: 70 ms → 2 ms warm (35×) on the 186k-row aggregate.
- API keys: malformed keys fail fast before DB/bcrypt; `last_used` write
  throttled to 60 s.
- Chat agent conversation history bounded (200 entries).
- Migrations run once in `scripts/docker-entrypoint.sh` before gunicorn workers
  (`FISHINTEL_RUN_MIGRATIONS=0`); `docs/DEPLOYMENT.md` documents the flow.
- CI hardening: fresh-runner DB bootstrap in conftest (schema + demo seed),
  production-scale tests skip below 10k lice rows, SQLite parent dir auto-created,
  `/api/metrics` single-owner (Prometheus text moved to `/api/metrics/prometheus`).
- Docker entrypoint LF-normalized; `.gitattributes` already enforces this.

#### Changed
- `PROJECT_STATUS.md` stats refreshed; version literals centralized.
- `.mcp.json` project config (firecrawl/playwright/context7/planet-docs).

## [2.2.0] — pre-Session-40 baseline
- 324 routes, 30 routers, 605+ tests baseline with prior sessions' hardening
  (error envelope, bounded caches, SSB/MET resilience, WS single-producer).
