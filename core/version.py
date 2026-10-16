"""
Single source of truth for platform versioning.

- PLATFORM_VERSION: the API/platform release version reported by FastAPI docs,
  /api/health, /api/status, /api/metrics and startup logs. Bump on release.
- API_SCHEMA_VERSION: version of the *response schema contract* (provenance
  envelope shape, field semantics). Bumped only on additive contract changes
  per the additive-only policy (see docs/summit/REPORT_ARCHITECTURE.md §7).
"""
from __future__ import annotations

PLATFORM_VERSION = "2.5.0"
API_SCHEMA_VERSION = "1.1"
