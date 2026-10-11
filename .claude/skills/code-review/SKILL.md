---
name: code-review
description: Mandatory pre-commit code review for FishIntel/AquaIntel. Use before EVERY commit to GitHub - reviews the actual git diff for security, honesty-layer regressions, and convention violations.
---

# Code Review (pre-commit gate)

Every commit to this repository MUST pass an independent review of the actual
diff before it reaches GitHub. See AGENTS.md rule 7.

## Procedure

1. Collect the diff of what will be committed:
   ```bash
   git status --short
   git diff -- <paths-you-touched>
   ```
2. Spawn a review subagent (or review yourself against this checklist) with
   the FULL diff text — never review from memory.

## Checklist (ordered by severity)

### CRITICAL — block the commit
- **Honesty**: any `DataProvenance.live()` applied to output that could be a
  fallback? Fallback-tagged results (`model="...-fallback"`) must use
  `DataProvenance.from_model_result()` or `.degraded()`.
- **Fabricated numbers**: any MAPE/coverage/backtest/price value hardcoded or
  displayed without a real artifact/source? (price_ml accuracy contract)
- **Auth bypass**: new endpoints touching user data, ops data, exports, or
  mutations without auth (`require_admin`, `get_current_user` + ownership)?
- **IDOR**: `user_id` read from request body/query instead of token.
- **SSRF**: external URL accepted without `validate_webhook_url()`.
- **Secrets**: credentials, tokens, or `.env` values in the diff.
- **Model claims**: response claims N models loaded when fallbacks ran.

### HIGH — fix before commit
- Sync DB `Session()` inside async functions (use `get_async_session()`).
- Bare `except: pass` swallowing errors (use structlog warning).
- New endpoint missing from `frontend/src/lib/api.ts` (if frontend needs it).
- Missing test for a bugfix or new feature.
- `HORIZON_MAPE` / reference tables surfaced to users as measured results.

### MEDIUM — note in commit message
- Inconsistent naming vs surrounding code.
- Missing docstring on public function/engine.
- Magic numbers that belong in `config/settings.py`.

## Output format

Return findings as:
```
BLOCKER: <file:line> <issue>
WARN:    <file:line> <issue>
OK:      <summary of what was checked and passed>
```
If BLOCKERs exist: fix them, re-diff, re-review. Only then commit.
