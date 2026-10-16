"""Provenance ratchet: freeze or verify the non-exempt /api route inventory.

    python scripts/provenance_ratchet.py            # verify (exit 1 on drift)
    python scripts/provenance_ratchet.py --update   # freeze after a decision

Deterministic and offline — the runtime provenance *measurement* stays in
`scripts/probe_liveness.py`; this gate only guarantees that a new data route cannot
appear without someone recording a provenance decision.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.provenance_register import (  # noqa: E402
    BASELINE_PATH,
    inventory,
    write_baseline,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="freeze the baseline")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if args.update:
        payload = write_baseline()
        print(
            f"froze {len(payload['registered'])} non-exempt /api GET route(s) "
            f"-> {BASELINE_PATH}"
        )
        return 0

    data = inventory()
    if args.json:
        import json

        print(json.dumps(data, indent=2))
    else:
        print(
            f"{data['total']} /api GET routes: {len(data['exempt'])} exempt, "
            f"{len(data['registered'])} baselined, {len(data['unregistered'])} "
            f"unregistered"
        )
        for path in data["unregistered"]:
            print(f"  UNREGISTERED {path}")

    if data["unregistered"]:
        print(
            "\nA new data route must either carry provenance "
            "(`@with_provenance(...)` from core.market.provenance_envelope) or be "
            "added to core/provenance_register.EXEMPT with a written reason, then "
            "re-run with --update."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
