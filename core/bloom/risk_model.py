"""
Algal Bloom Risk Model.

Scores bloom risk per farm locality based on chlorophyll-a concentration,
sea surface temperature, and trend data. Thresholds derived from Norwegian
Institute of Marine Research (Havforskningsinstituttet) guidelines and
historical bloom events (2019 Northern Norway, 2024, 2026 Skagerrak).

Key harmful algae species in Norwegian waters:
- Chrysochromulina leadbeateri — killed 8M+ salmon in 2019
- Karenia mikimotoi — gill damage, oxygen depletion
- Chattonella spp. — gill clogging, reactive oxygen species
- Pseudo-nitzschia — domoic acid (ASP toxin)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class BloomRiskResult:
    """Output of the bloom risk assessment for one locality.

    WS-33: this is a **chlorophyll band**, not a toxicity or mortality probability.
    ``risk_level`` and ``risk_score`` describe how far the satellite chlorophyll
    reading sits above the configured thresholds; they carry no species, toxin or
    harm information, and ``chl_a_trend`` is ``None`` when no earlier observation
    exists (never a silent 0.0).
    """
    risk_level: str  # LOW / ELEVATED / HIGH / CRITICAL — a chlorophyll band
    risk_score: float  # 0-100 index, NOT a probability
    chl_a_value: float
    sst_value: float | None
    chl_a_trend: float | None  # mg/m3 per day; None = no previous observation
    contributing_factors: list[str] = field(default_factory=list)
    #: What the number is and is not — travels with every payload.
    measurement: str = "chlorophyll-a concentration (biomass), not toxicity"
    is_toxicity_measurement: bool = False

    def factors_json(self) -> str:
        return json.dumps(self.contributing_factors)


# ── Thresholds ──────────────────────────────────────────────────────────
# These can be overridden via settings

DEFAULT_CHL_ELEVATED = 2.0   # mg/m3 — above background, watch closely
DEFAULT_CHL_HIGH = 5.0       # mg/m3 — active bloom
DEFAULT_CHL_CRITICAL = 10.0  # mg/m3 — dangerous bloom

# SST "danger window" for harmful species — most bloom events occur 8-15 C
SST_BLOOM_FAVORABLE_MIN = 8.0
SST_BLOOM_FAVORABLE_MAX = 15.0


def compute_bloom_risk(
    chl_a: float,
    sst: float | None = None,
    chl_a_trend: float | None = None,
    chl_elevated: float = DEFAULT_CHL_ELEVATED,
    chl_high: float = DEFAULT_CHL_HIGH,
    chl_critical: float = DEFAULT_CHL_CRITICAL,
) -> BloomRiskResult:
    """
    Compute bloom risk from satellite and in-situ data.

    Args:
        chl_a: Chlorophyll-a concentration in mg/m3
        sst: Sea surface temperature in Celsius (None if unavailable)
        chl_a_trend: Rate of change in chl-a (mg/m3 per day, positive = rising)
        chl_elevated/high/critical: Configurable threshold overrides

    Returns:
        BloomRiskResult with risk level, score, and contributing factors
    """
    factors: list[str] = []
    score = 0.0

    # ── Base score from chlorophyll-a level (0-60 points) ────────────
    if chl_a >= chl_critical:
        score += 60.0
        factors.append(f"Chl-a {chl_a:.1f} mg/m3 exceeds critical threshold ({chl_critical})")
    elif chl_a >= chl_high:
        score += 40.0
        factors.append(f"Chl-a {chl_a:.1f} mg/m3 indicates active bloom (>{chl_high})")
    elif chl_a >= chl_elevated:
        score += 20.0
        factors.append(f"Chl-a {chl_a:.1f} mg/m3 above background (>{chl_elevated})")
    else:
        factors.append(f"Chl-a {chl_a:.1f} mg/m3 within normal range")

    # ── Trend bonus (0-20 points) ────────────────────────────────────
    # WS-33: None means "no earlier observation", not "no change". A missing trend
    # earns no bonus and says so, instead of scoring a fabricated 0.0.
    if chl_a_trend is None:
        factors.append(
            "No previous chlorophyll observation for this cell — trend unavailable"
        )
    elif chl_a_trend > 1.0:
        score += 20.0
        factors.append(f"Rapid chl-a increase: +{chl_a_trend:.2f} mg/m3/day")
    elif chl_a_trend > 0.3:
        score += 10.0
        factors.append(f"Rising chl-a trend: +{chl_a_trend:.2f} mg/m3/day")
    elif chl_a_trend < -0.3:
        score -= 5.0
        factors.append(f"Declining chl-a trend: {chl_a_trend:.2f} mg/m3/day")

    # ── SST modifier (0-20 points) ───────────────────────────────────
    if sst is not None:
        if SST_BLOOM_FAVORABLE_MIN <= sst <= SST_BLOOM_FAVORABLE_MAX:
            score += 20.0
            factors.append(
                f"SST {sst:.1f}C in harmful bloom favorable range "
                f"({SST_BLOOM_FAVORABLE_MIN}-{SST_BLOOM_FAVORABLE_MAX}C)"
            )
        elif sst > SST_BLOOM_FAVORABLE_MAX:
            score += 5.0
            factors.append(f"SST {sst:.1f}C above typical bloom range but still viable")
        else:
            factors.append(f"SST {sst:.1f}C below typical bloom range")

    # ── Clamp score ──────────────────────────────────────────────────
    score = max(0.0, min(100.0, score))

    # ── Determine risk level ─────────────────────────────────────────
    if chl_a >= chl_critical or (chl_a >= chl_high and sst is not None and SST_BLOOM_FAVORABLE_MIN <= sst <= SST_BLOOM_FAVORABLE_MAX):
        risk_level = "CRITICAL"
    elif chl_a >= chl_high:
        risk_level = "HIGH"
    elif chl_a >= chl_elevated and chl_a_trend > 0.3:
        risk_level = "ELEVATED"
    elif chl_a >= chl_elevated:
        risk_level = "ELEVATED"
    else:
        risk_level = "LOW"

    # Ensure score matches level minimums
    level_min_scores = {"LOW": 0, "ELEVATED": 20, "HIGH": 50, "CRITICAL": 75}
    score = max(score, level_min_scores[risk_level])

    return BloomRiskResult(
        risk_level=risk_level,
        risk_score=round(score, 1),
        chl_a_value=chl_a,
        sst_value=sst,
        chl_a_trend=chl_a_trend,
        contributing_factors=factors,
    )
