---
name: release
description: FishIntel release ritual - version bump, docs/status refresh, full verification gates, commit/push, tag and release notes. Use when shipping a new version or a milestone of work to GitHub.
---

# Release Ritual (FishIntel)

> Repo: frehan83-collab/AquaIntel · default branch **master** (CI runs on master+main).
> Platform version lives in exactly ONE place: `core/version.py` (`PLATFORM_VERSION`).

## 1. Pre-flight (all must be green)

```bash
# Backend
python -m pytest tests/ -q --tb=line -W ignore        # expect 0 FAILED (background pattern - see run-tests skill)
python scripts/smoke_security.py                       # 401s/403s/400s as specified
# Frontend (if frontend touched)
cd frontend && npx tsc --noEmit && npm run build
```

## 2. Version bump
- Edit `core/version.py` → `PLATFORM_VERSION = "X.Y.Z"` (semver; bump minor for
  features, patch for fixes). `API_SCHEMA_VERSION` only on contract change.
- Sanity: `python -c "from core.api import app; print(app.version)"`.

## 3. Docs
- `PROJECT_STATUS.md`: "Last updated" date+session, Platform Stats table
  (routes = `len(app.routes)`, routers = count of `core/routers/*_routes.py`,
  tests = collect count), Endpoints-by-Domain table if routers changed.
- `CHANGELOG.md`: add a section for the release; entries grouped
  Added/Fixed/Changed, each one line, referencing the commit hashes.
- Update the relevant `.claude/skills/*` if a convention changed.

## 4. Review (mandatory — AGENTS.md rule 7)
Run the `code-review` skill against the full diff of the release range:
`git diff <last-tag>..HEAD`. Any BLOCKER → fix before tagging.

## 5. Ship
```bash
git add -A && git commit -m "release: vX.Y.Z"
git push origin master
git tag -a vX.Y.Z -m "FishIntel vX.Y.Z" && git push origin vX.Y.Z
```
Verify `origin/master` matches local (`git log --oneline -1 origin/master`)
— the PowerShell stderr noise from `git push` is NOT a failure; confirm via log.

## 6. Release notes (GitHub)
`git log --oneline <prev-tag>..vX.Y.Z` → summarise into the GitHub release.
Every claim must map to a real commit (data-honesty rule).
