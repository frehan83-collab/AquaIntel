"""
Tests for standardized domain errors and global exception handling.
"""
from starlette.testclient import TestClient

from core.errors import UpstreamUnavailable, ResourceNotFound, ErrorBody


def test_error_body_model():
    body = ErrorBody(error="not_found", detail="Locality 99999 not found", request_id="req-123")
    data = body.model_dump()
    assert data["error"] == "not_found"
    assert data["detail"] == "Locality 99999 not found"
    assert data["request_id"] == "req-123"
    assert "timestamp" in data


def test_upstream_unavailable_handler():
    from core.api import app
    client = TestClient(app, raise_server_exceptions=False)

    @app.get("/api/test-upstream-failure")
    async def _test_fail():
        raise UpstreamUnavailable(service="BarentsWatch", detail="API timeout", retry_after=45)

    r = client.get("/api/test-upstream-failure", headers={"x-request-id": "trace-test-abc"})
    assert r.status_code == 503
    assert r.headers["retry-after"] == "45"
    data = r.json()
    assert data["error"] == "upstream_unavailable"
    assert data["detail"] == "API timeout"
    assert data["request_id"] == "trace-test-abc"
    assert data["context"]["service"] == "BarentsWatch"


def test_domain_error_handler():
    from core.api import app
    client = TestClient(app, raise_server_exceptions=False)

    @app.get("/api/test-not-found")
    async def _test_nf():
        raise ResourceNotFound("Production Area 99 not configured")

    r = client.get("/api/test-not-found", headers={"x-request-id": "trace-nf-xyz"})
    assert r.status_code == 404
    data = r.json()
    assert data["error"] == "not_found"
    assert data["detail"] == "Production Area 99 not configured"
    assert data["request_id"] == "trace-nf-xyz"
