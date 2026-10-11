---
name: security-hardening
description: FishIntel security patterns - require_admin, ownership checks, SSRF validation, JWT rules, safe registration. Use when touching auth, admin routes, webhooks, or any user-scoped endpoint.
---

# Security Hardening Patterns

Session 38 flagged 4 CRITICAL issues; they are fixed. Do not regress them.
Full rules: AGENTS.md § Non-negotiable rules 2.

## 1. Protecting routes

```python
# Admin/ops only (router-level):
router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])
# or single endpoint:
@app.get("/api/cache/stats", dependencies=[Depends(require_admin)])

# User-scoped:
async def my_route(user: TokenPayload = Depends(get_current_user)):
    if user is None:
        raise HTTPException(401, "Authentication required")
    # ownership: hook.user_id == user.user_id, else 403 (admins bypass)
```

`require_admin` = valid JWT **and** (`User.role == "admin"` OR email in
`FISHINTEL_ADMIN_EMAILS`). Returns 401 without credentials, 403 for
authenticated non-admins.

## 2. Never trust client-supplied identity

- `user_id` in request body/query → IGNORE; use token `user.user_id`.
- Registration: roles are whitelisted (`_ALLOWED_SELF_SERVE_ROLES` in
  `auth_routes.py`); never allow `admin` self-service.

## 3. SSRF guard for outbound URLs

```python
from core.security import validate_public_url   # low-level, raises ValueError
from core.routers.webhook_routes import validate_webhook_url  # HTTP wrapper, raises 400

await validate_webhook_url(url)   # at creation AND at dispatch time
```
Layers: hostname blocklist → literal-IP checks (incl. inet_aton shorthand
like `127.1`) → **DNS resolution via getaddrinfo; every resolved address must
be public** (fails closed on unresolvable hosts). The webhook dispatcher
(`send_to_webhook`) re-validates automatically before every POST — any
outbound-calling code must do the same.

## 4. JWT rules

- `FISHINTEL_ENV=production` requires `FISHINTEL_JWT_SECRET` ≥32 chars,
  rejects known-weak values — startup fails fast (verified behavior).
- Never log secrets; never commit `.env` (only `.env.example`).

## 5. Verification

```bash
python scripts/smoke_security.py
# expects: 401s on admin/webhooks, 400s on SSRF probes,
#          register-as-admin -> farmer, non-admin token -> 403
python -m pytest tests/test_api_routes.py -k "admin or webhook" -q
```

## 6. Adding a protected endpoint — test contract

Every protected endpoint needs BOTH tests:
- no credentials → 401
- non-admin credentials → 403 (if admin-only)
Use the `admin_client` fixture in `tests/test_api_routes.py`.
