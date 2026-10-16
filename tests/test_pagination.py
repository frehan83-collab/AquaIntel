"""
Pagination contract tests (arch report §4.4).

- Helper contract (PageParams/paginate slicing + envelope).
- Wave-1 bounds: previously-unbounded `limit` params now reject >1000 with 422
  (pure validation change — defaults unchanged).
"""
import pytest
from starlette.testclient import TestClient

from core.api import app
from core.pagination import PageParams, paginate


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestPageHelper:
    def test_slice_and_total(self):
        items = list(range(250))
        out = paginate(items, PageParams(limit=100, offset=100))
        assert out["items"] == list(range(100, 200))
        assert out["total"] == 250
        assert out["limit"] == 100 and out["offset"] == 100

    def test_tail_slice(self):
        out = paginate(list(range(10)), PageParams(limit=100, offset=5))
        assert out["items"] == [5, 6, 7, 8, 9]


class TestLimitBounds:
    @pytest.mark.parametrize("path", [
        "/api/signals?limit=999999",
        "/api/orders?limit=999999",
        "/api/alerts?limit=999999",
        # /api/audit is admin-gated since the liveness audit (2.5.0): anonymous
        # requests get 401 before query validation, so its limit bound is
        # asserted in tests/test_route_liveness_contract.py instead.
    ])
    def test_oversized_limit_rejected(self, client, path):
        r = client.get(path)
        assert r.status_code == 422, f"{path} accepted an unbounded limit"

    def test_default_limit_still_works(self, client):
        r = client.get("/api/signals")
        assert r.status_code == 200
