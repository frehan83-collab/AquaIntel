"""
Treatment Constants — Single Source of Truth
==============================================
Shared between decision_engine.py and treatment_optimizer.py.

Efficacy values are harmonized from peer-reviewed literature:
  - Overton et al. (2019) "Salmon lice treatments and mortality":
    https://onlinelibrary.wiley.com/doi/10.1111/raq.12299
  - Mowi Industry Handbook 2024 (published treatment efficacy ranges)
  - Norwegian Veterinary Institute annual lice treatment reports

Resistance-adjusted values reflect 2024-2025 status per production area.
H2O2 efficacy significantly declined due to resistance spread:
  https://www.globalseafood.org/advocate/sea-lice-fight-salmon-farmers-phasing-hydrogen-peroxide/

Mortality constants from Mowi Handbook: ~85% seawater survival over
~18 months production cycle = daily mortality ~0.00028.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TreatmentProfile:
    """Immutable treatment profile with literature-cited values."""
    key: str
    label: str
    efficacy_pct: float          # Mid-range from literature (Overton et al. 2019)
    efficacy_range: tuple[float, float]  # Low-high range from published studies
    mortality_risk_pct: float    # Expected treatment mortality
    cost_per_fish_nok: float     # Average cost per fish treated
    recovery_weeks: int          # Weeks before re-treatment advisable
    suitable_temp_range: tuple[float, float]  # Celsius
    environmental_impact: str    # low / medium / high
    resistance_risk: str         # none / emerging / high
    notes: str = ""


# Harmonized treatment profiles — literature-cited values
# Efficacy represents mid-range of published data for 2024-2025
TREATMENT_PROFILES = {
    "mechanical": TreatmentProfile(
        key="mechanical",
        label="Mechanical (Hydrolicer/Optilicer)",
        efficacy_pct=83.0,          # Overton: 75-90%, mid=83
        efficacy_range=(75.0, 90.0),
        mortality_risk_pct=1.25,    # Overton: 0.5-3%, mid=1.25
        cost_per_fish_nok=3.0,
        recovery_weeks=6,
        suitable_temp_range=(4, 18),
        environmental_impact="low",
        resistance_risk="none",
        notes="Best all-round option. Avoid during smolt windows.",
    ),
    "thermal": TreatmentProfile(
        key="thermal",
        label="Thermal (Thermolicer)",
        efficacy_pct=92.0,          # Overton: 90-95%, mid=92
        efficacy_range=(90.0, 95.0),
        mortality_risk_pct=2.0,     # Highest mortality risk — Overton: elevated for 31% of treatments
        cost_per_fish_nok=4.0,
        recovery_weeks=8,
        suitable_temp_range=(6, 14),  # Welfare concerns above 12°C — tightened from (6,16)
        environmental_impact="low",
        resistance_risk="none",
        notes="Highest efficacy but highest mortality. Welfare risk above 12°C.",
    ),
    "freshwater": TreatmentProfile(
        key="freshwater",
        label="Freshwater Treatment",
        efficacy_pct=81.0,          # Literature: 75-87%, mid=81
        efficacy_range=(75.0, 87.0),
        mortality_risk_pct=0.8,
        cost_per_fish_nok=4.5,
        recovery_weeks=6,
        suitable_temp_range=(4, 20),
        environmental_impact="low",
        resistance_risk="none",
        notes="Effective against AGD as well as lice. Requires freshwater source.",
    ),
    "medicinal_bath": TreatmentProfile(
        key="medicinal_bath",
        label="Medicinal Bath (Azamethiphos)",
        efficacy_pct=72.0,          # Declining due to resistance — was 80%, now 60-80% regionally
        efficacy_range=(55.0, 80.0),
        mortality_risk_pct=0.3,
        cost_per_fish_nok=1.5,
        recovery_weeks=4,
        suitable_temp_range=(4, 16),
        environmental_impact="medium",
        resistance_risk="emerging",
        notes="Lower mortality but resistance emerging in PA 3-7. Monitor local sensitivity.",
    ),
    "medicinal_h2o2": TreatmentProfile(
        key="medicinal_h2o2",
        label="Medicinal Bath (Hydrogen Peroxide)",
        efficacy_pct=60.0,          # SIGNIFICANTLY declined — was 85%, now 40-70% due to widespread resistance
        efficacy_range=(40.0, 70.0),
        mortality_risk_pct=2.0,
        cost_per_fish_nok=2.0,
        recovery_weeks=4,
        suitable_temp_range=(4, 14),
        environmental_impact="medium",
        resistance_risk="high",
        notes="Efficacy severely reduced by resistance. Phase-out recommended in most PAs.",
    ),
    "medicinal_feed": TreatmentProfile(
        key="medicinal_feed",
        label="Medicinal In-Feed (Emamectin Benzoate)",
        efficacy_pct=85.0,          # Still effective where sensitivity remains
        efficacy_range=(75.0, 90.0),
        mortality_risk_pct=0.1,
        cost_per_fish_nok=2.0,
        recovery_weeks=10,
        suitable_temp_range=(4, 18),
        environmental_impact="medium",
        resistance_risk="emerging",
        notes="Long-lasting. 6-week withdrawal before harvest. Monitor sensitivity.",
    ),
    "biological": TreatmentProfile(
        key="biological",
        label="Cleaner Fish (Lumpfish/Wrasse)",
        efficacy_pct=30.0,          # Highly variable: 10-50% depending on stocking density, species, season
        efficacy_range=(10.0, 50.0),
        mortality_risk_pct=0.0,
        cost_per_fish_nok=5.0,
        recovery_weeks=0,
        suitable_temp_range=(4, 16),
        environmental_impact="low",
        resistance_risk="none",
        notes="Preventive, not curative. Deploy early. High cleaner fish mortality in winter.",
    ),
}

# Regulatory thresholds — Norwegian aquaculture regulations
REGULATORY_LIMIT = 0.5       # Adult female lice per fish — mandatory treatment trigger
TREATMENT_TRIGGER = 0.3      # Warning level — schedule treatment
MONITORING_THRESHOLD = 0.1   # Low level — routine monitoring

# Biological constants — Mowi Industry Handbook 2024
DAILY_MORTALITY_RATE = 0.00028    # ~85% seawater survival over 18 months (Mowi Handbook)
FISH_PER_CAGE = 200_000           # Standard Norwegian full-size sea cage
GROWTH_REDUCTION_PER_LICE = 0.03  # 3% SGR reduction per adult female louse (estimated)
MORTALITY_PER_LICE_WEEK = 0.005   # 0.5% additional mortality per louse per week at high loads
