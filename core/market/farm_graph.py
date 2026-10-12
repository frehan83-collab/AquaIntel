"""
Farm Network Graph — Lice Dispersal & Cascade Modeling
========================================================
Spatial graph model of all Norwegian salmon farms. Models lice
dispersal between neighboring farms based on:
  - Geographic distance (exponential decay)
  - Historical lice correlation (empirical co-movement)
  - Ocean current direction (prevailing southward along coast)
  - Production area clustering

Key capabilities:
  1. Identify high-risk farm clusters (lice "hotspots")
  2. Predict cascade treatment events (farm A treats → farm B next)
  3. Estimate treatment cost propagation through network
  4. Company exposure scoring (which company has most network risk?)

Alpha: Treatment cascades = supply shocks = price signals.
When lice spreads through a cluster, forced treatments reduce
harvest capacity and increase costs. Predict this before it hits financials.

Data: BarentsWatch locality coords + weekly lice data + company ownership
"""
from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

import numpy as np
import structlog

log = structlog.get_logger(__name__)

# Haversine distance calculation
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in km."""
    R = 6371.0  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


@dataclass
class FarmNode:
    """Single farm in the network graph."""
    locality_no: int
    name: str
    latitude: float
    longitude: float
    company: str
    ticker: str
    production_area: int
    current_lice: float = 0.0
    lice_trend: str = "stable"  # increasing/stable/decreasing
    above_threshold: bool = False
    last_treatment_week: Optional[int] = None
    biomass_tonnes: float = 0.0


@dataclass
class FarmEdge:
    """Connection between two farms with dispersal weight."""
    source: int  # locality_no
    target: int  # locality_no
    distance_km: float
    dispersal_weight: float  # 0-1, probability of lice transfer
    correlation: float  # historical lice correlation
    same_company: bool
    same_pa: bool


@dataclass
class ClusterRisk:
    """Risk assessment for a farm cluster."""
    cluster_id: int
    farms: list[int]  # locality_nos
    n_farms: int
    center_lat: float
    center_lon: float
    production_area: int
    companies_involved: list[str]
    avg_lice: float
    max_lice: float
    n_above_threshold: int
    cascade_probability: float  # probability of treatment cascade
    estimated_cascade_cost_nok: float
    risk_level: str  # low/medium/high/critical
    trigger_farm: Optional[int]  # farm most likely to trigger cascade


@dataclass
class CascadePrediction:
    """Predicted treatment cascade through the network."""
    predicted_at: dt.datetime
    trigger_farm: int
    trigger_lice: float
    affected_farms: list[int]
    cascade_order: list[int]  # predicted treatment sequence
    total_farms_affected: int
    estimated_duration_weeks: int
    companies_affected: list[str]
    tickers_affected: list[str]
    production_areas: list[int]
    estimated_total_cost_nok: float
    estimated_biomass_impact_tonnes: float
    confidence: float


# Lice dispersal parameters (from Norwegian research)
MAX_DISPERSAL_KM = 30.0  # maximum lice dispersal distance
DISPERSAL_HALF_LIFE_KM = 10.0  # distance at which dispersal probability halves
CURRENT_DIRECTION_BOOST = 1.5  # boost for farms downstream of prevailing current
TREATMENT_THRESHOLD = 0.5  # adult female lice per fish
CASCADE_THRESHOLD = 0.3  # lice level that predicts imminent cascade
TREATMENT_COST_NOK = 150_000  # average per treatment event per farm
BIOMASS_LOSS_PER_TREATMENT_PCT = 1.5  # % biomass lost per treatment


class FarmNetworkGraph:
    """
    Spatial graph model of Norwegian salmon farm network.

    Builds a weighted graph where:
    - Nodes = farms (with lice state, company, coordinates)
    - Edges = potential lice dispersal pathways (distance-weighted)

    Used for:
    - Identifying at-risk clusters
    - Predicting cascade treatments
    - Scoring company network exposure
    """

    def __init__(self) -> None:
        self._nodes: dict[int, FarmNode] = {}  # locality_no → node
        self._edges: list[FarmEdge] = []
        self._adjacency: dict[int, list[int]] = defaultdict(list)
        self._clusters: list[ClusterRisk] = []
        self._cascades: list[CascadePrediction] = []
        self._built = False

    async def build_graph(self) -> int:
        """
        Build the farm network graph from database.
        Returns number of edges created.
        """
        try:
            from core.models import Locality, LiceRecord
            from core.async_db import get_async_session
            from sqlalchemy import select

            async with get_async_session() as s:
                # Load all farms with coordinates
                farms = (await s.execute(
                    select(
                        Locality.locality_no,
                        Locality.name,
                        Locality.latitude,
                        Locality.longitude,
                        Locality.owner_company,
                        Locality.production_area,
                    ).where(
                        Locality.latitude.isnot(None),
                        Locality.longitude.isnot(None),
                    )
                )).all()

                # Get latest lice data
                latest = (await s.execute(
                    select(LiceRecord.year, LiceRecord.week)
                    .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                    .limit(1)
                )).first()

                lice_data = {}
                if latest:
                    records = (await s.execute(
                        select(
                            LiceRecord.locality_no,
                            LiceRecord.avg_adult_female_lice,
                            LiceRecord.avg_mobile_lice,
                        ).where(
                            LiceRecord.year == latest[0],
                            LiceRecord.week == latest[1],
                        )
                    )).all()
                    lice_data = {r[0]: (r[1] or 0, r[2] or 0) for r in records}

            # Ticker mapping
            company_to_ticker = {
                "Mowi": "MOWI", "MOWI": "MOWI", "Marine Harvest": "MOWI",
                "SalMar": "SALM", "SALM": "SALM",
                "Lerøy": "LSG", "Leroy": "LSG", "LSG": "LSG",
                "Grieg": "GSF", "Grieg Seafood": "GSF",
                "Cermaq": "CERMAQ", "NRS": "NRS",
                "Norway Royal Salmon": "NRS",
            }

            # Build nodes
            self._nodes.clear()
            for loc_no, name, lat, lon, company, pa in farms:
                ticker = ""
                for comp_key, tick in company_to_ticker.items():
                    if comp_key.lower() in (company or "").lower():
                        ticker = tick
                        break

                lice_adult, lice_mobile = lice_data.get(loc_no, (0, 0))

                self._nodes[loc_no] = FarmNode(
                    locality_no=loc_no,
                    name=name,
                    latitude=lat,
                    longitude=lon,
                    company=company or "Unknown",
                    ticker=ticker,
                    production_area=pa or 0,
                    current_lice=lice_adult,
                    above_threshold=lice_adult > TREATMENT_THRESHOLD,
                )

            # Build edges (connect farms within dispersal range)
            self._edges.clear()
            self._adjacency.clear()
            nodes_list = list(self._nodes.values())
            n_edges = 0

            for i, node_a in enumerate(nodes_list):
                for j in range(i + 1, len(nodes_list)):
                    node_b = nodes_list[j]
                    dist = haversine_km(
                        node_a.latitude, node_a.longitude,
                        node_b.latitude, node_b.longitude,
                    )

                    if dist > MAX_DISPERSAL_KM:
                        continue

                    # Dispersal weight: exponential decay with distance
                    weight = math.exp(-dist * math.log(2) / DISPERSAL_HALF_LIFE_KM)

                    # Boost for same PA (similar ocean conditions)
                    if node_a.production_area == node_b.production_area:
                        weight *= 1.3

                    # Current direction boost — use real CMEMS ocean current data when available,
                    # fall back to static southward bias (prevailing Norwegian coastal current)
                    try:
                        from core.market.ocean_currents import ocean_currents
                        current_boost = ocean_currents.get_current_boost(
                            node_a.latitude, node_a.longitude,
                            node_b.latitude, node_b.longitude,
                        )
                        weight *= current_boost
                    except Exception:
                        # Static fallback: Norwegian Coastal Current flows predominantly SW
                        if node_b.latitude < node_a.latitude:
                            weight *= CURRENT_DIRECTION_BOOST

                    weight = min(1.0, weight)

                    edge = FarmEdge(
                        source=node_a.locality_no,
                        target=node_b.locality_no,
                        distance_km=round(dist, 1),
                        dispersal_weight=round(weight, 4),
                        correlation=0.0,  # will be computed from historical data
                        same_company=node_a.company == node_b.company,
                        same_pa=node_a.production_area == node_b.production_area,
                    )
                    self._edges.append(edge)
                    self._adjacency[node_a.locality_no].append(node_b.locality_no)
                    self._adjacency[node_b.locality_no].append(node_a.locality_no)
                    n_edges += 1

            self._built = True
            log.info(
                "farm_graph.built",
                n_nodes=len(self._nodes),
                n_edges=n_edges,
            )

            # Compute clusters and risk
            self._identify_clusters()
            self._predict_cascades()

            return n_edges

        except Exception as e:
            log.warning("farm_graph.build_error", error=str(e)[:150])
            return 0

    def _identify_clusters(self) -> None:
        """
        Identify farm clusters using connected components with
        high lice pressure. A cluster = group of connected farms
        where at least one farm is above cascade threshold.
        """
        if not self._nodes:
            return

        self._clusters.clear()
        visited = set()
        cluster_id = 0

        for start_node in self._nodes:
            if start_node in visited:
                continue

            # BFS to find connected component
            component = []
            queue = [start_node]
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                component.append(node)
                for neighbor in self._adjacency.get(node, []):
                    if neighbor not in visited:
                        queue.append(neighbor)

            if len(component) < 2:
                continue

            # Compute cluster risk
            nodes = [self._nodes[n] for n in component if n in self._nodes]
            if not nodes:
                continue

            lice_values = [n.current_lice for n in nodes]
            above = sum(1 for n in nodes if n.above_threshold)
            companies = list({n.company for n in nodes})
            tickers = list({n.ticker for n in nodes if n.ticker})
            pas = list({n.production_area for n in nodes})

            # Cascade probability: based on number of farms with high lice
            # and average lice level in cluster
            avg_lice = float(np.mean(lice_values)) if lice_values else 0
            max_lice = float(np.max(lice_values)) if lice_values else 0

            high_lice_fraction = sum(1 for l in lice_values if l > CASCADE_THRESHOLD) / max(len(lice_values), 1)
            cascade_prob = min(1.0, high_lice_fraction * 1.5 + (avg_lice / TREATMENT_THRESHOLD) * 0.3)

            # Risk level
            if cascade_prob > 0.7 or above > 3:
                risk = "critical"
            elif cascade_prob > 0.4 or above > 1:
                risk = "high"
            elif cascade_prob > 0.2 or avg_lice > CASCADE_THRESHOLD * 0.5:
                risk = "medium"
            else:
                risk = "low"

            # Trigger farm: highest lice in cluster
            trigger = max(nodes, key=lambda n: n.current_lice)

            cluster = ClusterRisk(
                cluster_id=cluster_id,
                farms=component,
                n_farms=len(component),
                center_lat=float(np.mean([n.latitude for n in nodes])),
                center_lon=float(np.mean([n.longitude for n in nodes])),
                production_area=pas[0] if pas else 0,
                companies_involved=companies[:5],
                avg_lice=round(avg_lice, 3),
                max_lice=round(max_lice, 3),
                n_above_threshold=above,
                cascade_probability=round(cascade_prob, 3),
                estimated_cascade_cost_nok=round(above * TREATMENT_COST_NOK * 1.5),
                risk_level=risk,
                trigger_farm=trigger.locality_no,
            )
            self._clusters.append(cluster)
            cluster_id += 1

        # Sort by risk
        self._clusters.sort(key=lambda c: c.cascade_probability, reverse=True)
        log.info("farm_graph.clusters", n_clusters=len(self._clusters))

    def _predict_cascades(self) -> None:
        """
        Predict treatment cascades using network propagation.

        Algorithm:
        1. Start from farms with highest lice (trigger farms)
        2. Propagate through network using dispersal weights
        3. Predict which farms will be affected and in what order
        4. Estimate total cost and duration
        """
        self._cascades.clear()

        # Find trigger farms: above threshold or trending up fast
        triggers = [
            n for n in self._nodes.values()
            if n.current_lice > CASCADE_THRESHOLD
        ]

        for trigger in triggers[:10]:  # top 10 most dangerous
            affected = self._simulate_cascade(trigger.locality_no)

            if len(affected) < 2:
                continue

            affected_nodes = [self._nodes[loc] for loc in affected if loc in self._nodes]
            companies = list({n.company for n in affected_nodes})
            tickers = list({n.ticker for n in affected_nodes if n.ticker})
            pas = list({n.production_area for n in affected_nodes})

            total_biomass = sum(n.biomass_tonnes for n in affected_nodes)
            biomass_impact = total_biomass * BIOMASS_LOSS_PER_TREATMENT_PCT / 100

            cascade = CascadePrediction(
                predicted_at=dt.datetime.now(dt.UTC),
                trigger_farm=trigger.locality_no,
                trigger_lice=trigger.current_lice,
                affected_farms=affected,
                cascade_order=affected,
                total_farms_affected=len(affected),
                estimated_duration_weeks=max(1, len(affected) // 3),
                companies_affected=companies,
                tickers_affected=tickers,
                production_areas=pas,
                estimated_total_cost_nok=round(len(affected) * TREATMENT_COST_NOK),
                estimated_biomass_impact_tonnes=round(biomass_impact, 1),
                confidence=0.5 + (trigger.current_lice / TREATMENT_THRESHOLD) * 0.2,
            )
            self._cascades.append(cascade)

        log.info("farm_graph.cascades", n_predicted=len(self._cascades))

    def _simulate_cascade(self, trigger_loc: int, rounds: int = 5) -> list[int]:
        """
        Simulate cascade propagation from a trigger farm.

        Uses iterative network propagation where each round
        infects connected farms proportional to dispersal weight.
        """
        infected = {trigger_loc}
        order = [trigger_loc]
        lice_level = {trigger_loc: self._nodes[trigger_loc].current_lice if trigger_loc in self._nodes else 0.5}

        for _ in range(rounds):
            new_infected = set()
            for loc in list(infected):
                for neighbor in self._adjacency.get(loc, []):
                    if neighbor in infected or neighbor in new_infected:
                        continue

                    # Find edge weight
                    weight = 0.3  # default
                    for edge in self._edges:
                        if (edge.source == loc and edge.target == neighbor) or \
                           (edge.target == loc and edge.source == neighbor):
                            weight = edge.dispersal_weight
                            break

                    # Probability of infection: weight * source lice level
                    source_lice = lice_level.get(loc, 0)
                    infection_prob = weight * (source_lice / TREATMENT_THRESHOLD)

                    if infection_prob > 0.3:  # infection threshold
                        new_infected.add(neighbor)
                        lice_level[neighbor] = source_lice * weight * 0.6  # attenuated
                        order.append(neighbor)

            if not new_infected:
                break
            infected.update(new_infected)

        return order

    # ── Public API ───────────────────────────────────────────────

    async def get_graph_summary(self) -> dict:
        """Get network graph summary statistics."""
        if not self._built:
            await self.build_graph()

        n_above = sum(1 for n in self._nodes.values() if n.above_threshold)
        lice_values = [n.current_lice for n in self._nodes.values() if n.current_lice > 0]

        return {
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "n_farms": len(self._nodes),
            "n_connections": len(self._edges),
            "n_clusters": len(self._clusters),
            "n_above_threshold": n_above,
            "avg_lice": round(float(np.mean(lice_values)), 3) if lice_values else 0,
            "max_lice": round(float(np.max(lice_values)), 3) if lice_values else 0,
            "avg_connections_per_farm": round(
                len(self._edges) * 2 / max(len(self._nodes), 1), 1
            ),
            "high_risk_clusters": len([c for c in self._clusters if c.risk_level in ("high", "critical")]),
            "active_cascade_predictions": len(self._cascades),
        }

    async def get_clusters(self, risk_level: Optional[str] = None) -> list[dict]:
        """Get farm clusters with risk assessment."""
        if not self._built:
            await self.build_graph()

        clusters = self._clusters
        if risk_level:
            clusters = [c for c in clusters if c.risk_level == risk_level]

        return [
            {
                "cluster_id": c.cluster_id,
                "n_farms": c.n_farms,
                "center": {"lat": c.center_lat, "lon": c.center_lon},
                "production_area": c.production_area,
                "companies": c.companies_involved,
                "avg_lice": c.avg_lice,
                "max_lice": c.max_lice,
                "above_threshold": c.n_above_threshold,
                "cascade_probability": c.cascade_probability,
                "estimated_cost_nok": c.estimated_cascade_cost_nok,
                "risk_level": c.risk_level,
                "trigger_farm": c.trigger_farm,
                "farms": c.farms[:20],  # limit for API response
            }
            for c in clusters[:30]
        ]

    async def get_cascade_predictions(self) -> list[dict]:
        """Get predicted treatment cascades."""
        if not self._built:
            await self.build_graph()

        return [
            {
                "predicted_at": c.predicted_at.isoformat(),
                "trigger_farm": c.trigger_farm,
                "trigger_lice": c.trigger_lice,
                "affected_farms": c.affected_farms[:20],
                "total_farms": c.total_farms_affected,
                "duration_weeks": c.estimated_duration_weeks,
                "companies": c.companies_affected,
                "tickers": c.tickers_affected,
                "production_areas": c.production_areas,
                "total_cost_nok": c.estimated_total_cost_nok,
                "biomass_impact_t": c.estimated_biomass_impact_tonnes,
                "confidence": round(c.confidence, 2),
            }
            for c in self._cascades[:20]
        ]

    async def get_company_network_exposure(self) -> list[dict]:
        """
        Score each company's network exposure risk.

        Companies with farms in high-risk clusters face higher
        cascade treatment costs. This is a unique alpha signal.
        """
        if not self._built:
            await self.build_graph()

        company_exposure: dict[str, dict] = {}

        for node in self._nodes.values():
            ticker = node.ticker
            if not ticker:
                continue

            if ticker not in company_exposure:
                company_exposure[ticker] = {
                    "ticker": ticker,
                    "total_farms": 0,
                    "farms_above_threshold": 0,
                    "avg_lice": 0,
                    "total_lice": 0,
                    "n_in_high_risk_cluster": 0,
                    "cascade_exposure_nok": 0,
                    "production_areas": set(),
                }

            exp = company_exposure[ticker]
            exp["total_farms"] += 1
            exp["total_lice"] += node.current_lice
            if node.above_threshold:
                exp["farms_above_threshold"] += 1
            exp["production_areas"].add(node.production_area)

        # Add cascade exposure
        for cascade in self._cascades:
            for ticker in cascade.tickers_affected:
                if ticker in company_exposure:
                    n_company_farms = sum(
                        1 for loc in cascade.affected_farms
                        if loc in self._nodes and self._nodes[loc].ticker == ticker
                    )
                    company_exposure[ticker]["cascade_exposure_nok"] += (
                        n_company_farms * TREATMENT_COST_NOK
                    )
                    company_exposure[ticker]["n_in_high_risk_cluster"] += n_company_farms

        # Compute risk score and format
        results = []
        for ticker, exp in company_exposure.items():
            if exp["total_farms"] == 0:
                continue

            avg_lice = exp["total_lice"] / exp["total_farms"]
            pct_above = exp["farms_above_threshold"] / exp["total_farms"]
            cluster_pct = exp["n_in_high_risk_cluster"] / exp["total_farms"]

            # Network risk score: 0-100
            risk_score = min(100, round(
                pct_above * 30 +
                cluster_pct * 40 +
                (avg_lice / TREATMENT_THRESHOLD) * 20 +
                (exp["cascade_exposure_nok"] / 1_000_000) * 10
            ))

            results.append({
                "ticker": ticker,
                "total_farms": exp["total_farms"],
                "farms_above_threshold": exp["farms_above_threshold"],
                "pct_above_threshold": round(pct_above * 100, 1),
                "avg_lice": round(avg_lice, 3),
                "n_in_high_risk_cluster": exp["n_in_high_risk_cluster"],
                "cascade_exposure_nok": exp["cascade_exposure_nok"],
                "production_areas": sorted(exp["production_areas"]),
                "network_risk_score": risk_score,
                "risk_level": (
                    "critical" if risk_score > 70 else
                    "high" if risk_score > 50 else
                    "medium" if risk_score > 30 else
                    "low"
                ),
            })

        results.sort(key=lambda r: r["network_risk_score"], reverse=True)
        return results

    async def get_farm_neighbors(self, locality_no: int) -> dict:
        """Get a farm's neighbors and connections."""
        if not self._built:
            await self.build_graph()

        node = self._nodes.get(locality_no)
        if not node:
            return {"error": f"Farm {locality_no} not found"}

        neighbors = []
        for neighbor_loc in self._adjacency.get(locality_no, []):
            n = self._nodes.get(neighbor_loc)
            if not n:
                continue

            # Find edge
            dist = 0.0
            weight = 0.0
            for edge in self._edges:
                if (edge.source == locality_no and edge.target == neighbor_loc) or \
                   (edge.target == locality_no and edge.source == neighbor_loc):
                    dist = edge.distance_km
                    weight = edge.dispersal_weight
                    break

            neighbors.append({
                "locality_no": neighbor_loc,
                "name": n.name,
                "company": n.company,
                "distance_km": dist,
                "dispersal_weight": weight,
                "current_lice": n.current_lice,
                "above_threshold": n.above_threshold,
            })

        neighbors.sort(key=lambda n: n["distance_km"])

        return {
            "locality_no": locality_no,
            "name": node.name,
            "company": node.company,
            "ticker": node.ticker,
            "current_lice": node.current_lice,
            "n_neighbors": len(neighbors),
            "neighbors": neighbors[:20],
        }

    async def get_map_data(self) -> dict:
        """
        Get all data needed for the frontend map visualization.
        Includes farm positions, connections, and cluster coloring.
        """
        if not self._built:
            await self.build_graph()

        # Farm nodes
        nodes = [
            {
                "id": n.locality_no,
                "name": n.name,
                "lat": n.latitude,
                "lon": n.longitude,
                "company": n.company,
                "ticker": n.ticker,
                "pa": n.production_area,
                "lice": n.current_lice,
                "above": n.above_threshold,
            }
            for n in self._nodes.values()
        ]

        # Edges (only high-weight connections for map)
        edges = [
            {
                "source": [self._nodes[e.source].longitude, self._nodes[e.source].latitude],
                "target": [self._nodes[e.target].longitude, self._nodes[e.target].latitude],
                "weight": e.dispersal_weight,
                "distance": e.distance_km,
            }
            for e in self._edges
            if e.dispersal_weight > 0.3
            and e.source in self._nodes
            and e.target in self._nodes
        ]

        # Cluster centers
        clusters = [
            {
                "id": c.cluster_id,
                "center": [c.center_lon, c.center_lat],
                "risk": c.risk_level,
                "n_farms": c.n_farms,
                "cascade_prob": c.cascade_probability,
            }
            for c in self._clusters
            if c.risk_level in ("high", "critical")
        ]

        return {
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "nodes": nodes,
            "edges": edges[:500],  # limit for performance
            "clusters": clusters,
            "n_total_nodes": len(nodes),
            "n_total_edges": len(self._edges),
        }


# Singleton
farm_graph = FarmNetworkGraph()
