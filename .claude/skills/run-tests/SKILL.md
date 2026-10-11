---
name: run-tests
description: Correct way to run FishIntel tests on this Windows dev box - avoids the 30s command timeout, handles execution-policy blocks, and defines which suites gate a commit.
---

# Running Tests (FishIntel)

## Quick reference

| Goal | Command |
|---|---|
| Fast smoke (~10s) | `python -m pytest tests/test_critical_engines.py -q --tb=short -W ignore` |
| One area | `python -m pytest tests/test_api_routes.py -q -k "admin"` |
| Security gate | `python scripts/smoke_security.py` |
| Full suite (>30s) | background pattern below |
| Frontend types | `cd frontend && npx tsc --noEmit` |

## Windows-specific rules

- **Never** `pip ...` directly — execution policy blocks `pip.exe`.
  Use `python -m pip ...`.
- The command runner times out at ~30s. For the full suite start a background
  process and poll the output file:
  ```powershell
  Start-Process -FilePath python -ArgumentList '-m','pytest','tests/','-q','--tb=line','-W','ignore' `
    -RedirectStandardOutput pytest_out.txt -RedirectStandardError pytest_err.txt -NoNewWindow
  # ...wait, then...
  Get-Content pytest_out.txt | Select-Object -Last 15
  ```
- Direct `cmd /c "python ... > file 2>&1"` also works for capture.

## Interpreting results

- `xfailed` / `xpassed` are tolerated (non-strict markers exist).
- Optional-dependency tests must use `pytest.importorskip("torch")` — they
  should SKIP on this box (torch is not installed), never FAIL.
- A FAIL in `admin`/`webhook`/`cache` tests usually means an auth-contract
  change: check AGENTS.md security rules before "fixing" the test.
- Known pre-existing local issue: dev SQLite can lag the ORM
  (`no such column`) — reconcile with `PRAGMA table_info` + `ALTER TABLE`.

## Commit gate

All of these must be green before commit: touched-area tests, full suite
(zero FAILED lines), `scripts/smoke_security.py` for security-touching diffs,
`tsc --noEmit` for frontend diffs. Then run the `code-review` skill.
