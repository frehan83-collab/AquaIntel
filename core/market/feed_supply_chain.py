"""
Feed Supply Chain Intelligence Engine
=======================================
Tracks feed ingredient sourcing, supplier risk, and EUDR deforestation compliance.
Models the soy -> fishmeal -> feed -> salmon cost chain with origin tracing.

Key ingredients tracked: soy, fishmeal, fish oil, wheat, rapeseed oil,
micronutrients, astaxanthin (pigment).

EU Deforestation Regulation (EUDR):
  - Regulation (EU) 2023/1115, effective 30 Dec 2024
  - Requires due diligence on commodities linked to deforestation
  - Soy is a regulated commodity; fishmeal/fish oil are NOT regulated
  - High-risk origins: Brazil (Cerrado/Amazon), Argentina, Paraguay

Feed is ~40% of salmon production cost. Soy protein concentrate (SPC) is
the largest single plant-based ingredient by weight in Norwegian salmon feed.

Reference: BioMar Sustainability Report 2024, IFFO Marine Ingredients,
           Skretting Sustainability Report 2024, Mowi Industry Handbook 2024.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum

import structlog

log = structlog.get_logger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class EUDRRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class FeedIngredient:
    """Single feed ingredient with origin tracing and risk assessment."""
    name: str
    origin_country: str
    supplier: str
    weight_pct: float          # % of total feed by weight
    cost_nok_per_kg: float     # cost per kg of this ingredient
    carbon_kg_co2_per_kg: float  # carbon footprint per kg
    eudr_risk: EUDRRisk = EUDRRisk.LOW

    @property
    def cost_nok_per_tonne(self) -> float:
        return self.cost_nok_per_kg * 1000


@dataclass
class FeedBatch:
    """A batch of feed from a specific mill."""
    batch_id: str
    feed_mill: str
    date: dt.date
    ingredients: list[FeedIngredient]
    total_cost_nok_per_tonne: float = 0.0
    total_carbon_kg_co2_per_tonne: float = 0.0
    eudr_compliant: bool = True

    def __post_init__(self) -> None:
        if self.ingredients and self.total_cost_nok_per_tonne == 0.0:
            self.total_cost_nok_per_tonne = sum(
                ing.cost_nok_per_kg * (ing.weight_pct / 100) * 1000
                for ing in self.ingredients
            )
            self.total_carbon_kg_co2_per_tonne = sum(
                ing.carbon_kg_co2_per_kg * (ing.weight_pct / 100) * 1000
                for ing in self.ingredients
            )
            self.eudr_compliant = all(
                ing.eudr_risk in (EUDRRisk.LOW, EUDRRisk.MEDIUM)
                for ing in self.ingredients
            )


@dataclass
class SupplyChainRisk:
    """Aggregate supply chain risk assessment."""
    risk_level: str              # low, medium, high, critical
    risk_factors: list[str]
    eudr_status: str             # compliant, partial, non_compliant
    deforestation_pct: float     # % of feed linked to deforestation-risk origins
    recommendation: str
    assessed_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))


# ── Default USD/NOK for cost conversion ─────────────────────────────────────
_DEFAULT_USDNOK = 10.5


class FeedSupplyChainEngine:
    """
    Models the complete feed supply chain from raw ingredients to salmon farm.

    Integrates with FeedCostEngine for live ingredient prices. Adds origin
    tracing, EUDR compliance assessment, and alternative sourcing scenarios.
    """

    _cache_ttl = dt.timedelta(hours=1)
    _last_fetch: dt.datetime | None = None
    _cached_summary: dict | None = None

    def get_standard_feed_composition(self) -> list[FeedIngredient]:
        """
        Returns typical Norwegian salmon feed composition (7 ingredients).

        Source: BioMar/Skretting sustainability reports, IFFO Marine Ingredients.
        Prices approximate 2025 global commodity rates in NOK (via USD × 10.5).
        """
        return [
            FeedIngredient(
                name="Soy Protein Concentrate",
                origin_country="Brazil",
                supplier="Cargill / Caramuru",
                weight_pct=18.0,
                cost_nok_per_kg=4.73,     # ~$450/t × 10.5 / 1000
                carbon_kg_co2_per_kg=2.8,
                eudr_risk=EUDRRisk.HIGH,
            ),
            FeedIngredient(
                name="Fishmeal",
                origin_country="Peru / Nordic",
                supplier="TASA / Pelagia",
                weight_pct=14.0,
                cost_nok_per_kg=14.70,    # ~$1,400/t × 10.5 / 1000
                carbon_kg_co2_per_kg=1.2,
                eudr_risk=EUDRRisk.LOW,
            ),
            FeedIngredient(
                name="Fish Oil",
                origin_country="Peru / Nordic",
                supplier="TASA / Pelagia",
                weight_pct=11.0,
                cost_nok_per_kg=29.40,    # ~$2,800/t × 10.5 / 1000
                carbon_kg_co2_per_kg=1.5,
                eudr_risk=EUDRRisk.LOW,
            ),
            FeedIngredient(
                name="Wheat",
                origin_country="EU (France/Germany)",
                supplier="Cargill / Bunge",
                weight_pct=13.0,
                cost_nok_per_kg=2.63,     # ~$250/t × 10.5 / 1000
                carbon_kg_co2_per_kg=0.5,
                eudr_risk=EUDRRisk.LOW,
            ),
            FeedIngredient(
                name="Rapeseed Oil",
                origin_country="EU / Canada",
                supplier="Bunge / Cargill",
                weight_pct=16.0,
                cost_nok_per_kg=9.45,     # ~$900/t × 10.5 / 1000
                carbon_kg_co2_per_kg=1.1,
                eudr_risk=EUDRRisk.LOW,
            ),
            FeedIngredient(
                name="Micro-nutrients",
                origin_country="Various",
                supplier="DSM / BASF",
                weight_pct=4.0,
                cost_nok_per_kg=31.50,    # ~$3,000/t × 10.5 / 1000
                carbon_kg_co2_per_kg=0.8,
                eudr_risk=EUDRRisk.LOW,
            ),
            FeedIngredient(
                name="Astaxanthin",
                origin_country="Netherlands",
                supplier="DSM (Carophyll Pink)",
                weight_pct=0.5,
                cost_nok_per_kg=36.75,    # ~$3,500/t × 10.5 / 1000
                carbon_kg_co2_per_kg=3.2,
                eudr_risk=EUDRRisk.LOW,
            ),
        ]

    def assess_eudr_risk(self, ingredients: list[FeedIngredient]) -> SupplyChainRisk:
        """
        Assess EU Deforestation Regulation (EUDR) compliance risk.

        Scores based on:
          - Soy origin (Brazil Cerrado/Amazon = HIGH/CRITICAL)
          - Proportion of feed from deforestation-linked supply chains
          - Documentation completeness (simplified: origin_country presence)
        """
        risk_factors: list[str] = []
        deforestation_weight = 0.0
        max_risk = EUDRRisk.LOW

        for ing in ingredients:
            if ing.eudr_risk in (EUDRRisk.HIGH, EUDRRisk.CRITICAL):
                deforestation_weight += ing.weight_pct
                risk_factors.append(
                    f"{ing.name} ({ing.weight_pct}%): {ing.origin_country} "
                    f"- EUDR {ing.eudr_risk.value} risk"
                )
                if ing.eudr_risk.value > max_risk.value:
                    max_risk = ing.eudr_risk

        # Soy-specific checks
        soy_ingredients = [i for i in ingredients if "soy" in i.name.lower()]
        for soy in soy_ingredients:
            if "brazil" in soy.origin_country.lower():
                risk_factors.append(
                    "Brazilian soy linked to Cerrado/Amazon deforestation risk"
                )
            if "argentina" in soy.origin_country.lower():
                risk_factors.append(
                    "Argentine soy: Gran Chaco deforestation monitoring required"
                )

        # Determine overall status
        if deforestation_weight == 0:
            eudr_status = "compliant"
            risk_level = "low"
            recommendation = "Supply chain is EUDR compliant. Maintain documentation."
        elif deforestation_weight < 10:
            eudr_status = "partial"
            risk_level = "medium"
            recommendation = (
                "Minor EUDR exposure. Consider certified deforestation-free soy "
                "(RTRS/ProTerra) for remaining supply."
            )
        elif deforestation_weight < 25:
            eudr_status = "non_compliant"
            risk_level = "high"
            recommendation = (
                f"{deforestation_weight:.0f}% of feed from high-risk origins. "
                "Urgent: switch to RTRS-certified soy or European protein alternatives "
                "(fava bean, pea protein, insect meal)."
            )
        else:
            eudr_status = "non_compliant"
            risk_level = "critical"
            recommendation = (
                f"{deforestation_weight:.0f}% of feed from high-risk origins. "
                "Critical: immediate supplier audit and transition plan required "
                "for EUDR compliance by enforcement date."
            )

        return SupplyChainRisk(
            risk_level=risk_level,
            risk_factors=risk_factors,
            eudr_status=eudr_status,
            deforestation_pct=round(deforestation_weight, 1),
            recommendation=recommendation,
        )

    def model_cost_scenarios(
        self,
        base: list[FeedIngredient],
        scenarios: list[str] | None = None,
    ) -> list[dict]:
        """
        Model alternative feed sourcing scenarios.

        Scenarios:
          - soy_spike_20pct: Soy price increases 20% (trade disruption/drought)
          - fishmeal_shortage: Fishmeal price increases 40% (El Nino/quota cut)
          - switch_to_insect_meal: Replace 50% of soy with black soldier fly larvae
          - switch_to_algae_oil: Replace fish oil with algae-derived DHA/EPA oil
        """
        if scenarios is None:
            scenarios = [
                "soy_spike_20pct",
                "fishmeal_shortage",
                "switch_to_insect_meal",
                "switch_to_algae_oil",
            ]

        base_cost = sum(
            ing.cost_nok_per_kg * (ing.weight_pct / 100) * 1000
            for ing in base
        )
        base_carbon = sum(
            ing.carbon_kg_co2_per_kg * (ing.weight_pct / 100) * 1000
            for ing in base
        )
        base_risk = self.assess_eudr_risk(base)

        results = [{
            "scenario": "current",
            "label": "Current Baseline",
            "cost_nok_per_tonne": round(base_cost, 0),
            "carbon_kg_co2_per_tonne": round(base_carbon, 0),
            "cost_delta_pct": 0.0,
            "carbon_delta_pct": 0.0,
            "eudr_status": base_risk.eudr_status,
            "eudr_risk_level": base_risk.risk_level,
            "description": "Standard Norwegian salmon feed composition.",
        }]

        for scenario in scenarios:
            modified = [FeedIngredient(**{
                "name": i.name,
                "origin_country": i.origin_country,
                "supplier": i.supplier,
                "weight_pct": i.weight_pct,
                "cost_nok_per_kg": i.cost_nok_per_kg,
                "carbon_kg_co2_per_kg": i.carbon_kg_co2_per_kg,
                "eudr_risk": i.eudr_risk,
            }) for i in base]

            description = ""

            if scenario == "soy_spike_20pct":
                for ing in modified:
                    if "soy" in ing.name.lower():
                        ing.cost_nok_per_kg *= 1.20
                description = "Soy price +20% due to trade disruption or drought."

            elif scenario == "fishmeal_shortage":
                for ing in modified:
                    if "fishmeal" in ing.name.lower():
                        ing.cost_nok_per_kg *= 1.40
                description = (
                    "Fishmeal price +40% due to El Nino anchovy quota reduction."
                )

            elif scenario == "switch_to_insect_meal":
                for ing in modified:
                    if "soy" in ing.name.lower():
                        # Replace 50% of soy with insect meal (BSF larvae)
                        original_pct = ing.weight_pct
                        ing.weight_pct = original_pct * 0.5
                        # Insect meal: ~$1,800/t, lower carbon, EUDR-free
                        insect = FeedIngredient(
                            name="Insect Meal (BSF)",
                            origin_country="Norway / Netherlands",
                            supplier="Invertapro / Protix",
                            weight_pct=original_pct * 0.5,
                            cost_nok_per_kg=18.90,  # ~$1,800/t × 10.5 / 1000
                            carbon_kg_co2_per_kg=0.9,
                            eudr_risk=EUDRRisk.LOW,
                        )
                        modified.append(insect)
                description = (
                    "Replace 50% of soy with black soldier fly larvae. "
                    "Higher ingredient cost but EUDR-free and lower carbon."
                )

            elif scenario == "switch_to_algae_oil":
                for ing in modified:
                    if "fish oil" in ing.name.lower():
                        # Replace fish oil with algae DHA/EPA oil
                        ing.name = "Algae Oil (DHA/EPA)"
                        ing.origin_country = "USA / EU"
                        ing.supplier = "Veramaris (DSM-Evonik JV)"
                        ing.cost_nok_per_kg = 42.00  # ~$4,000/t × 10.5 / 1000
                        ing.carbon_kg_co2_per_kg = 2.0
                        ing.eudr_risk = EUDRRisk.LOW
                description = (
                    "Replace fish oil with algae-derived DHA/EPA (Veramaris). "
                    "Higher cost but eliminates marine ingredient dependency."
                )

            new_cost = sum(
                ing.cost_nok_per_kg * (ing.weight_pct / 100) * 1000
                for ing in modified
            )
            new_carbon = sum(
                ing.carbon_kg_co2_per_kg * (ing.weight_pct / 100) * 1000
                for ing in modified
            )
            new_risk = self.assess_eudr_risk(modified)

            cost_delta = ((new_cost - base_cost) / base_cost) * 100 if base_cost else 0
            carbon_delta = ((new_carbon - base_carbon) / base_carbon) * 100 if base_carbon else 0

            results.append({
                "scenario": scenario,
                "label": {
                    "soy_spike_20pct": "Soy Price Spike (+20%)",
                    "fishmeal_shortage": "Fishmeal Shortage (+40%)",
                    "switch_to_insect_meal": "Insect Meal Substitute",
                    "switch_to_algae_oil": "Algae Oil Substitute",
                }.get(scenario, scenario),
                "cost_nok_per_tonne": round(new_cost, 0),
                "carbon_kg_co2_per_tonne": round(new_carbon, 0),
                "cost_delta_pct": round(cost_delta, 1),
                "carbon_delta_pct": round(carbon_delta, 1),
                "eudr_status": new_risk.eudr_status,
                "eudr_risk_level": new_risk.risk_level,
                "description": description,
            })

        return results

    def get_supply_chain_summary(self) -> dict:
        """
        Returns current feed cost breakdown, EUDR status, carbon footprint,
        and scenario comparison in a single response.
        """
        ingredients = self.get_standard_feed_composition()
        risk = self.assess_eudr_risk(ingredients)
        scenarios = self.model_cost_scenarios(ingredients)

        # Build ingredient breakdown
        composition = []
        for ing in ingredients:
            composition.append({
                "name": ing.name,
                "origin": ing.origin_country,
                "supplier": ing.supplier,
                "weight_pct": ing.weight_pct,
                "cost_nok_per_kg": round(ing.cost_nok_per_kg, 2),
                "cost_nok_per_tonne": round(ing.cost_nok_per_tonne, 0),
                "carbon_kg_co2_per_kg": ing.carbon_kg_co2_per_kg,
                "eudr_risk": ing.eudr_risk.value,
            })

        total_cost = sum(
            ing.cost_nok_per_kg * (ing.weight_pct / 100) * 1000
            for ing in ingredients
        )
        total_carbon = sum(
            ing.carbon_kg_co2_per_kg * (ing.weight_pct / 100) * 1000
            for ing in ingredients
        )

        # Sankey flow data: origin -> ingredient -> feed mill -> farm
        sankey = self._build_sankey_data(ingredients)

        return {
            "timestamp": dt.datetime.now(dt.UTC).isoformat(),
            "composition": composition,
            "total_cost_nok_per_tonne": round(total_cost, 0),
            "total_carbon_kg_co2_per_tonne": round(total_carbon, 0),
            "eudr_risk": {
                "status": risk.eudr_status,
                "level": risk.risk_level,
                "deforestation_pct": risk.deforestation_pct,
                "risk_factors": risk.risk_factors,
                "recommendation": risk.recommendation,
            },
            "scenarios": scenarios,
            "sankey": sankey,
            "data_provenance": {
                "source": "BioMar/Skretting sustainability reports, IFFO, EUDR Reg 2023/1115",
                "freshness": "model_based",
                "confidence": 0.75,
                "note": "Standard composition model with approximate 2025 commodity prices",
            },
        }

    async def get_feed_cost_with_supply_chain(self) -> dict:
        """
        Integrates with existing FeedCostEngine for live FRED prices,
        overlays supply chain origin tracing and EUDR compliance.
        """
        try:
            from core.market.feed_cost_engine import feed_cost_engine
            snapshot = await feed_cost_engine.fetch_prices()

            # Get standard composition and overlay live prices where available
            ingredients = self.get_standard_feed_composition()
            live_mapping = {
                "Soy Protein Concentrate": "soy",
                "Fishmeal": "fishmeal",
                "Fish Oil": "fish_oil",
                "Wheat": "wheat",
                "Rapeseed Oil": "rapeseed",
            }

            for ing in ingredients:
                fred_key = live_mapping.get(ing.name)
                if fred_key and fred_key in snapshot.ingredients:
                    live_price = snapshot.ingredients[fred_key]
                    ing.cost_nok_per_kg = round(
                        live_price.price_usd_per_kg * snapshot.usd_nok, 2
                    )

            risk = self.assess_eudr_risk(ingredients)
            scenarios = self.model_cost_scenarios(ingredients)

            return {
                "timestamp": snapshot.timestamp.isoformat(),
                "usd_nok": snapshot.usd_nok,
                "live_feed_cost_nok_per_kg": round(snapshot.feed_cost_nok_per_kg, 2),
                "live_production_cost_nok": round(snapshot.production_cost_nok_per_kg_salmon, 2),
                "composition": [
                    {
                        "name": ing.name,
                        "origin": ing.origin_country,
                        "weight_pct": ing.weight_pct,
                        "cost_nok_per_kg": round(ing.cost_nok_per_kg, 2),
                        "eudr_risk": ing.eudr_risk.value,
                    }
                    for ing in ingredients
                ],
                "eudr_risk": {
                    "status": risk.eudr_status,
                    "level": risk.risk_level,
                    "deforestation_pct": risk.deforestation_pct,
                    "risk_factors": risk.risk_factors,
                    "recommendation": risk.recommendation,
                },
                "scenarios": scenarios,
                "data_provenance": {
                    "source": "FRED + BioMar/Skretting + EUDR Reg 2023/1115",
                    "freshness": "live" if not feed_cost_engine._using_defaults else "degraded",
                    "confidence": 0.85,
                },
            }
        except Exception as e:
            log.warning("feed_supply_chain.live_overlay_failed", error=str(e))
            return self.get_supply_chain_summary()

    def _build_sankey_data(self, ingredients: list[FeedIngredient]) -> dict:
        """Build Sankey flow data: origin -> ingredient -> feed mill -> farm."""
        nodes = []
        links = []
        node_ids: set[str] = set()

        # Stage 0: Origins
        for ing in ingredients:
            origin_id = f"origin_{ing.origin_country.replace(' ', '_').replace('/', '_')}"
            if origin_id not in node_ids:
                nodes.append({"id": origin_id, "label": ing.origin_country, "column": 0})
                node_ids.add(origin_id)

        # Stage 1: Ingredients
        for ing in ingredients:
            ing_id = f"ing_{ing.name.replace(' ', '_')}"
            if ing_id not in node_ids:
                nodes.append({"id": ing_id, "label": ing.name, "column": 1})
                node_ids.add(ing_id)

            origin_id = f"origin_{ing.origin_country.replace(' ', '_').replace('/', '_')}"
            links.append({
                "source": origin_id,
                "target": ing_id,
                "value": round(ing.weight_pct, 1),
            })

        # Stage 2: Feed mill
        mill_id = "mill_BioMar_Myre"
        nodes.append({"id": mill_id, "label": "BioMar Myre", "column": 2})
        for ing in ingredients:
            ing_id = f"ing_{ing.name.replace(' ', '_')}"
            links.append({
                "source": ing_id,
                "target": mill_id,
                "value": round(ing.weight_pct, 1),
            })

        # Stage 3: Farm
        farm_id = "farm_Norwegian_Salmon"
        nodes.append({"id": farm_id, "label": "Norwegian Salmon Farms", "column": 3})
        links.append({
            "source": mill_id,
            "target": farm_id,
            "value": round(sum(i.weight_pct for i in ingredients), 1),
        })

        return {
            "nodes": nodes,
            "links": links,
            "stages": ["Origin", "Ingredient", "Feed Mill", "Farm"],
        }


# ── Singleton ────────────────────────────────────────────────────────────────
feed_supply_chain = FeedSupplyChainEngine()
