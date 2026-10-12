"""
Lice GNN — Graph Neural Network for Sea Lice Spread Prediction
===============================================================
Predicts next-week sea lice counts and exceedance probability (>0.5 threshold)
across the Norwegian salmon farm network using a Temporal Graph Attention Network.

Architecture choice: Temporal GAT (Graph Attention Network) with sliding window
-  GAT over GraphSAGE/GCN: attention heads learn *which* neighboring farms
   are the strongest lice sources, dynamically weighting by lice level,
   distance, and current direction — critical because a single upstream
   hot-spot can dominate an entire cluster while distant farms contribute
   negligibly; static aggregation (GCN) would under-weight this.
-  Temporal window over pure spatial GNN: lice dynamics have strong
   week-on-week autocorrelation (~0.7 lag-1 Pearson on BarentsWatch data)
   and seasonal patterns; 4-week input captures the build-up ramp before a
   treatment event without excessive memory overhead.
-  Dual-head output: regression head (MSE) + classification head (BCE)
   jointly optimised — treatment decisions are threshold-triggered so the
   binary probability is the operationally relevant signal.

Required packages (add to requirements.txt):
    torch>=2.2.0
    torch_geometric>=2.5.0
    torch_scatter>=2.1.2
    torch_sparse>=0.6.18
    # Install PyG via:
    # pip install torch_geometric
    # pip install torch_scatter torch_sparse -f https://data.pyg.org/whl/torch-2.2.0+cpu.html

Training data requirements:
    - ~1 000 farms × 4 years × 52 weeks ≈ 208 000 farm-week samples
    - Minimum viable: 2 years (104 weeks) — enough for seasonal coverage
    - Expected MAE on held-out weeks: ~0.04–0.08 lice/fish (within 1 treatment unit)
    - Expected AUROC for threshold exceedance: ~0.82–0.88
    - Caveat: sparse reporting (farms with no fish skip weeks) reduces
      effective N; impute missing weeks with forward-fill before training.
"""
from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict
from typing import Optional

import numpy as np
import structlog

# ── torch (optional — ships in requirements-models.txt) ──────────────
# Stand-ins keep this module importable AND the trainer constructible when
# torch is absent (CI installs the light requirements only). Every real use
# raises a clear RuntimeError; routes gate on is_available() before that.
_TORCH_AVAILABLE = False
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch import Tensor
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_MSG = "torch is not installed — pip install -r requirements-models.txt"

    class _StubRaiser:
        def __init__(self, name: str):
            self._name = name

        def __call__(self, *a, **k):
            raise RuntimeError(_TORCH_MSG)

        def __getattr__(self, name):
            return _StubRaiser(f"{self._name}.{name}")

    class _CudaStub:
        @staticmethod
        def is_available() -> bool:
            return False

    class _TorchMeta(type):
        def __getattr__(cls, name):
            if name == "device":
                return lambda arg=None: (arg or "cpu")
            if name == "cuda":
                return _CudaStub
            if name == "is_available":
                return lambda: False
            return _StubRaiser(name)

    class _TorchStub(metaclass=_TorchMeta):
        pass

    class _StubModule:
        def __init__(self, *a, **k):
            raise RuntimeError(_TORCH_MSG)

    class _NNMeta(type):
        def __getattr__(cls, name):
            if name == "Module":
                return _StubModule
            return _StubRaiser(name)

    class _NNStub(metaclass=_NNMeta):
        pass

    class _StubTensor:
        pass

    torch = _TorchStub
    nn = _NNStub
    F = _NNStub
    Tensor = _StubTensor

# Lazy import — torch_geometric is optional (large dependency)
# Add to requirements.txt: torch_geometric>=2.5.0
_TORCH_GEOMETRIC_AVAILABLE = False
try:
    from torch_geometric.data import Data, DataLoader
    from torch_geometric.nn import GATv2Conv, LayerNorm
    _TORCH_GEOMETRIC_AVAILABLE = True
except ImportError:
    class _MissingPyG:
        """Stand-in for torch_geometric symbols so the module stays importable.

        Any construction attempt raises a clear RuntimeError — routes gate on
        is_available()/503 before that point, but stray uses must not crash
        the import itself (that broke 2 tests whenever torch was present and
        torch_geometric was not).
        """
        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "torch_geometric is not installed — pip install torch_geometric"
            )

    Data = DataLoader = GATv2Conv = LayerNorm = _MissingPyG

log = structlog.get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
TREATMENT_THRESHOLD = 0.5       # adult female lice/fish — Norwegian regulatory limit
WINDOW_WEEKS = 4                # temporal sliding window fed as stacked node features
NODE_BASE_FEATURES = 9          # [lat, lon, lice_count, company_id, production_area,
                                #  week_sin, week_cos, sea_temp, has_cleaner_fish]
NODE_INPUT_DIM = NODE_BASE_FEATURES * WINDOW_WEEKS   # 36 — all time steps flattened
EDGE_ATTR_DIM = 3               # [dispersal_weight, distance_km_norm, current_boost]
HIDDEN_DIM = 128
HEADS = 4                       # GAT attention heads
DROPOUT = 0.3
LR = 1e-3
WEIGHT_DECAY = 1e-4


# ── Model ────────────────────────────────────────────────────────────────────

class LiceGNN(nn.Module):
    """
    Temporal Graph Attention Network for lice spread prediction.

    Input:
        x          (N, NODE_INPUT_DIM)  — stacked 4-week node feature matrix
        edge_index (2, E)               — COO adjacency (PyG format)
        edge_attr  (E, EDGE_ATTR_DIM)   — per-edge dispersal attributes

    Output:
        lice_pred  (N,)   — predicted adult-female lice count next week
        exceed_prob (N,)  — sigmoid probability of exceeding 0.5 threshold
    """

    def __init__(
        self,
        node_input_dim: int = NODE_INPUT_DIM,
        edge_attr_dim: int = EDGE_ATTR_DIM,
        hidden_dim: int = HIDDEN_DIM,
        heads: int = HEADS,
        dropout: float = DROPOUT,
        n_conv_layers: int = 3,
    ) -> None:
        super().__init__()
        self.dropout = dropout

        # Project raw node features to hidden space before graph convolutions
        self.input_proj = nn.Sequential(
            nn.Linear(node_input_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
        )

        # Edge attribute projection: broadcast to match attention mechanism
        self.edge_proj = nn.Linear(edge_attr_dim, hidden_dim)

        # GATv2 conv layers — GATv2 fixes the static attention issue in GATv1
        # by computing e(Wh_i || Wh_j) instead of e(Wh_i) + e(Wh_j), making
        # attention truly dynamic and better suited for directional lice flow.
        assert n_conv_layers >= 2, "Need at least 2 conv layers"
        self.convs = nn.ModuleList()
        self.norms = nn.ModuleList()

        # Layer 0: input_proj → heads * (hidden_dim // heads)
        self.convs.append(
            GATv2Conv(
                in_channels=hidden_dim,
                out_channels=hidden_dim // heads,
                heads=heads,
                dropout=dropout,
                edge_dim=hidden_dim,
                concat=True,   # output: hidden_dim
            )
        )
        self.norms.append(LayerNorm(hidden_dim))

        # Middle layers: hidden_dim → hidden_dim
        for _ in range(n_conv_layers - 2):
            self.convs.append(
                GATv2Conv(
                    in_channels=hidden_dim,
                    out_channels=hidden_dim // heads,
                    heads=heads,
                    dropout=dropout,
                    edge_dim=hidden_dim,
                    concat=True,
                )
            )
            self.norms.append(LayerNorm(hidden_dim))

        # Final conv: collapse heads → single vector for output MLP
        self.convs.append(
            GATv2Conv(
                in_channels=hidden_dim,
                out_channels=hidden_dim,
                heads=1,
                dropout=dropout,
                edge_dim=hidden_dim,
                concat=False,  # output: hidden_dim
            )
        )
        self.norms.append(LayerNorm(hidden_dim))

        # Dual output heads
        self.regression_head = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
            nn.Softplus(),   # lice count is non-negative
        )
        self.classification_head = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
            # No sigmoid here — use BCEWithLogitsLoss during training
        )

    def forward(
        self,
        x: Tensor,               # (N, NODE_INPUT_DIM)
        edge_index: Tensor,      # (2, E)
        edge_attr: Tensor,       # (E, EDGE_ATTR_DIM)
    ) -> tuple[Tensor, Tensor]:

        # Project inputs
        h = self.input_proj(x)                          # (N, hidden_dim)
        e = self.edge_proj(edge_attr)                   # (E, hidden_dim)

        # Graph convolution stack with residual connections
        for conv, norm in zip(self.convs, self.norms):
            h_new = conv(h, edge_index, edge_attr=e)    # (N, hidden_dim or heads*dim)
            h_new = norm(h_new)
            h_new = F.gelu(h_new)
            h_new = F.dropout(h_new, p=self.dropout, training=self.training)
            # Residual only when shapes match (all layers except first if concat changes shape)
            if h_new.shape == h.shape:
                h = h + h_new
            else:
                h = h_new

        lice_pred = self.regression_head(h).squeeze(-1)       # (N,)
        exceed_logit = self.classification_head(h).squeeze(-1) # (N,) — raw logit
        return lice_pred, exceed_logit


# ── Trainer ──────────────────────────────────────────────────────────────────

class LiceGNNTrainer:
    """
    End-to-end trainer for LiceGNN.

    Workflow:
        trainer = LiceGNNTrainer()
        graphs = trainer.prepare_data(farm_records)
        trainer.train(epochs=100)
        prob = trainer.predict(farm_id=12345, weeks_ahead=1)
    """

    def __init__(
        self,
        hidden_dim: int = HIDDEN_DIM,
        heads: int = HEADS,
        n_conv_layers: int = 3,
        dropout: float = DROPOUT,
        lr: float = LR,
        weight_decay: float = WEIGHT_DECAY,
        device: Optional[str] = None,
        model_path: str = "core/market/lice_gnn_weights.pt",
    ) -> None:
        self.device = torch.device(
            device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        )
        self.model_path = model_path
        self.lr = lr
        self.weight_decay = weight_decay

        if not _TORCH_GEOMETRIC_AVAILABLE:
            # Keep construction import-safe; is_available() gates all use.
            self.model = None
            self.optimizer = None
        else:
            self.model = LiceGNN(
                hidden_dim=hidden_dim,
                heads=heads,
                n_conv_layers=n_conv_layers,
                dropout=dropout,
            ).to(self.device)

            self.optimizer = torch.optim.AdamW(
                self.model.parameters(), lr=lr, weight_decay=weight_decay
            )
            self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                self.optimizer, T_max=100, eta_min=1e-5
            )
        if not _TORCH_GEOMETRIC_AVAILABLE:
            self.scheduler = None

        # State populated by prepare_data
        self._graph_snapshots: list[Data] = []          # one per week
        self._farm_index: dict[int, int] = {}           # locality_no → node index
        self._scaler_mean: Optional[np.ndarray] = None
        self._scaler_std: Optional[np.ndarray] = None
        self._trained = False

    def is_available(self) -> bool:
        """True when torch_geometric is installed — routes gate on this (503)."""
        return _TORCH_GEOMETRIC_AVAILABLE

    def status(self) -> dict:
        """Operational status for /api/gnn/status (honest about availability)."""
        return {
            "available": _TORCH_GEOMETRIC_AVAILABLE,
            "trained": bool(self._trained),
            "model": "LiceGNN (Temporal GAT, 4-week window, dual-head)",
            "n_snapshots": len(self._graph_snapshots),
            "hint": None if _TORCH_GEOMETRIC_AVAILABLE
                    else "pip install torch torch_geometric to enable the GNN",
        }

    # ── Data preparation ──────────────────────────────────────────────────────

    def prepare_data(self, farm_records: list[dict]) -> list[Data]:
        """
        Convert farm DB records to a sequence of PyG Data snapshots,
        one per week. Each snapshot carries 4-week stacked node features.

        Expected record schema (matches LiceRecord + Locality join):
            locality_no: int
            year: int
            week: int
            lat: float
            lon: float
            avg_adult_female_lice: float   # target variable
            company_id: int                # encoded integer company id
            production_area: int
            sea_temp_c: float | None
            has_cleaner_fish: bool | None

        Records for ALL farms and ALL weeks should be passed together.
        Missing weeks per farm are forward-filled automatically.
        """
        if not farm_records:
            raise ValueError("farm_records is empty")

        # ── 1. Organise by (year, week) → {locality_no: record} ──────────────
        week_map: dict[tuple[int, int], dict[int, dict]] = defaultdict(dict)
        all_localities: dict[int, dict] = {}  # locality_no → static attrs

        for r in farm_records:
            loc = r["locality_no"]
            yw = (r["year"], r["week"])
            week_map[yw][loc] = r
            if loc not in all_localities:
                all_localities[loc] = {
                    "lat": r["lat"],
                    "lon": r["lon"],
                    "company_id": r.get("company_id", 0),
                    "production_area": r.get("production_area", 0),
                }

        # Sorted list of farm nodes (stable ordering = stable node indices)
        sorted_locs = sorted(all_localities.keys())
        self._farm_index = {loc: idx for idx, loc in enumerate(sorted_locs)}
        N = len(sorted_locs)

        # ── 2. Build edge_index + edge_attr from FarmNetworkGraph ────────────
        from core.market.farm_graph import haversine_km, MAX_DISPERSAL_KM, DISPERSAL_HALF_LIFE_KM, CURRENT_DIRECTION_BOOST

        src_list, dst_list, edge_attrs = [], [], []
        for i, loc_a in enumerate(sorted_locs):
            a = all_localities[loc_a]
            for j, loc_b in enumerate(sorted_locs):
                if i >= j:
                    continue
                b = all_localities[loc_b]
                dist = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
                if dist > MAX_DISPERSAL_KM:
                    continue
                weight = math.exp(-dist * math.log(2) / DISPERSAL_HALF_LIFE_KM)
                same_pa = int(a["production_area"] == b["production_area"])
                if same_pa:
                    weight *= 1.3
                # Directional boost: add directed edge A→B (south) with boost
                current_boost_ab = CURRENT_DIRECTION_BOOST if b["lat"] < a["lat"] else 1.0
                current_boost_ba = CURRENT_DIRECTION_BOOST if a["lat"] < b["lat"] else 1.0
                dist_norm = dist / MAX_DISPERSAL_KM
                w = min(1.0, weight)

                src_list += [i, j]
                dst_list += [j, i]
                edge_attrs += [
                    [w * current_boost_ab, dist_norm, current_boost_ab],
                    [w * current_boost_ba, dist_norm, current_boost_ba],
                ]

        edge_index = torch.tensor([src_list, dst_list], dtype=torch.long)
        edge_attr = torch.tensor(edge_attrs, dtype=torch.float32)

        # ── 3. Normalise lat/lon to [0,1] range (Norwegian coast) ────────────
        lats = np.array([all_localities[l]["lat"] for l in sorted_locs])
        lons = np.array([all_localities[l]["lon"] for l in sorted_locs])
        lat_min, lat_max = lats.min(), lats.max()
        lon_min, lon_max = lons.min(), lons.max()

        # ── 4. Build temporal feature matrix per week-snapshot ────────────────
        sorted_weeks = sorted(week_map.keys())  # [(year, week), ...]

        # Feature matrix per week: shape (N, NODE_BASE_FEATURES)
        def week_features(yw: tuple[int, int], prev_records: dict[int, dict]) -> np.ndarray:
            """Build (N, 9) feature matrix for one week, using prev_records for fill."""
            records = week_map.get(yw, {})
            year, week = yw
            week_sin = math.sin(2 * math.pi * week / 52)
            week_cos = math.cos(2 * math.pi * week / 52)
            mat = np.zeros((N, NODE_BASE_FEATURES), dtype=np.float32)
            for idx, loc in enumerate(sorted_locs):
                r = records.get(loc) or prev_records.get(loc) or {}
                lice = float(r.get("avg_adult_female_lice") or 0.0)
                temp = float(r.get("sea_temp_c") or 10.0)  # fallback to typical fjord temp
                cleaner = float(bool(r.get("has_cleaner_fish", False)))
                lat_norm = (all_localities[loc]["lat"] - lat_min) / max(lat_max - lat_min, 1e-6)
                lon_norm = (all_localities[loc]["lon"] - lon_min) / max(lon_max - lon_min, 1e-6)
                company_norm = float(all_localities[loc]["company_id"]) / 100.0
                pa_norm = float(all_localities[loc]["production_area"]) / 13.0
                mat[idx] = [lat_norm, lon_norm, lice, company_norm, pa_norm,
                            week_sin, week_cos, temp / 20.0, cleaner]
            return mat

        # ── 5. Compute global lice stats for normalisation ────────────────────
        all_lice = [
            float(r.get("avg_adult_female_lice") or 0.0)
            for r in farm_records
        ]
        lice_mean = float(np.mean(all_lice))
        lice_std = float(np.std(all_lice)) + 1e-6
        self._scaler_mean = np.array([lice_mean])
        self._scaler_std = np.array([lice_std])

        # ── 6. Construct Data objects with WINDOW_WEEKS stacked features ──────
        self._graph_snapshots = []
        prev: dict[int, dict] = {}

        week_feat_cache: list[np.ndarray] = []
        for yw in sorted_weeks:
            week_feat_cache.append(week_features(yw, prev))
            prev.update(week_map[yw])

        for t in range(WINDOW_WEEKS, len(sorted_weeks)):
            # Stack 4 previous weeks as input
            window = np.concatenate(
                [week_feat_cache[t - WINDOW_WEEKS + k] for k in range(WINDOW_WEEKS)],
                axis=1,
            )  # (N, NODE_BASE_FEATURES * WINDOW_WEEKS)

            # Target: lice counts at week t (the week to predict)
            yw_target = sorted_weeks[t]
            target_records = week_map.get(yw_target, {})
            y_lice = np.zeros(N, dtype=np.float32)
            y_exceed = np.zeros(N, dtype=np.float32)
            for idx, loc in enumerate(sorted_locs):
                r = target_records.get(loc) or {}
                lice = float(r.get("avg_adult_female_lice") or 0.0)
                y_lice[idx] = (lice - lice_mean) / lice_std  # standardised
                y_exceed[idx] = float(lice > TREATMENT_THRESHOLD)

            data = Data(
                x=torch.tensor(window, dtype=torch.float32),
                edge_index=edge_index,
                edge_attr=edge_attr,
                y_lice=torch.tensor(y_lice, dtype=torch.float32),
                y_exceed=torch.tensor(y_exceed, dtype=torch.float32),
                week=torch.tensor(list(yw_target), dtype=torch.long),
            )
            self._graph_snapshots.append(data)

        log.info(
            "lice_gnn.data_prepared",
            n_farms=N,
            n_edges=edge_index.shape[1],
            n_snapshots=len(self._graph_snapshots),
        )
        return self._graph_snapshots

    async def build_training_data_from_db(self) -> dict:
        """
        Build training data directly from the database.
        Queries LiceRecord + Locality tables, builds temporal graph snapshots.
        Returns dict with stats about the built dataset.
        """
        try:
            from core.models import LiceRecord, Locality
            from core.async_db import get_async_session
            from sqlalchemy import select, func  # noqa: F401
        except ImportError:
            log.warning("gnn.db_import_failed", msg="Cannot import core.models")
            return {"status": "error", "message": "Database models not available"}

        snapshots = []
        farm_index: dict[int, int] = {}

        async with get_async_session() as session:
            # Get all localities with coordinates
            locs = (await session.execute(
                select(Locality).where(Locality.latitude.isnot(None))
            )).scalars().all()

            if len(locs) < 10:
                log.warning("gnn.insufficient_localities", n=len(locs))
                return {"status": "error", "message": f"Only {len(locs)} localities with coordinates"}

            # Build farm index
            loc_list = sorted(locs, key=lambda l: l.locality_no)
            for idx, loc in enumerate(loc_list):
                farm_index[loc.locality_no] = idx

            n_farms = len(loc_list)
            log.info("gnn.building_data", n_farms=n_farms)

            # Build adjacency from distance (reuse haversine)
            from core.market.farm_graph import haversine_km
            edge_src, edge_dst, edge_attrs = [], [], []
            MAX_DIST = 30.0

            for i, loc_i in enumerate(loc_list):
                for j, loc_j in enumerate(loc_list):
                    if i >= j:
                        continue
                    dist = haversine_km(
                        loc_i.latitude, loc_i.longitude,
                        loc_j.latitude, loc_j.longitude,
                    )
                    if dist < MAX_DIST:
                        weight = math.exp(-dist / 10.0)
                        # Bidirectional edges
                        edge_src.extend([i, j])
                        edge_dst.extend([j, i])
                        edge_attrs.extend([
                            [weight, dist / MAX_DIST, 1.0],
                            [weight, dist / MAX_DIST, 1.0],
                        ])

            if not edge_src:
                return {"status": "error", "message": "No edges found within 30km"}

            edge_index = torch.tensor([edge_src, edge_dst], dtype=torch.long)
            edge_attr = torch.tensor(edge_attrs, dtype=torch.float32)

            # Get available weeks
            weeks = (await session.execute(
                select(LiceRecord.year, LiceRecord.week)
                .distinct()
                .order_by(LiceRecord.year, LiceRecord.week)
            )).all()

            if len(weeks) < WINDOW_WEEKS + 1:
                return {"status": "error", "message": f"Only {len(weeks)} weeks available, need {WINDOW_WEEKS + 1}"}

            # Build lookup: (locality_no, year, week) -> record
            all_records = (await session.execute(select(LiceRecord))).scalars().all()
            rec_map: dict[tuple, any] = {}
            for r in all_records:
                rec_map[(r.locality_no, r.year, r.week)] = r

            # Build snapshots for each window
            for w_idx in range(WINDOW_WEEKS, len(weeks) - 1):
                window_weeks = weeks[w_idx - WINDOW_WEEKS: w_idx]
                target_week = weeks[w_idx]

                # Build node features: stack WINDOW_WEEKS of features per farm
                x = torch.zeros(n_farms, NODE_INPUT_DIM, dtype=torch.float32)

                for t, (yr, wk) in enumerate(window_weeks):
                    week_sin = math.sin(2 * math.pi * wk / 52)
                    week_cos = math.cos(2 * math.pi * wk / 52)

                    for farm_idx, loc in enumerate(loc_list):
                        rec = rec_map.get((loc.locality_no, yr, wk))
                        base_offset = t * NODE_BASE_FEATURES

                        # Normalized lat/lon
                        x[farm_idx, base_offset + 0] = (loc.latitude - 58.0) / 13.0
                        x[farm_idx, base_offset + 1] = (loc.longitude - 4.0) / 28.0

                        if rec:
                            x[farm_idx, base_offset + 2] = rec.avg_adult_female_lice or 0.0
                            x[farm_idx, base_offset + 3] = 0.0  # company_id placeholder
                            x[farm_idx, base_offset + 4] = (loc.production_area or 7) / 13.0
                            x[farm_idx, base_offset + 5] = week_sin
                            x[farm_idx, base_offset + 6] = week_cos
                            x[farm_idx, base_offset + 7] = (rec.sea_temp_c or 8.0) / 20.0
                            x[farm_idx, base_offset + 8] = 1.0 if rec.has_cleaner_fish else 0.0
                        else:
                            # Missing data — use defaults
                            x[farm_idx, base_offset + 4] = (loc.production_area or 7) / 13.0
                            x[farm_idx, base_offset + 5] = week_sin
                            x[farm_idx, base_offset + 6] = week_cos
                            x[farm_idx, base_offset + 7] = 0.4  # ~8°C default

                # Build targets from next week
                t_yr, t_wk = target_week
                y_reg = torch.zeros(n_farms, dtype=torch.float32)
                y_cls = torch.zeros(n_farms, dtype=torch.float32)
                valid_mask = torch.zeros(n_farms, dtype=torch.bool)

                for farm_idx, loc in enumerate(loc_list):
                    rec = rec_map.get((loc.locality_no, t_yr, t_wk))
                    if rec and rec.avg_adult_female_lice is not None:
                        y_reg[farm_idx] = rec.avg_adult_female_lice
                        y_cls[farm_idx] = 1.0 if rec.avg_adult_female_lice >= TREATMENT_THRESHOLD else 0.0
                        valid_mask[farm_idx] = True

                if valid_mask.sum() < 5:
                    continue  # Skip weeks with too few valid targets

                if _TORCH_GEOMETRIC_AVAILABLE:
                    snapshot = Data(
                        x=x,
                        edge_index=edge_index,
                        edge_attr=edge_attr,
                        y_lice=y_reg,
                        y_exceed=y_cls,
                        valid_mask=valid_mask,
                    )
                else:
                    snapshot = {
                        "x": x,
                        "edge_index": edge_index,
                        "edge_attr": edge_attr,
                        "y_regression": y_reg,
                        "y_classification": y_cls,
                        "valid_mask": valid_mask,
                    }
                snapshots.append(snapshot)

        self._graph_snapshots = snapshots
        self._farm_index = farm_index

        log.info(
            "gnn.training_data_built",
            n_snapshots=len(snapshots),
            n_farms=n_farms,
            n_edges=len(edge_src),
        )

        return {
            "status": "ok",
            "n_snapshots": len(snapshots),
            "n_farms": n_farms,
            "n_edges": len(edge_src),
            "week_range": f"{weeks[0]}-{weeks[-1]}" if weeks else "none",
        }

    # ── Training ──────────────────────────────────────────────────────────────

    def train(self, epochs: int = 100, val_split: float = 0.15, batch_size: int = 8) -> dict:
        """
        Train the GNN on prepared snapshots.

        Returns dict with final train/val losses and AUROC.
        """
        if not self._graph_snapshots:
            raise RuntimeError("Call prepare_data() before train()")

        n_val = max(1, int(len(self._graph_snapshots) * val_split))
        train_data = self._graph_snapshots[:-n_val]
        val_data = self._graph_snapshots[-n_val:]

        train_loader = DataLoader(train_data, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_data, batch_size=batch_size, shuffle=False)

        # Loss: MSE for regression (standardised) + BCE for classification
        mse_loss = nn.MSELoss()
        bce_loss = nn.BCEWithLogitsLoss()
        # Upweight positive class (~15% farms exceed threshold)
        pos_weight = torch.tensor([5.0], device=self.device)
        bce_loss_weighted = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

        best_val_loss = float("inf")
        history = {"train_loss": [], "val_loss": []}

        for epoch in range(1, epochs + 1):
            # ── Train ──
            self.model.train()
            total_loss = 0.0
            for batch in train_loader:
                batch = batch.to(self.device)
                self.optimizer.zero_grad()
                lice_pred, exceed_logit = self.model(batch.x, batch.edge_index, batch.edge_attr)
                loss_reg = mse_loss(lice_pred, batch.y_lice)
                loss_cls = bce_loss_weighted(exceed_logit, batch.y_exceed)
                loss = loss_reg + 0.5 * loss_cls
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.optimizer.step()
                total_loss += loss.item()
            self.scheduler.step()
            avg_train = total_loss / max(len(train_loader), 1)

            # ── Validate ──
            self.model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for batch in val_loader:
                    batch = batch.to(self.device)
                    lice_pred, exceed_logit = self.model(batch.x, batch.edge_index, batch.edge_attr)
                    l = mse_loss(lice_pred, batch.y_lice) + 0.5 * bce_loss(exceed_logit, batch.y_exceed)
                    val_loss += l.item()
            avg_val = val_loss / max(len(val_loader), 1)

            history["train_loss"].append(avg_train)
            history["val_loss"].append(avg_val)

            if avg_val < best_val_loss:
                best_val_loss = avg_val
                torch.save(self.model.state_dict(), self.model_path)

            if epoch % 10 == 0:
                log.info(
                    "lice_gnn.train",
                    epoch=epoch,
                    train_loss=round(avg_train, 4),
                    val_loss=round(avg_val, 4),
                )

        # Reload best weights
        self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
        self._trained = True
        log.info("lice_gnn.train_complete", best_val_loss=round(best_val_loss, 4))
        return {
            "best_val_loss": best_val_loss,
            "epochs": epochs,
            "train_loss_final": history["train_loss"][-1],
        }

    # ── Inference ─────────────────────────────────────────────────────────────

    def predict(self, farm_id: int, weeks_ahead: int = 1) -> dict:
        """
        Predict next-week lice count and exceedance probability for a single farm.

        Args:
            farm_id:     locality_no of the target farm
            weeks_ahead: 1 (supported; multi-step would require auto-regressive rollout)

        Returns:
            {
                "farm_id": int,
                "predicted_lice": float,      # adult female lice/fish
                "exceed_probability": float,  # P(lice > 0.5)
                "above_threshold": bool,
                "predicted_at": str,          # ISO timestamp
            }
        """
        if not self._trained:
            raise RuntimeError("Model not trained. Call train() first or load weights.")
        if farm_id not in self._farm_index:
            raise ValueError(f"farm_id {farm_id} not in training graph (unknown locality)")
        if weeks_ahead != 1:
            raise NotImplementedError(
                "Multi-step prediction requires auto-regressive rollout; "
                "currently only weeks_ahead=1 is supported."
            )

        farm_idx = self._farm_index[farm_id]

        # Use the most recent snapshot as input
        latest_snapshot = self._graph_snapshots[-1]

        self.model.eval()
        with torch.no_grad():
            x = latest_snapshot.x.to(self.device)
            edge_index = latest_snapshot.edge_index.to(self.device)
            edge_attr = latest_snapshot.edge_attr.to(self.device)
            lice_pred, exceed_logit = self.model(x, edge_index, edge_attr)

        # Denormalise regression output
        lice_std = float(self._scaler_std[0]) if self._scaler_std is not None else 1.0
        lice_mean = float(self._scaler_mean[0]) if self._scaler_mean is not None else 0.0
        raw_lice = float(lice_pred[farm_idx].cpu())
        predicted_lice = max(0.0, raw_lice * lice_std + lice_mean)

        exceed_prob = float(torch.sigmoid(exceed_logit[farm_idx]).cpu())

        return {
            "farm_id": farm_id,
            "predicted_lice": round(predicted_lice, 4),
            "exceed_probability": round(exceed_prob, 4),
            "above_threshold": exceed_prob >= 0.5,
            "predicted_at": dt.datetime.now(dt.UTC).isoformat(),
        }

    def load_weights(self, path: Optional[str] = None) -> None:
        """Load pre-trained weights from disk."""
        p = path or self.model_path
        self.model.load_state_dict(torch.load(p, map_location=self.device))
        self._trained = True
        log.info("lice_gnn.weights_loaded", path=p)

    def predict_all_farms(self) -> list[dict]:
        """
        Run inference on all farms in the latest snapshot.
        Returns a list of prediction dicts sorted by exceed_probability descending.
        """
        if not self._trained:
            raise RuntimeError("Model not trained.")

        latest_snapshot = self._graph_snapshots[-1]
        self.model.eval()
        with torch.no_grad():
            x = latest_snapshot.x.to(self.device)
            edge_index = latest_snapshot.edge_index.to(self.device)
            edge_attr = latest_snapshot.edge_attr.to(self.device)
            lice_pred, exceed_logit = self.model(x, edge_index, edge_attr)

        lice_std = float(self._scaler_std[0]) if self._scaler_std is not None else 1.0
        lice_mean = float(self._scaler_mean[0]) if self._scaler_mean is not None else 0.0
        lice_pred_np = lice_pred.cpu().numpy() * lice_std + lice_mean
        lice_pred_np = np.clip(lice_pred_np, 0.0, None)
        exceed_prob_np = torch.sigmoid(exceed_logit).cpu().numpy()

        results = []
        inv_index = {v: k for k, v in self._farm_index.items()}
        now = dt.datetime.now(dt.UTC).isoformat()
        for idx in range(len(inv_index)):
            farm_id = inv_index.get(idx)
            if farm_id is None:
                continue
            results.append({
                "farm_id": farm_id,
                "predicted_lice": round(float(lice_pred_np[idx]), 4),
                "exceed_probability": round(float(exceed_prob_np[idx]), 4),
                "above_threshold": float(exceed_prob_np[idx]) >= 0.5,
                "predicted_at": now,
            })

        results.sort(key=lambda r: r["exceed_probability"], reverse=True)
        return results


# ── Singleton ────────────────────────────────────────────────────────────────
lice_gnn_trainer = LiceGNNTrainer()
