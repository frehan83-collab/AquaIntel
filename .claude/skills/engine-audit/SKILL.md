---
name: engine-audit
description: Detect missing-await bugs (coroutine-never-awaited) across the FishIntel codebase - the recurring bug class that silently killed farm_graph, regime_detector, biomass outlook, federated benchmark, ESG and the LLM tools. Use before releases and whenever an engine "returns empty" or a feature seems dead.
---

# Engine Audit — Missing-Await Sweep

## Why this exists

This platform's most expensive recurring bug class: an `async def` called
without `await` — the coroutine is created, never runs, and the feature
silently degrades (empty lists, "0 results", soft-200 "Computation failed").
Fixed instances so far: `farm_graph.build_graph`, `regime_detector.build`,
`biomass_predictor.compute_outlook` (+ `_load_current_state`), `esg_scorer.get_all`,
`federated_benchmark._get_company_data`, `pairs_engine._get_biological_overlay`,
`lice_gnn.build_training_data_from_db`, `llm/tools.get_farm_network_risk`,
`chat_agent`/`morning_brief` ESG blocks.

## The sweep (run after any engine work)

1. AST scan: collect every `async def` name in `core/`, `agents/`, `scripts/`;
   find `Call` nodes whose callee name matches an async name but which are NOT
   wrapped in `Await` — flag them. (Session-40 implementation found ~150
   candidates; most are name-collision false positives.)
2. For each candidate, resolve the ACTUAL class/function via `ast` (file of the
   object, not the name globally) — the collision list to expect:
   `predict` (sklearn/xgb/darts — sync), `close` (xarray/h5py — sync),
   `get_alerts` (regime/alert engines — sync), `execute` (sync SQLA sessions in
   thread-wrapped `*_sync` helpers), `acquire` (threading.Lock),
   `create_task(...)` call sites (intentionally not awaited),
   `gather(...)` tuple members (awaited by gather).
3. Real hits → fix with `await`; if the enclosing function is sync but callers
   are async, convert the chain to async (as done for `pairs_engine` /
   `federated_benchmark`) — never call `asyncio.run()` inside the loop.
4. Regression-test each fix through the HTTP layer (`TestClient`), asserting
   the field that used to be empty is now populated — status-code-only tests
   do NOT catch this bug class.

## Runtime smoke (catches what statics miss)

```bash
python -m pytest tests/ -q -W error::RuntimeWarning -k "route or engine"
# a "coroutine ... was never awaited" RuntimeWarning is the smoking gun
```
Also grep logs for: `Computation failed`, `: 0`, `not available` right after
deploys of any engine change.
