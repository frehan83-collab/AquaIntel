"""
core/market/causal_engine.py
OpenClaw - Norwegian Salmon Aquaculture Trading Platform

Causal Inference Module: Discovers the true causal lag between sea lice outbreaks
and Norwegian salmon export price movements using:
  1. Granger Causality (statsmodels)
  2. Transfer Entropy (pure numpy/scipy fallback)
  3. PCMCI via Tigramite (optional enhancement)

Data sources:
  - BarentsWatch lice counts: avg adult female lice per fish, per locality, weekly (2019-2025)
  - SSB salmon export prices: NOK/kg, table 03024, weekly

Academic basis:
  Abolofia et al. (2017) and Asche et al. (2009, 2015) establish that Norwegian salmon
  prices are sensitive to supply shocks caused by disease events. The empirical lag from
  a significant lice spike to measurable price impact on SSB export data is typically
  6-10 weeks, reflecting: ~2 weeks for outbreak confirmation/reporting, ~2-3 weeks for
  harvest schedule adjustment, and ~2-4 weeks for export contract repricing. The
  relationship is asymmetric: sharp lice spikes produce stronger/faster price signals
  than lice declines, consistent with loss-aversion pricing in commodity spot markets.

Usage:
    from core.market.causal_engine import causal_engine

    causal_engine.load_data(lice_series, price_series, pct_above_series)
    summary = causal_engine.get_causal_summary()
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats
from scipy.special import digamma

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependencies – gracefully degrade if not installed
# ---------------------------------------------------------------------------
try:
    from statsmodels.tsa.stattools import grangercausalitytests, adfuller
    from statsmodels.tsa.vector_ar.var_model import VAR  # noqa: F401
    _HAS_STATSMODELS = True
except ImportError:  # pragma: no cover
    _HAS_STATSMODELS = False
    logger.warning("statsmodels not installed – Granger causality will be skipped.")

try:
    import tigramite.data_processing as pp
    from tigramite.pcmci import PCMCI
    from tigramite.independence_tests.parcorr import ParCorr
    _HAS_TIGRAMITE = True
except ImportError:
    _HAS_TIGRAMITE = False
    logger.info("tigramite not installed – PCMCI will be skipped; Transfer Entropy used instead.")


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class GrangerResult:
    lag: int
    f_stat: float
    p_value: float
    significant: bool  # p < 0.05


@dataclass
class TransferEntropyResult:
    lag: int
    te_value: float       # bits
    z_score: float        # vs. shuffled null
    p_value: float


@dataclass
class CausalSummary:
    dominant_lag_weeks: int
    method_used: str                              # "granger", "transfer_entropy", "pcmci"
    confidence: str                               # "high", "medium", "low"
    granger_results: List[Dict]
    te_results: List[Dict]
    pcmci_available: bool
    pcmci_results: Optional[Dict]
    interpretation: str
    asymmetry_detected: bool                      # lice-up vs lice-down price response
    recommended_lag_range: Tuple[int, int]        # (min_lag, max_lag) for production model


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _check_stationarity(series: np.ndarray, name: str = "series") -> bool:
    """Run ADF test; warn if non-stationary (unit root present)."""
    if not _HAS_STATSMODELS:
        return True  # assume stationary if we can't test
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = adfuller(series[~np.isnan(series)], autolag="AIC")
    p = result[1]
    if p > 0.05:
        logger.warning(
            "Series '%s' appears non-stationary (ADF p=%.4f). "
            "Consider first-differencing before causal analysis.", name, p
        )
        return False
    return True


def _first_difference(series: np.ndarray) -> np.ndarray:
    """Return first differences, preserving NaN positions."""
    diff = np.full_like(series, np.nan)
    diff[1:] = np.diff(series)
    return diff


def _knn_entropy(x: np.ndarray, k: int = 5) -> float:
    """
    KSG k-nearest-neighbour entropy estimator (Kraskov et al. 2004).
    Returns entropy in nats.
    """
    n = len(x)
    x = x.reshape(-1, 1)
    # pairwise Chebyshev distances
    dists = np.abs(x - x.T)  # shape (n, n)
    np.fill_diagonal(dists, np.inf)
    kth_dists = np.partition(dists, k, axis=1)[:, k]
    # KSG estimator
    return -digamma(k) + digamma(n) + np.mean(np.log(2.0 * kth_dists + 1e-15))


def _joint_knn_entropy(x: np.ndarray, y: np.ndarray, k: int = 5) -> float:
    """Joint KSG entropy H(X,Y)."""
    n = len(x)
    xy = np.column_stack([x, y])
    # Chebyshev distance in joint space
    diffs = np.abs(xy[:, None, :] - xy[None, :, :])  # (n,n,2)
    dists = diffs.max(axis=2)                          # Chebyshev
    np.fill_diagonal(dists, np.inf)
    kth_dists = np.partition(dists, k, axis=1)[:, k]
    return -digamma(k) + digamma(n) + 2.0 * np.mean(np.log(2.0 * kth_dists + 1e-15))


def _transfer_entropy_ksg(
    source: np.ndarray,
    target: np.ndarray,
    lag: int,
    history: int = 1,
    k: int = 5,
) -> float:
    """
    TE(source → target, lag τ) using the KSG estimator.

    TE = H(target_future | target_past) - H(target_future | target_past, source_past_lagged)
       = H(target_future, target_past) - H(target_past)
         - H(target_future, target_past, source_lagged) + H(target_past, source_lagged)

    All series must be pre-aligned and free of NaN.
    """
    n = len(target)
    start = max(lag + history, history)
    if start >= n - 1:
        return 0.0

    tf = target[start:]                           # target future
    tp = target[start - history: n - 1][:len(tf)]  # target past (1 step back)
    sl = source[start - lag: n - lag][:len(tf)]    # source lagged

    if len(tf) < k + 2:
        return 0.0

    h_tf_tp   = _joint_knn_entropy(tf, tp, k)
    h_tp      = _knn_entropy(tp, k)
    h_tf_tp_sl = _joint_knn_entropy(np.column_stack([tf, tp]).T[0],
                                     np.column_stack([tf, tp]).T[1], k)
    # Proper 3-var joint entropy via Chebyshev
    xyz = np.column_stack([tf, tp, sl])
    n3 = len(xyz)
    diffs3 = np.abs(xyz[:, None, :] - xyz[None, :, :]).max(axis=2)
    np.fill_diagonal(diffs3, np.inf)
    kth3 = np.partition(diffs3, k, axis=1)[:, k]
    h_tf_tp_sl = -digamma(k) + digamma(n3) + 3.0 * np.mean(np.log(2.0 * kth3 + 1e-15))

    xy = np.column_stack([tp, sl])
    n2 = len(xy)
    diffs2 = np.abs(xy[:, None, :] - xy[None, :, :]).max(axis=2)
    np.fill_diagonal(diffs2, np.inf)
    kth2 = np.partition(diffs2, k, axis=1)[:, k]
    h_tp_sl = -digamma(k) + digamma(n2) + 2.0 * np.mean(np.log(2.0 * kth2 + 1e-15))

    te = h_tf_tp - h_tp - h_tf_tp_sl + h_tp_sl
    return float(te)


def _shuffle_null_te(
    source: np.ndarray,
    target: np.ndarray,
    lag: int,
    n_shuffles: int = 100,
    k: int = 5,
    seed: int = 42,
) -> Tuple[float, float]:
    """
    Compute mean and std of TE under time-shuffled null hypothesis.
    Returns (null_mean, null_std).
    """
    rng = np.random.default_rng(seed)
    null_tes = []
    for _ in range(n_shuffles):
        shuffled = source.copy()
        rng.shuffle(shuffled)
        null_tes.append(_transfer_entropy_ksg(shuffled, target, lag, k=k))
    arr = np.array(null_tes)
    return float(arr.mean()), float(arr.std() + 1e-12)


# ---------------------------------------------------------------------------
# Main CausalEngine class
# ---------------------------------------------------------------------------

class CausalEngine:
    """
    Discovers causal lag structure between Norwegian sea lice outbreaks
    and salmon export price movements.

    Supported causal methods (in order of preference):
      1. PCMCI (Tigramite) – full multivariate causal graph discovery
      2. Granger Causality  – bivariate, parametric
      3. Transfer Entropy   – bivariate, non-parametric (pure numpy/scipy)
    """

    def __init__(self) -> None:
        self._lice: Optional[np.ndarray] = None          # weekly_lice_national_avg (X1)
        self._price: Optional[np.ndarray] = None         # salmon_price_nok          (X2)
        self._pct_above: Optional[np.ndarray] = None     # pct_farms_above_threshold (X3)
        self._n_weeks: int = 0

        self._granger_cache: Dict[int, GrangerResult] = {}
        self._te_cache: Dict[int, TransferEntropyResult] = {}
        self._pcmci_cache: Optional[Dict] = None
        self._dominant_lag: Optional[int] = None
        self._method_used: str = "none"

    # ------------------------------------------------------------------
    # Data ingestion
    # ------------------------------------------------------------------

    def load_data(
        self,
        lice_series: np.ndarray,
        price_series: np.ndarray,
        pct_above_series: Optional[np.ndarray] = None,
        auto_difference: bool = True,
    ) -> "CausalEngine":
        """
        Load and validate the three time series.

        Parameters
        ----------
        lice_series       : 1-D array of weekly avg adult female lice per fish
        price_series      : 1-D array of weekly salmon export price (NOK/kg)
        pct_above_series  : 1-D array of % farms above 0.5 lice threshold (optional)
        auto_difference   : if True, first-difference any non-stationary series

        Returns
        -------
        self (fluent API)
        """
        lice  = np.asarray(lice_series,  dtype=float)
        price = np.asarray(price_series, dtype=float)

        if lice.shape != price.shape:
            raise ValueError(
                f"lice_series length {len(lice)} != price_series length {len(price)}"
            )

        if pct_above_series is not None:
            pct = np.asarray(pct_above_series, dtype=float)
            if pct.shape != lice.shape:
                raise ValueError("pct_above_series must have same length as lice_series")
            self._pct_above = pct
        else:
            self._pct_above = None

        # Stationarity checks with optional auto-differencing
        lice_stat  = _check_stationarity(lice,  "lice_series")
        price_stat = _check_stationarity(price, "price_series")

        if auto_difference:
            if not lice_stat:
                logger.info("Auto-differencing lice_series for stationarity.")
                lice = _first_difference(lice)
            if not price_stat:
                logger.info("Auto-differencing price_series for stationarity.")
                price = _first_difference(price)

        self._lice   = lice
        self._price  = price
        self._n_weeks = len(lice)

        # Clear caches when new data is loaded
        self._granger_cache.clear()
        self._te_cache.clear()
        self._pcmci_cache = None
        self._dominant_lag = None
        self._method_used  = "none"

        logger.info(
            "CausalEngine: loaded %d weeks of data "
            "(lice mean=%.3f, price mean=%.2f NOK/kg)",
            self._n_weeks,
            float(np.nanmean(lice)),
            float(np.nanmean(price)),
        )
        return self

    def _require_data(self) -> None:
        if self._lice is None or self._price is None:
            raise RuntimeError("No data loaded. Call load_data() first.")

    # ------------------------------------------------------------------
    # Method 1: Granger Causality
    # ------------------------------------------------------------------

    def run_granger(self, max_lag: int = 16) -> Dict[int, Dict]:
        """
        Test Granger causality: lice → price for lags 1..max_lag.

        Uses statsmodels grangercausalitytests with the F-test.

        Returns
        -------
        dict of {lag: {"f_stat": float, "p_value": float, "significant": bool}}
        """
        self._require_data()

        if not _HAS_STATSMODELS:
            logger.warning("statsmodels unavailable – Granger test skipped.")
            return {}

        # Drop NaN rows (first-differencing inserts one)
        mask = ~(np.isnan(self._lice) | np.isnan(self._price))
        lice_clean  = self._lice[mask]
        price_clean = self._price[mask]

        data = np.column_stack([price_clean, lice_clean])  # [dependent, causal]

        results = {}
        logger.info("Running Granger causality tests for lags 1..%d …", max_lag)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                raw = grangercausalitytests(data, maxlag=max_lag, verbose=False)
            except Exception as exc:
                logger.error("grangercausalitytests failed: %s", exc)
                return {}

        for lag in range(1, max_lag + 1):
            f_stat  = raw[lag][0]["ssr_ftest"][0]
            p_value = raw[lag][0]["ssr_ftest"][1]
            gr = GrangerResult(
                lag=lag,
                f_stat=float(f_stat),
                p_value=float(p_value),
                significant=bool(p_value < 0.05),
            )
            self._granger_cache[lag] = gr
            results[lag] = {
                "f_stat": gr.f_stat,
                "p_value": gr.p_value,
                "significant": gr.significant,
            }

        logger.info(
            "Granger: significant lags = %s",
            [l for l, r in results.items() if r["significant"]],
        )
        return results

    # ------------------------------------------------------------------
    # Method 2: Transfer Entropy (pure numpy/scipy)
    # ------------------------------------------------------------------

    def compute_transfer_entropy(
        self,
        lag: int,
        n_shuffles: int = 200,
        knn_k: int = 5,
    ) -> Dict:
        """
        Compute TE(lice → price, lag=τ) using the KSG k-NN estimator.

        Parameters
        ----------
        lag        : causal lag τ in weeks
        n_shuffles : number of random shuffles for null distribution
        knn_k      : number of nearest neighbours for KSG estimator

        Returns
        -------
        dict with keys: lag, te_value, z_score, p_value
        """
        self._require_data()

        if lag < 1:
            raise ValueError("lag must be >= 1")

        mask = ~(np.isnan(self._lice) | np.isnan(self._price))
        source = self._lice[mask]
        target = self._price[mask]

        # Standardise for numerical stability
        source = (source - source.mean()) / (source.std() + 1e-12)
        target = (target - target.mean()) / (target.std() + 1e-12)

        te_val = _transfer_entropy_ksg(source, target, lag, k=knn_k)
        null_mean, null_std = _shuffle_null_te(source, target, lag, n_shuffles, knn_k)

        z_score = (te_val - null_mean) / null_std
        # One-tailed p-value from normal approximation
        p_value = float(stats.norm.sf(z_score))

        ter = TransferEntropyResult(
            lag=lag,
            te_value=float(te_val),
            z_score=float(z_score),
            p_value=p_value,
        )
        self._te_cache[lag] = ter

        return {
            "lag": lag,
            "te_value": ter.te_value,
            "z_score": ter.z_score,
            "p_value": ter.p_value,
            "significant": p_value < 0.05,
        }

    def run_transfer_entropy(
        self,
        max_lag: int = 16,
        n_shuffles: int = 200,
        knn_k: int = 5,
    ) -> Dict[int, Dict]:
        """
        Run TE for all lags 1..max_lag.

        Returns
        -------
        dict of {lag: {te_value, z_score, p_value, significant}}
        """
        self._require_data()
        logger.info("Running Transfer Entropy for lags 1..%d …", max_lag)
        results = {}
        for lag in range(1, max_lag + 1):
            results[lag] = self.compute_transfer_entropy(lag, n_shuffles, knn_k)
        sig = [l for l, r in results.items() if r["significant"]]
        logger.info("Transfer Entropy: significant lags = %s", sig)
        return results

    # ------------------------------------------------------------------
    # Method 3: PCMCI (Tigramite – optional)
    # ------------------------------------------------------------------

    def run_pcmci(
        self,
        max_lag: int = 16,
        alpha_level: float = 0.05,
    ) -> Optional[Dict]:
        """
        Run PCMCI on the multivariate system [lice, price, pct_above].

        Requires tigramite to be installed. Returns None if unavailable.

        Returns
        -------
        dict with keys: links_coefficients, p_matrix, val_matrix, var_names
        """
        self._require_data()

        if not _HAS_TIGRAMITE:
            logger.info("Tigramite not available – PCMCI skipped.")
            return None

        vars_list = [self._lice, self._price]
        var_names = ["lice_avg", "price_nok"]

        if self._pct_above is not None:
            vars_list.append(self._pct_above)
            var_names.append("pct_above_threshold")

        # Stack into (T, N) matrix, drop leading NaN row from differencing
        mat = np.column_stack(vars_list)
        mask = ~np.isnan(mat).any(axis=1)
        mat = mat[mask]

        dataframe = pp.DataFrame(
            mat,
            var_names=var_names,
            datatime={0: np.arange(mat.shape[0])},
        )

        parcorr = ParCorr(significance="analytic")
        pcmci   = PCMCI(dataframe=dataframe, cond_ind_test=parcorr, verbosity=0)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            results = pcmci.run_pcmci(tau_max=max_lag, pc_alpha=alpha_level)

        self._pcmci_cache = {
            "p_matrix": results["p_matrix"].tolist(),
            "val_matrix": results["val_matrix"].tolist(),
            "var_names": var_names,
            "tau_max": max_lag,
            "alpha_level": alpha_level,
            # Significant links as human-readable list
            "significant_links": _extract_pcmci_links(
                results["p_matrix"], results["val_matrix"],
                var_names, alpha_level
            ),
        }
        logger.info("PCMCI complete. Significant links: %s",
                    self._pcmci_cache["significant_links"])
        return self._pcmci_cache

    # ------------------------------------------------------------------
    # Dominant lag discovery
    # ------------------------------------------------------------------

    def find_dominant_lag(self, max_lag: int = 16) -> int:
        """
        Return the dominant causal lag (weeks) from lice to price.

        Priority:
          1. Granger (highest F-statistic among significant lags)
          2. Transfer Entropy (highest TE z-score among significant lags)
          3. Literature default: 8 weeks

        Returns
        -------
        int – dominant causal lag in weeks
        """
        self._require_data()

        # --- Try Granger ---
        if _HAS_STATSMODELS:
            granger = self.run_granger(max_lag) if not self._granger_cache else {
                l: {"f_stat": r.f_stat, "p_value": r.p_value, "significant": r.significant}
                for l, r in self._granger_cache.items()
            }
            sig_granger = {l: r for l, r in granger.items() if r["significant"]}
            if sig_granger:
                dominant = max(sig_granger, key=lambda l: sig_granger[l]["f_stat"])
                self._dominant_lag  = dominant
                self._method_used   = "granger"
                logger.info(
                    "Dominant lag (Granger): %d weeks (F=%.2f)",
                    dominant, sig_granger[dominant]["f_stat"]
                )
                return dominant

        # --- Fallback: Transfer Entropy ---
        te_results = self.run_transfer_entropy(max_lag) if not self._te_cache else {
            l: {"te_value": r.te_value, "z_score": r.z_score,
                "p_value": r.p_value, "significant": r.p_value < 0.05}
            for l, r in self._te_cache.items()
        }
        sig_te = {l: r for l, r in te_results.items() if r["significant"]}
        if sig_te:
            dominant = max(sig_te, key=lambda l: sig_te[l]["z_score"])
            self._dominant_lag = dominant
            self._method_used  = "transfer_entropy"
            logger.info(
                "Dominant lag (TE): %d weeks (z=%.2f)",
                dominant, sig_te[dominant]["z_score"]
            )
            return dominant

        # --- Literature default ---
        logger.warning(
            "No statistically significant causal lag detected. "
            "Falling back to literature default: 8 weeks."
        )
        self._dominant_lag = 8
        self._method_used  = "literature_default"
        return 8

    # ------------------------------------------------------------------
    # Asymmetry analysis
    # ------------------------------------------------------------------

    def _detect_asymmetry(self) -> bool:
        """
        Test whether price reacts more strongly to lice increases than decreases.
        Uses a sign-stratified cross-correlation heuristic.
        Returns True if upward lice shocks show stronger/faster price response.
        """
        if self._lice is None or self._price is None:
            return False

        mask = ~(np.isnan(self._lice) | np.isnan(self._price))
        lice  = self._lice[mask]
        price = self._price[mask]

        lag = self._dominant_lag or 8

        # Split lice changes into positive (outbreak) and negative (recovery)
        delta_lice = np.diff(lice)
        up_idx   = np.where(delta_lice > 0)[0]
        down_idx = np.where(delta_lice < 0)[0]

        def _lagged_price_response(idx: np.ndarray) -> float:
            responses = []
            for i in idx:
                future = i + lag
                if future < len(price):
                    responses.append(price[future] - price[i])
            return float(np.mean(responses)) if responses else 0.0

        up_response   = _lagged_price_response(up_idx)
        down_response = _lagged_price_response(down_idx)

        # Asymmetric if magnitude of up-shock response > down-shock response
        asymmetric = abs(up_response) > abs(down_response) * 1.2  # 20% threshold
        logger.info(
            "Asymmetry check: up_response=%.4f, down_response=%.4f → asymmetric=%s",
            up_response, down_response, asymmetric
        )
        return asymmetric

    # ------------------------------------------------------------------
    # Summary API
    # ------------------------------------------------------------------

    def get_causal_summary(self, max_lag: int = 16) -> Dict:
        """
        Run all available causal analyses and return a structured summary
        suitable for API response serialisation.

        Returns
        -------
        dict matching CausalSummary fields plus metadata
        """
        self._require_data()

        # Ensure Granger is run
        granger_results = []
        if _HAS_STATSMODELS and not self._granger_cache:
            self.run_granger(max_lag)
        for lag, r in sorted(self._granger_cache.items()):
            granger_results.append({
                "lag": lag, "f_stat": r.f_stat,
                "p_value": r.p_value, "significant": r.significant,
            })

        # Ensure TE is run
        if not self._te_cache:
            self.run_transfer_entropy(max_lag)
        te_results = []
        for lag, r in sorted(self._te_cache.items()):
            te_results.append({
                "lag": lag, "te_value": r.te_value,
                "z_score": r.z_score, "p_value": r.p_value,
                "significant": r.p_value < 0.05,
            })

        # PCMCI (if available and not yet cached)
        if _HAS_TIGRAMITE and self._pcmci_cache is None:
            self.run_pcmci(max_lag)

        # Find dominant lag
        dominant = self.find_dominant_lag(max_lag)

        # Confidence rating
        n_sig_granger = sum(1 for r in granger_results if r["significant"])
        n_sig_te      = sum(1 for r in te_results if r["significant"])
        if n_sig_granger >= 2 and n_sig_te >= 2:
            confidence = "high"
        elif n_sig_granger >= 1 or n_sig_te >= 1:
            confidence = "medium"
        else:
            confidence = "low"

        # Recommended lag range: ±2 weeks around dominant, bounded by [1, max_lag]
        rec_min = max(1, dominant - 2)
        rec_max = min(max_lag, dominant + 2)

        asymmetric = self._detect_asymmetry()

        interpretation = _build_interpretation(
            dominant, self._method_used, confidence, asymmetric,
            n_sig_granger, n_sig_te
        )

        summary = CausalSummary(
            dominant_lag_weeks=dominant,
            method_used=self._method_used,
            confidence=confidence,
            granger_results=granger_results,
            te_results=te_results,
            pcmci_available=_HAS_TIGRAMITE,
            pcmci_results=self._pcmci_cache,
            interpretation=interpretation,
            asymmetry_detected=asymmetric,
            recommended_lag_range=(rec_min, rec_max),
        )

        return {
            "dominant_lag_weeks": summary.dominant_lag_weeks,
            "method_used": summary.method_used,
            "confidence": summary.confidence,
            "recommended_lag_range": list(summary.recommended_lag_range),
            "asymmetry_detected": summary.asymmetry_detected,
            "interpretation": summary.interpretation,
            "pcmci_available": summary.pcmci_available,
            "pcmci_results": summary.pcmci_results,
            "granger_results": summary.granger_results,
            "te_results": summary.te_results,
            "meta": {
                "n_obs": self._n_weeks,
                "tigramite_installed": _HAS_TIGRAMITE,
                "statsmodels_installed": _HAS_STATSMODELS,
            },
        }


# ---------------------------------------------------------------------------
# Module-level helpers (not part of the class)
# ---------------------------------------------------------------------------

def _extract_pcmci_links(
    p_matrix: np.ndarray,
    val_matrix: np.ndarray,
    var_names: List[str],
    alpha: float,
) -> List[Dict]:
    """Extract significant PCMCI causal links as human-readable list."""
    links = []
    n_vars = p_matrix.shape[0]
    tau_max = p_matrix.shape[2] - 1
    for j in range(n_vars):
        for i in range(n_vars):
            for tau in range(tau_max + 1):
                if i == j and tau == 0:
                    continue
                if p_matrix[i, j, tau] < alpha:
                    links.append({
                        "cause": var_names[i],
                        "effect": var_names[j],
                        "lag_weeks": tau,
                        "coefficient": float(val_matrix[i, j, tau]),
                        "p_value": float(p_matrix[i, j, tau]),
                    })
    return links


def _build_interpretation(
    dominant_lag: int,
    method: str,
    confidence: str,
    asymmetric: bool,
    n_sig_granger: int,
    n_sig_te: int,
) -> str:
    """Generate a human-readable interpretation of the causal results."""
    lines = [
        f"Dominant causal lag (lice → price): {dominant_lag} weeks "
        f"[method: {method}, confidence: {confidence}].",
    ]
    if confidence == "high":
        lines.append(
            f"Both Granger ({n_sig_granger} significant lags) and Transfer Entropy "
            f"({n_sig_te} significant lags) agree on a strong causal signal."
        )
    elif confidence == "medium":
        lines.append(
            "Moderate causal evidence detected. Results should be interpreted "
            "alongside domain knowledge."
        )
    else:
        lines.append(
            "No statistically significant causal lag found in current dataset. "
            "Using literature default (8 weeks). More data or pre-processing may help."
        )

    if asymmetric:
        lines.append(
            "Asymmetric response detected: price reacts more strongly to lice INCREASES "
            "than to decreases, consistent with loss-aversion pricing behaviour in "
            "Norwegian salmon spot markets (Asche et al., 2009)."
        )
    else:
        lines.append(
            "No significant asymmetry detected between outbreak and recovery price responses."
        )

    lines.append(
        "Academic context: Asche et al. (2009, 2015) and Abolofia et al. (2017) "
        "estimate a 6-10 week transmission window from sea lice outbreak confirmation "
        "to measurable SSB export price impact, driven by harvest schedule adjustment "
        "and contract repricing cycles."
    )
    return " ".join(lines)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

causal_engine = CausalEngine()
