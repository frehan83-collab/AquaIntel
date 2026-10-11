---
name: add-endpoint
description: Add a new API endpoint or engine to FishIntel following the established conventions - router, provenance, caching, typing, tests, frontend client. Use when creating any new route.
---

# Adding an Endpoint / Engine

Follow this checklist exactly (see also CONTRIBUTING.md and AGENTS.md).

## Backend

1. **Router**: add to the appropriate module in `core/routers/` (create a new
   `APIRouter` file only if a whole new domain appears; register it in
   `core/api.py`).
2. **Auth**: decide explicitly —
   - public data (prices, lice summaries): no auth, but emit provenance
   - user-scoped: `Depends(get_current_user)` + ownership vs token `user_id`
   - ops/admin/exports/invalidations: `Depends(require_admin)`
   Document the choice in the docstring.
3. **Engine**: for compute logic, follow the engine pattern —
   ```python
   class MyEngine:
       @cached(ttl=300)
       def analyze(self, key: str) -> dict:
           logger.info("my_engine.analyze", key=key)
           return {"result": ..., "data_provenance": DataProvenance.live("Source", confidence=0.9).to_dict()}
   my_engine = MyEngine()  # singleton at module bottom
   ```
   For ML outputs use `DataProvenance.from_model_result(result, source)`.
4. **Errors**: return the platform error envelope, never a bare 200 with
   `{"error": ...}` for what is really a failure (4xx/5xx), and no bare
   `except: pass`.
5. **External URLs**: validate with `validate_webhook_url()`-style guards.

## Frontend

6. Add a typed method to `frontend/src/lib/api.ts`:
   ```ts
   myEndpoint: (arg: string) => fetchAPI<MyType>(`/api/mypath/${arg}`),
   ```
7. Add response types to `frontend/src/types/api.ts`.

## Verification (required)

8. `python -c "import core.routers.<module>"` (or `ast.parse` for edits).
9. Test hit via TestClient — add a test to `tests/test_api_routes.py` or the
   area-specific file asserting status codes (including the auth denials:
   401 without credentials where protected).
10. Run `python -m pytest tests/ -k "<module>" -q` then the full suite.
11. Run the `code-review` skill on the diff before committing.
