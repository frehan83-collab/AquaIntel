"""Bloom context — the dated facts that make a chlorophyll band decision-relevant.

WS-34 (2026-10-18). The chlorophyll band on ``/bloom`` describes biomass; on its own
it does not tell a farmer whether the region has a history of fish-killing blooms, what
the official advisory says this week, or what the instrument cannot see. This module
carries those three pieces as **dated, sourced facts**:

* :data:`IMR_ALGEINFO` — IMR's weekly Algestatus map. It has **no API** (verified
  2026-10-18), so nothing here scrapes it: the platform links to it and states when the
  link was last checked. A "current" label would be a claim we cannot make.
* :data:`REGIONAL_EVENTS` — documented harmful-algal-bloom mortality events in
  Norwegian salmon farming, with species, area, loss and a primary/secondary source.
  This is a base-rate statement, not a probability.
* :func:`limitations` — what the chlorophyll product cannot see, written once so the
  page and any future surface cannot drift.

Rule (AGENTS.md rule 1): every number here is a published figure with a citation, and
nothing here predicts a bloom.
"""
from __future__ import annotations

#: The official Norwegian HAB advisory. Weekly, qualitative, region-level, manual.
IMR_ALGEINFO = {
    "name": "IMR Algestatus",
    "publisher": "Institute of Marine Research (Havforskningsinstituttet)",
    "url": "https://algestatus.hi.no/",
    "cadence": "weekly",
    "format": "web map + weekly status report",
    "api": None,
    "api_note": (
        "No machine-readable interface was found when this was verified (2026-10-18). "
        "The platform links to the report and never presents a scraped copy as current."
    ),
    "checked_at": "2026-10-18",
    "use": (
        "The authoritative human reference for which potentially harmful taxa are "
        "present. Confirm species and toxicity there and with site cell counts before "
        "acting; a satellite chlorophyll band cannot substitute for it."
    ),
}

#: Documented mortality events in Norwegian salmon farming. Loss figures are the
#: published ones, not platform estimates. No probability is implied by this list.
REGIONAL_EVENTS = (
    {
        "year": 2019,
        "period": "May 2019",
        "species": "Chrysochromulina leadbeateri",
        "areas": "Nordland / Troms (PO9-PO10)",
        "loss": "8 M fish, 13 200-14 500 t",
        "value_nok": "NOK 2.4 bn potential sales value",
        "source": "Directorate of Fisheries (2019); Fon et al. (2024); NRK",
        "source_url": (
            "https://www.nrk.no/nordland/har-ikke-sett-lignende-pa-flere-tiar_-_-fisk-til-en-"
            "verdi-av-2_4-milliarder-er-gatt-tapt-1.14559168"
        ),
    },
    {
        "year": 2025,
        "period": "spring 2025",
        "species": "Chrysochromulina leadbeateri + Phaeocystis pouchetii",
        "areas": "PO9 / PO10 (Fornes, Øksfjorden)",
        "loss": ">2 M fish; 39.5 % acute mortality at one site",
        "value_nok": ">= NOK 300 M for one group",
        "source": "Norwegian Veterinary Institute (2026); SalmonBusiness",
        "source_url": (
            "https://www.salmonbusiness.com/study-reveals-scale-of-destruction-in-2025-"
            "algae-disaster/"
        ),
    },
    {
        "year": 2026,
        "period": "March 2026",
        "species": "Pseudochattonella",
        "areas": "PO1 (Skagerrak coast)",
        "loss": "~1.7 M dead fish in one month; PO1+2 Q1 mortality 13.3 % vs 3.4 % national",
        "value_nok": None,
        "source": "Norwegian Veterinary Institute (2026-05-13)",
        "source_url": "https://www.vetinst.no/nyheter/dodelighet-i-lakseoppdrett-forste-kvartal-2026",
    },
)

#: The one place the instrument's limits are written down.
LIMITATIONS = (
    "Chlorophyll-a is biomass, not toxicity: a high band means more phytoplankton, and "
    "it names no species.",
    "One pixel is kilometres wide (4 km for the gap-free product), so the reading is "
    "regional — never a farm-level measurement.",
    "Subsurface and pycnocline blooms are invisible to ocean colour; the 2019 "
    "C. leadbeateri concentrations sat around 12 m.",
    "The gap-free product is interpolated by construction (about half of ocean-colour "
    "pixels are missing globally, more at high latitudes), so a cloudy week is partly "
    "model.",
    "No Norwegian chlorophyll threshold for farm mortality is published; the bands are "
    "monitoring aids, and there is no published operational species-level HAB forecast "
    "for the fish-killing taxa.",
)


def context() -> dict:
    """The dated context block served beside the chlorophyll band."""
    return {
        "imr_algeinfo": dict(IMR_ALGEINFO),
        "regional_events": [dict(event) for event in REGIONAL_EVENTS],
        "limitations": list(LIMITATIONS),
        "measurement": "chlorophyll-a biomass (satellite), not toxicity",
        "note": (
            "The event list is a base rate, not a probability: about five lethal blooms "
            "in 35 years nationally, two of them within 14 months (2025, 2026)."
        ),
    }
