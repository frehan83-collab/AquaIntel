# QUANT — ML & Algorithmic Excellence Audit

**Agent:** QUANT (ML & Algorithmic Excellence Specialist)
**Date:** 2026-06-11
**Mode:** PLAN-ONLY (no platform code modified)
**Verdict:** The "3 foundation models" are impressive scaffolding that, in this environment, serve **seasonal-naive fallbacks relabelled as live foundation-model forecasts**. The architecture is sound; the honesty layer is inverted. The bones for a real system are mostly in place.

---

## 0. Ground Truth: What Is Actually Loaded

torch is NOT installed (Python 3.14.3). Verified: torch False | chronos False | timesfm False | uni2ts False | xgboost False | torch_geometric False | pytorch_forecasting False | lightning False | pyod False | sklearn True

Consequence: every torch-dependent model falls back. `chronos_baseline.forecast_series([...])` raises `ModuleNotFoundError: No module named torch` (the unconditional `import torch` at `core/ml/chronos_baseline.py:58` bypasses the engine fallback for the Chronos path; only pipeline-load is guarded).

Net: all of /api/ml/chronos/*, /api/ml/timesfm/*, /api/ml/moirai/*, /api/ml/ensemble/*, the TFT tier of /api/market/price-outlook, and all 6 /api/gnn/* return fallback or 503 in this build.

---

## 1. Honest ML Audit Table

| Model | Claim | Loaded here? | Verdict |
|---|---|---|---|
| TimesFM 2.5 (core/ml/timesfm_engine.py) | Google 200M, native quantiles, XReg | No - not installed -> seasonal-naive. Even if installed, `model.forecast(input,horizon=,xreg=)` (l.156) is a guessed binding never validated vs the real API. | RETIRE |
| Chronos "-2" (core/ml/chronos_baseline.py) | "Amazon Chronos-2" | No. Loads `amazon/chronos-t5-small` = Chronos v1 (l.28); body model field says chronos-t5-small while router labels chronos-2. | REPLACE with real amazon/chronos-2 or chronos-bolt-small; fix v1/v2 mislabel. Keep this one. |
| MOIRAI-2 (core/ml/moirai_engine.py) | "Salesforce 30M MoE, arxiv 2502.20000" | No. arxiv 2502.20000 is fabricated; real paper is Moirai 2.0 (arxiv 2511.11698), a single decoder, not a 30M small-MoE variant. | RETIRE |
| Ensemble (core/routers/ml_routes.py:406) | "3 FMs, conf 0.70+0.05n" | No. Counts a model "available" if result has a median key - fallbacks do - so it reports models_used:[TimesFM 2.5, Chronos-2, MOIRAI-2] at conf 0.85 while averaging 3 identical seasonal-naives. | RETIRE until >=1 real model loads |
| TFT (core/market/tft_predictor.py, data/models/tft_best.ckpt) | Tier-1, 7-quantile bands | No - pytorch_forecasting absent -> predict()=None. BUG: is_available (l.189) True whenever ckpt file exists -> callers think TFT is active. | KEEP, FIX is_available |
| price_ml cascade (core/market/price_ml.py) | TFT->XGB->rule, conformal, "Backtested 2020-25 MAPE" | Rule tier only (no price_xgb.json on disk). HORIZON_MAPE l.117-120 is a hardcoded literal surfaced as "Backtested 4-week MAPE: 5.2% ... 80% of actual prices fell within band" (l.359). | KEEP engine, DELETE false accuracy statement |
| Harvest "Optimizer" (core/ml/harvest_optimizer.py) | "RL Foundation, Gym env" | Yes (pure Python) but it is a 3-rule SimpleHarvestPolicy (l.258); no RL despite header/step() dressing. | KEEP, RENAME |
| Lice GNN (core/market/lice_gnn.py) | GATv2 spatial spread, val_loss 0.0482 | No - torch_geometric absent -> /api/gnn/* 503 (only honest fallback). Weights file real. | KEEP, gated correctly |
| Anomaly engine (core/market/anomaly_engine.py) | Z-score + Isolation Forest hybrid | Partial - IForest needs pyod (absent) -> 15%-weighted multivariate always 0. Lice "z" uses std_est=0.3*mean (l.170) = fabricated sigma, not rolling std. | KEEP, FIX |

### Core dishonesty (one mechanism, many endpoints)
`DataProvenance.live(source,confidence)` ALWAYS sets is_live=True (core/market/data_provenance.py:29). Every ML router wraps the result in live("Google TimesFM 2.5 / Chronos-2 / TFT ensemble", confidence=0.75) AFTER the engine returned {"model":"seasonal-naive-fallback","is_live":False,"confidence":0.3}. Body says fallback; provenance badge says live, 0.75. User sees the optimistic one. Also: chat forecast block imports `from core.market.price_ensemble import price_ensemble` (core/api.py:1015) - that module does not exist (it is core.market.price_ml) -> silent except.

---

## 2. State of the Art (June 2026) vs Ours

- Chronos-2 (120M, encoder-only) leads GIFT-Eval: 79.8% WQL / 81.5% MASE win-rate, beating TimesFM-2.5 (70.0/71.6); univariate+multivariate+covariates, CPU inference. (arxiv 2510.15821)
- Chronos-Bolt: 5% lower error, up to 250x faster, 20x less memory, CPU-deployable, covariate-capable. (HF amazon/chronos-bolt-base) -> makes the separate MOIRAI "speed" engine redundant.
- TimesFM 2.5 was #1 Sep 2025, since passed by Chronos-2/Moirai-2. (MLM 2026 toolkit)
- Calibration gap: FMs frequently mis-calibrated out of the box - "Beyond Accuracy: Are TS FMs Well-Calibrated?" (arxiv 2510.16060). Our bands are a deterministic MC with a hardcoded 5% shock.
- Conformal SOTA: split/online CP (MSCP, ACI, AcMCP) gives distribution-free coverage under non-stationarity (arxiv 2601.18509). Our _conformal_bands is conformal in name only (falls to parametric Gaussian).
- Pro practice (Kontali): 18-month probabilistic supply->price grounded in smolt/biomass mechanics; analysts state assumptions, not vanity MAPE. We have the mechanistic smolt model - lead with it.

Sources: arxiv 2510.15821, 2510.16060, 2601.18509, 2511.11698; huggingface.co/amazon/chronos-2 and chronos-bolt-base; machinelearningmastery.com 2026-time-series-toolkit; kontali.com.

---

## 3. Top 3 Upgrades (value / complexity)

**#1 Make ONE model real on CPU + invert the honesty layer. Effort: M (1.5-2d).**
Install torch CPU + chronos-forecasting>=2.0; swap chronos-t5-small -> amazon/chronos-bolt-small; move the unconditional import torch (l.58) inside the guarded path. Retire TimesFM+MOIRAI+3-model ensemble. When engine is_live:False, router must use DataProvenance.degraded(...) not .live(0.75). Highest value: turns flagship "AI forecasts" from fiction to fact.

**#2 Split-conformal calibration wrapper + trust score. Effort: M (2-3d).**
core/ml/conformal.py: model-agnostic calibrator over stored (pred,actual) residuals; horizon-specific quantiles (MSCP); persist to data/models/conformal_residuals.json (path price_ml already expects). Surface empirical coverage as a "trust" field so users know WHEN to trust.

**#3 Fix LLM tool wiring + ship NL-to-engine-query. Effort: S-M (1d).**
2 of 6 chat tools are dead: get_price_outlook imports nonexistent price_predictor (singleton is price_ensemble); search_knowledge_base imports nonexistent rag_retriever.search() (singleton is rag_layer.query()). Both always return {"error":...}, embedded into chat context. Provider defaults to openrouter so the native tool-use path never runs.

---

## 4. LLM Integration Architecture (one page)

Decision: NL-to-engine-query (structured tool routing over live engines) is the single highest-value LLM pattern - above RAG-over-reg-docs (corpus tiny/static, already in DOMAIN_KNOWLEDGE) and auto-narratives.

Flow: User NL -> LLMClient.complete_with_tools (route Anthropic-style tool-use even under openrouter - OpenRouter proxies Claude tool-use) -> tool router (chat_agent._agentic_ask, <=5 loops) -> live engines (price_ensemble, anomaly_engine, decision_engine, farm_graph, smolt_model, mattilsynet) -> synthesis that stamps each numeric answer with the engine real DataProvenance (no relabelling).

Build order (1-2d): (1) repair the 2 broken handlers; (2) force agentic path when the model supports tool-use, not only provider==anthropic; (3) add get_forecast, get_anomaly_report, get_decision_card tools; (4) inherit honesty fixes from section 1. Defer vector RAG and daily narratives.

---

## 5. Honesty Bar (mandate item 3)
A forecast is defensible only if it states: (a) point + calibrated interval; (b) which model ran and whether it actually loaded (no fallback in a FM badge); (c) benchmark vs seasonal-naive on a stored holdout, not a same-request split; (d) empirical coverage of the band; (e) any MAPE computed and dated, never a literal. Today the stack fails (b),(c),(d),(e). Sections 1 + 2 clear the bar with ONE real model + a conformal wrapper - three are unnecessary.
