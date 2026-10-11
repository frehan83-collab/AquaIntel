---
name: data-honesty
description: FishIntel honesty layer rules - how to mark fallback/degraded data, make truthful accuracy claims, and label model availability. Use whenever touching ML outputs, provenance, or accuracy statements.
---

# Data Honesty Layer

The platform's brand promise: *every number traceable, never fabricated.*
AGENTS.md rules 1 and 4 are enforced in review.

## Provenance

| Situation | Call |
|---|---|
| Live authoritative fetch (SSB, FRED, BarentsWatch) | `DataProvenance.live(source, confidence=0.9)` |
| ML engine result dict (may be fallback) | `DataProvenance.from_model_result(result, source)` |
| Known-degraded / fetch failed | `DataProvenance.degraded(source, reason, confidence=0.5)` |
| Synthetic/demo only | `DataProvenance.simulated(reason)` |

`from_model_result` detects `model="...-fallback"`, `fallback: True`, and
`error` keys. Never wrap a fallback result in `.live()` — that is the exact
bug class that made "3 foundation models" claim 3 seasonal-naives.

## Ensemble / multi-model responses

- `models_used`: only models that produced real output.
- `models_fallback`: models that fell back (still report them!).
- Provenance `is_live` iff ≥1 real model ran.
- Never write "ensemble of N" where N counts fallbacks.

## Accuracy claims (price_ml contract)

- MAPE / coverage numbers may ONLY come from
  `data/models/price_backtest.json` written by a real backtest, matched
  against the running `model_version`.
- Otherwise the `accuracy_statement` must say plainly that no validated
  backtest is on record.
- Reference tables (`REFERENCE_HORIZON_MAPE`) are internal tuning — never
  displayed as measured results.

## Model availability labels

- A model id must match what is actually loaded (e.g. default
  `amazon/chronos-2` via `FISHINTEL_CHRONOS_MODEL`; the response `model`
  field carries the real id).
- `tft_predictor.is_available` checks importability, not just file existence.
- Docs/UI claiming "TimesFM 2.5 + Chronos-2 + MOIRAI-2" must reflect runtime
  state; in CPU-only dev, the honest answer is "seasonal-naive fallback".

## Verification

```bash
python -m pytest tests/ -k "provenance or ensemble or price" -q
python -c "from fastapi.testclient import TestClient; from core.api import app; \
  print(TestClient(app).get('/api/ml/ensemble/price-forecast').json()['data_provenance'])"
```
Expect `is_live: false` whenever models aren't installed on this box.
