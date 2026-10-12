"""
Module import ratchet (Session 41, found via the ruff F821 sweep).

Every module under `core/` must import cleanly. Two modules were broken since
creation (a nonexistent `ShortTermForecast` import, a nonexistent
`_temperature_growth_factor` import) because no test ever imported them —
this walk catches that class of wiring breakage forever.

Known-good state is an EMPTY failure set. If a module legitimately cannot be
imported in the test environment (heavy native dep etc.), the module must be
guarded internally, not allowlisted here.
"""
import importlib
import pkgutil

import core

# Modules that are permitted to fail import in the test environment.
# Must stay EMPTY; entries require a comment with the reason + issue link.
KNOWN_IMPORT_FAILURES: set[str] = set()


def _walk_failures() -> dict[str, str]:
    failures: dict[str, str] = {}
    for mod in pkgutil.walk_packages(core.__path__, prefix="core."):
        try:
            importlib.import_module(mod.name)
        except Exception as exc:  # noqa: BLE001 - collect everything, assert below
            failures[mod.name] = f"{type(exc).__name__}: {exc}"[:160]
    return failures


def test_all_core_modules_import():
    failures = _walk_failures()
    unexpected = {k: v for k, v in failures.items() if k not in KNOWN_IMPORT_FAILURES}
    assert not unexpected, (
        "core modules fail to import (fix the wiring or guard heavy deps):\n"
        + "\n".join(f"  {k} -> {v}" for k, v in sorted(unexpected.items()))
    )


def test_known_failures_list_is_not_stale():
    """If a listed module imports again, remove it from the allowlist."""
    failures = _walk_failures()
    stale = KNOWN_IMPORT_FAILURES - set(failures)
    assert not stale, f"remove fixed modules from KNOWN_IMPORT_FAILURES: {sorted(stale)}"
