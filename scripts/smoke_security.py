"""Smoke test for security hardening: admin auth, webhook auth, role escalation."""
import sys
import traceback
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from fastapi.testclient import TestClient
    from core.api import app
    from core.auth import create_token

    c = TestClient(app)
    failures = []

    # 1) Admin endpoints: unauthenticated -> 401
    for path in ["/api/admin/status", "/api/admin/cache-stats", "/api/cache/stats"]:
        r = c.get(path)
        print(f"{path}: {r.status_code}")
        if r.status_code != 401:
            failures.append(f"{path} expected 401 got {r.status_code}")

    # 2) Webhooks: unauthenticated -> 401; events stays public
    r = c.get("/api/webhooks")
    print(f"/api/webhooks: {r.status_code}")
    if r.status_code != 401:
        failures.append(f"/api/webhooks expected 401 got {r.status_code}")
    r = c.get("/api/webhooks/events")
    if r.status_code != 200:
        failures.append(f"/api/webhooks/events expected 200 got {r.status_code}")

    # 3) SSRF guard (literal private IPs, internal hostnames, and
    #    inet_aton shorthand forms that bypass naive ipaddress checks)
    token = create_token(1, "ssrf-test@example.com", "free")
    for bad in ["http://127.0.0.1/hook", "http://localhost:9999/x",
                "http://10.0.0.5/h", "http://169.254.169.254/latest/meta-data",
                "http://127.1/hook", "http://0x7f000001/hook",
                "http://2130706433/hook", "http://metadata.google.internal/x"]:
        r = c.post("/api/webhooks", json={"url": bad},
                   headers={"Authorization": f"Bearer {token}"})
        print(f"ssrf {bad}: {r.status_code}")
        if r.status_code != 400:
            failures.append(f"ssrf {bad} expected 400 got {r.status_code}")

    # 4) Registration role escalation
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = c.post("/api/auth/register",
               json={"email": email, "password": "x" * 12, "role": "admin"})
    print(f"register: {r.status_code}")
    if r.status_code == 200:
        role = r.json()["user"]["role"]
        print(f"role after register-as-admin: {role}")
        if role == "admin":
            failures.append("registration allowed role=admin (escalation)")
    else:
        # rate-limited from prior runs is acceptable
        print(f"register body: {r.text[:200]}")

    # 5) Non-admin authenticated user gets 403 on admin endpoints
    r = c.get("/api/admin/status", headers={"Authorization": f"Bearer {token}"})
    print(f"admin with non-admin token: {r.status_code}")
    if r.status_code != 403:
        failures.append(f"non-admin token expected 403 got {r.status_code}")

    print()
    if failures:
        print("FAILURES:")
        for f in failures:
            print(" -", f)
        return 1
    print("ALL SECURITY SMOKE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
