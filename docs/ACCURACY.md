# Accuracy & Method

**The rule:** a MAPE, coverage or backtest number may appear to a customer only if
a **real artifact** produced it. No estimates, no illustrative figures, no
third-party numbers presented as ours. This page is the public contract.

## Where accuracy lives

```
scripts/publish_accuracy.py  ──►  artifacts/accuracy/<artifact_id>.json  (TRACKED in git)
                                            │
                                            ▼
                         core/ml/accuracy_registry.py (validate + read + rollup)
                                            │
                                            ▼
                    GET /api/accuracy   (published metrics, or "not yet published")
                    GET /api/accuracy/method      (this contract, structured)
                    GET /api/accuracy/artifacts/{id}   (verbatim, for audit)
```

Artifacts live under `artifacts/accuracy/` and **not** under `data/` (gitignored)
— an accuracy claim that exists only on one developer's laptop is exactly what this
platform refuses to publish.

## Artifact contract (schema 1.0)

Required keys: `artifact_id`, `schema_version`, `model`, `target`, `method`,
`window`, `n_obs`, `metrics`, `produced_at`, `source`, `fallback_used`.
Required metric: `mape_pct`. Optional: `mae_nok_kg`, `coverage_pct`,
`interval_level`, `rmse`.

`fallback_used: true` means the evaluated predictor is the **honest
seasonal-naive fallback** rather than a trained model — the disclosure is a field,
not a footnote.

Validation is enforced on write (`publish()` raises `ValueError`) *and* on read
(invalid files are reported in `invalid_artifacts`, never silently skipped).

## Evaluation protocol

1. **Strict walk-forward** — each prediction uses only data available before it.
2. **Interval calibration without leakage** — the prediction interval is
   calibrated on the **first 70%** of year-back pairs, and coverage is measured
   **out-of-sample** on the remaining 30%.
3. Reported together: `mape_pct`, `mae_nok_kg`, `coverage_pct`, `n_obs`, `window`.

## Prohibited (enforced by review)

- Displaying a MAPE/coverage/backtest figure not backed by a valid artifact.
- Measuring accuracy on **demo/seed/synthetic** rows. `scripts/publish_accuracy.py`
  filters on `source` and reports how many synthetic rows it ignored; when only
  synthetic data exists it **exits non-zero and writes nothing**. (This is not
  hypothetical: the dev database contains 52 `ssb_weekly_prices` rows with
  `source='demo_seed'`.)
- Presenting a fallback result as a model result (see AGENTS.md rule 1).

## Current state (honest)

**One artifact is published** — `seasonal_naive_weekly_prices`, measured on a live
SSB fetch:

| Field | Value |
|---|---|
| Model | seasonal-naive (same ISO week, year-1) |
| Target | SSB weekly salmon export price (NOK/kg) |
| Window | 2021W42 .. 2026W41 (5 years) |
| n (year-back pairs) | 208 |
| MAPE | **13.42%** |
| MAE | 11.60 NOK/kg |
| Coverage (80% nominal interval) | **92.1%** out-of-sample |
| `fallback_used` | **true** — this *is* the honest fallback baseline |

Three things worth stating plainly:

1. **This is the floor, not a model score.** `fallback_used: true` means it measures
   the seasonal-naive rule the platform falls back to when no foundation-model
   weights are available, so it is the error a real model must **beat** — useful
   precisely because it is not flattering.
2. **92.1% coverage against an 80% nominal interval means the interval is
   conservative** (too wide), not that the point forecast is good. Reported as
   measured, including the unflattering interpretation.
3. **`foundation_models_available` is `false` where `torch` is not installed**, so
   every live forecast is that fallback. The `/api/accuracy` response states this
   rather than hiding it.

To regenerate on a host with live data access:

```bash
python scripts/publish_accuracy.py --weeks 260   # refuses to publish on demo-only data
```

The publisher also refuses to run on the demo-seeded rows
(`source='demo_seed'`) and reports how many synthetic rows it ignored — publishing
a MAPE from those would fabricate a claim.

## Why this is a sales asset

Enterprise buyers, insurers and auditors do not accept "trust us". The artifact
store gives them: a named model, a named target, a named evaluation method, the
sample size, the window, the measured error, and a machine-readable record of
whether a fallback was involved — all retrievable by `artifact_id` for audit.
