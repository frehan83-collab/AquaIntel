"""
Prometheus metrics endpoint test (review L7)
============================================
`core/api.py` registers prometheus-fastapi-instrumentator at import time
(guarded by ImportError) — the /api/metrics/prometheus endpoint exists
whenever the dependency is installed, which is the case in CI and the
Docker image (requirements.lock). Locally, if the package is missing,
this test skips instead of failing.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from core.api import app

    return TestClient(app)


def test_prometheus_metrics_endpoint_exposes_metrics(client):
    pytest.importorskip("prometheus_fastapi_instrumentator")
    r = client.get("/api/metrics/prometheus")
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")
    # A couple of representative instrumentator series must be present
    body = r.text
    assert "http_requests" in body or "http_request" in body


def test_prometheus_endpoint_not_in_openapi_schema(client):
    # include_in_schema=False — the metrics endpoint stays out of the
    # frozen API contract (docs/openapi.frozen.json).
    from core.api import app

    spec = app.openapi()
    assert "/api/metrics/prometheus" not in spec.get("paths", {})