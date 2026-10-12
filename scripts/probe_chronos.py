"""Diagnostic: verify the configured Chronos model actually loads on CPU.

Reports which pipeline class and model id were used — the engine's response
`model` field mirrors this, so a successful run here means /api/ml/chronos/*
will report live (not fallback) provenance.

Usage: python scripts/probe_chronos.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.ml.chronos_baseline import chronos_baseline

pipeline = chronos_baseline._get_pipeline()
print("loaded:", pipeline is not None, "| model:", chronos_baseline._model_name)
if pipeline is not None:
    print("pipeline class:", pipeline.__class__.__name__)
    import asyncio

    result = asyncio.run(
        chronos_baseline.forecast_series([70.0, 71.0, 72.0, 71.5, 73.0], horizon=4)
    )
    print("forecast model tag:", result.get("model"))
    print("median:", result.get("median"))

