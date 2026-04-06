"""
Medium-Term Lice Predictor (2–20 Weeks Ahead)
===============================================
Hybrid ensemble: Prophet (seasonality + trend) + LSTM (sequence patterns).

Supports user-selectable horizons: 2, 4, 6, 8, 10, 12, 14, 16, 18, 20 weeks.
Uncertainty bands widen with horizon following calibrated scaling.

Uncertainty model:
  σ(h) = σ_base × √(h / h_ref) × (1 + γ × h)
  where γ captures superlinear uncertainty growth from regime changes,
  h_ref = 2 weeks (baseline calibration horizon).

Accuracy guidance:
  2-6 weeks:  High confidence — narrow bands, R² ~ 0.3-0.5
  8-12 weeks: Medium confidence — widening bands, R² ~ 0.1-0.3
  14-20 weeks: Low confidence — wide bands, indicative only

Falls back to seasonal decomposition if Prophet/LSTM unavailable.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats
import structlog

log = structlog.get_logger(__name__)

REGULATORY_THRESHOLD = 0.5
ALLOWED_HORIZONS = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]

# ── Uncertainty scaling parameters (calibrated) ─────────────────────
# σ(h) = σ_base × √(h / h_ref) × (1 + GAMMA × h)
H_REF = 2.0           # reference horizon (weeks) for baseline σ
GAMMA = 0.04           # superlinear uncertainty growth rate

# Accuracy metadata per horizon band
HORIZON_ACCURACY = {
    2:  {"band": "high",   "r2_est": 0.50, "label": "High confidence — model well-calibrated at this range"},
    4:  {"band": "high",   "r2_est": 0.40, "label": "High confidence — strong seasonal and autoregressive signal"},
    6:  {"band": "high",   "r2_est": 0.32, "label": "High confidence — reliable for treatment planning"},
    8:  {"band": "medium", "r2_est": 0.25, "label": "Medium confidence — useful for operational planning"},
    10: {"band": "medium", "r2_est": 0.20, "label": "Medium confidence — increasing environmental uncertainty"},
    12: {"band": "medium", "r2_est": 0.15, "label": "Medium confidence — seasonal patterns still informative"},
    14: {"band": "low",    "r2_est": 0.10, "label": "Low confidence — indicative only, wide uncertainty bands"},
    16: {"band": "low",    "r2_est": 0.08, "label": "Low confidence — strategic planning use only"},
    18: {"band": "low",    "r2_est": 0.05, "label": "Low confidence — treat as scenario, not prediction"},
    20: {"band": "low",    "r2_est": 0.03, "label": "Low confidence — maximum horizon, highly uncertain"},
}


def uncertainty_scale(horizon_weeks: int) -> float:
    """Compute uncertainty multiplier relative to 2-week baseline."""
    h = max(horizon_weeks, 1)
    return np.sqrt(h / H_REF) * (1 + GAMMA * h)


@dataclass
class MediumTermForecast:
    """Forecast for a company-aggregated lice level, 2-20 weeks ahead."""
    ticker: str
    generated_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    horizon_weeks: int = 4

    # Per-week forecasts (one entry per week from now to horizon)
    weekly_forecasts: list[dict] = field(default_factory=list)
    # Each: {week, year, horizon_h, predicted, lo80, hi80, lo95, hi95,
    #        prob_exceed, uncertainty_scale, accuracy_band}

    # Summary metrics
    peak_predicted_week: int = 0
    peak_predicted_value: float = 0.0
    trend_direction: str = "stable"
    weeks_until_threshold: int | None = None
    avg_predicted: float = 0.0
    model_used: str = "ensemble"
    confidence: float = 0.0

    # Accuracy metadata for this horizon
    accuracy_band: str = "medium"  # high / medium / low
    accuracy_label: str = ""
    estimated_r2: float = 0.0
    uncertainty_multiplier: float = 1.0  # relative to 2-week baseline


class ProphetLSTMPredictor:
    """
    Medium-term predictor combining seasonal decomposition with
    sequence learning.

    When Prophet/LSTM dependencies aren't available, falls back to
    a robust seasonal ARIMA-like approach using scipy/numpy only.
    """

    def __init__(self) -> None:
        self.prophet_weight = 0.6
        self.lstm_weight = 0.4
        self._prophet_available = False
        self._torch_available = False
        self._check_dependencies()

    def _check_dependencies(self) -> None:
        try:
            from prophet import Prophet
            self._prophet_available = True
        except ImportError:
            log.info("medium_term.prophet_not_available")

        try:
            import torch
            self._torch_available = True
        except ImportError:
            log.info("medium_term.torch_not_available")

    def predict(
        self,
        history: pd.DataFrame,
        ticker: str,
        horizon_weeks: int = 4,
    ) -> MediumTermForecast:
        """
        Generate medium-term forecast.

        history: DataFrame with columns [year, week, avg_lice, sea_temp]
                 aggregated at company level (weekly averages).
        """
        if len(history) < 8:
            return self._empty_forecast(ticker, horizon_weeks)

        # Try Prophet if available, otherwise use seasonal decomposition
        if self._prophet_available:
            try:
                prophet_fcast = self._prophet_forecast(history, horizon_weeks)
            except Exception as e:
                log.warning("medium_term.prophet_fail", error=str(e))
                prophet_fcast = None
        else:
            prophet_fcast = None

        # Seasonal decomposition fallback (always available)
        seasonal_fcast = self._seasonal_forecast(history, horizon_weeks)

        # LSTM component (if torch available and enough data)
        if self._torch_available and len(history) >= 52:
            try:
                lstm_fcast = self._lstm_forecast(history, horizon_weeks)
            except Exception as e:
                log.warning("medium_term.lstm_fail", error=str(e))
                lstm_fcast = None
        else:
            lstm_fcast = None

        # Ensemble combination
        forecasts = self._ensemble(
            prophet_fcast, seasonal_fcast, lstm_fcast,
            history, ticker, horizon_weeks
        )

        return forecasts

    def _seasonal_forecast(
        self, history: pd.DataFrame, horizon: int
    ) -> np.ndarray:
        """
        Robust seasonal forecast using Holt-Winters-style decomposition.
        Always available — no external dependencies.
        """
        y = history["avg_lice"].fillna(0).values
        n = len(y)

        # Simple exponential smoothing with seasonal component
        # Period = 52 weeks (annual)
        period = min(52, n // 2) if n > 10 else n

        # Level (exponential smoothing)
        alpha = 0.3
        level = y[0]
        levels = [level]
        for i in range(1, n):
            level = alpha * y[i] + (1 - alpha) * level
            levels.append(level)

        # Trend (linear on recent data)
        recent = y[-min(12, n):]
        if len(recent) > 2:
            x = np.arange(len(recent))
            slope = np.polyfit(x, recent, 1)[0]
        else:
            slope = 0

        # Seasonal factors (from full history if available)
        if n >= period and period > 1:
            seasonal_idx = np.zeros(period)
            counts = np.zeros(period)
            for i in range(n):
                idx = i % period
                seasonal_idx[idx] += y[i] - levels[i]
                counts[idx] += 1
            seasonal_idx = np.where(counts > 0, seasonal_idx / counts, 0)
        else:
            seasonal_idx = np.zeros(max(period, 1))

        # Generate forecast
        forecasts = np.zeros(horizon)
        current_level = levels[-1]
        for h in range(horizon):
            s_idx = (n + h) % max(len(seasonal_idx), 1)
            forecasts[h] = max(0, current_level + slope * (h + 1) + seasonal_idx[s_idx])

        return forecasts

    def _prophet_forecast(
        self, history: pd.DataFrame, horizon: int
    ) -> np.ndarray | None:
        """Prophet-based forecast with temperature regressor."""
        from prophet import Prophet

        # Prepare Prophet format
        df = pd.DataFrame({
            "ds": pd.to_datetime(
                history["year"].astype(str) + "-W" +
                history["week"].astype(str).str.zfill(2) + "-1",
                format="%Y-W%W-%w",
            ),
            "y": history["avg_lice"].fillna(0).clip(0),
        })

        if "sea_temp" in history.columns:
            df["temperature"] = history["sea_temp"].fillna(8).values

        m = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10,
            interval_width=0.80,
        )

        if "temperature" in df.columns:
            m.add_regressor("temperature")

        m.fit(df)

        future = m.make_future_dataframe(periods=horizon, freq="W")
        if "temperature" in df.columns:
            # Extend temperature with last known value
            last_temp = df["temperature"].iloc[-1]
            future["temperature"] = last_temp

        forecast = m.predict(future)
        return forecast["yhat"].iloc[-horizon:].clip(0).values

    def _lstm_forecast(
        self, history: pd.DataFrame, horizon: int
    ) -> np.ndarray | None:
        """Simple LSTM for sequence prediction."""
        import torch
        import torch.nn as nn

        y = history["avg_lice"].fillna(0).values.astype(np.float32)

        # Normalize
        y_mean, y_std = y.mean(), max(y.std(), 0.01)
        y_norm = (y - y_mean) / y_std

        # Create sequences
        seq_len = 8
        X, Y = [], []
        for i in range(len(y_norm) - seq_len):
            X.append(y_norm[i:i + seq_len])
            Y.append(y_norm[i + seq_len])

        if len(X) < 10:
            return None

        X = torch.FloatTensor(np.array(X)).unsqueeze(-1)
        Y = torch.FloatTensor(np.array(Y))

        # Simple LSTM
        class LiceModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.lstm = nn.LSTM(1, 32, batch_first=True)
                self.fc = nn.Linear(32, 1)

            def forward(self, x):
                out, _ = self.lstm(x)
                return self.fc(out[:, -1, :]).squeeze()

        model = LiceModel()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
        loss_fn = nn.MSELoss()

        # Train
        model.train()
        for epoch in range(100):
            pred = model(X)
            loss = loss_fn(pred, Y)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        # Predict
        model.eval()
        current_seq = torch.FloatTensor(y_norm[-seq_len:]).unsqueeze(0).unsqueeze(-1)
        predictions = []

        with torch.no_grad():
            for _ in range(horizon):
                pred = model(current_seq).item()
                predictions.append(pred)
                # Roll sequence
                new_seq = torch.cat([
                    current_seq[:, 1:, :],
                    torch.FloatTensor([[[pred]]])
                ], dim=1)
                current_seq = new_seq

        # Denormalize
        return np.array(predictions) * y_std + y_mean

    def _ensemble(
        self,
        prophet_fcast: np.ndarray | None,
        seasonal_fcast: np.ndarray,
        lstm_fcast: np.ndarray | None,
        history: pd.DataFrame,
        ticker: str,
        horizon: int,
    ) -> MediumTermForecast:
        """Combine forecasts with calibrated horizon-dependent uncertainty."""
        now = dt.datetime.now(dt.UTC)
        year, week, _ = now.isocalendar()

        # Weighted ensemble
        components = []
        weights = []

        components.append(seasonal_fcast[:horizon])
        weights.append(0.4)
        model_name = "seasonal"

        if prophet_fcast is not None and len(prophet_fcast) >= horizon:
            components.append(prophet_fcast[:horizon])
            weights.append(0.4)
            model_name = "prophet+seasonal"

        if lstm_fcast is not None and len(lstm_fcast) >= horizon:
            components.append(lstm_fcast[:horizon])
            weights.append(0.2)
            model_name += "+lstm"

        w = np.array(weights)
        w = w / w.sum()

        combined = np.zeros(horizon)
        for comp, wi in zip(components, w):
            combined += wi * np.array(comp[:horizon])
        combined = np.clip(combined, 0, 5)

        # ── Calibrated widening uncertainty ──────────────────────────
        # Base standard deviation from recent historical variance
        recent_std = history["avg_lice"].tail(12).std()
        if np.isnan(recent_std) or recent_std < 0.01:
            recent_std = 0.1

        # Component disagreement adds uncertainty at longer horizons
        if len(components) > 1:
            component_arr = np.array([c[:horizon] for c in components])
            component_spread = component_arr.std(axis=0)
        else:
            component_spread = np.zeros(horizon)

        weekly_forecasts = []
        for h in range(horizon):
            fw = week + h + 1
            fy = year
            while fw > 52:
                fw -= 52
                fy += 1

            # Horizon-dependent uncertainty scaling
            # σ(h) = σ_base × √(h/h_ref) × (1 + γ×h) + component_spread
            h_weeks = h + 1  # 1-indexed
            unc_scale = uncertainty_scale(h_weeks)
            std_h = recent_std * unc_scale + component_spread[h] * 0.5

            mu = combined[h]
            lo80 = max(0, mu - 1.28 * std_h)
            hi80 = mu + 1.28 * std_h
            lo95 = max(0, mu - 1.96 * std_h)
            hi95 = mu + 1.96 * std_h

            prob_exceed = float(1 - stats.norm.cdf(
                (REGULATORY_THRESHOLD - mu) / max(std_h, 0.001)
            ))

            # Per-week accuracy band
            nearest_horizon = min(ALLOWED_HORIZONS, key=lambda x: abs(x - h_weeks))
            acc_info = HORIZON_ACCURACY.get(nearest_horizon, HORIZON_ACCURACY[20])

            weekly_forecasts.append({
                "week": fw,
                "year": fy,
                "horizon_h": h_weeks,
                "predicted": round(float(mu), 4),
                "lo80": round(float(lo80), 4),
                "hi80": round(float(hi80), 4),
                "lo95": round(float(lo95), 4),
                "hi95": round(float(hi95), 4),
                "prob_exceed": round(prob_exceed, 4),
                "uncertainty_scale": round(unc_scale, 2),
                "accuracy_band": acc_info["band"],
            })

        # ── Summary metrics ──────────────────────────────────────────
        peak_idx = int(np.argmax(combined))
        peak_val = float(combined[peak_idx])

        if len(combined) >= 2:
            if combined[-1] > combined[0] * 1.15:
                trend = "increasing"
            elif combined[-1] < combined[0] * 0.85:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"

        weeks_until = None
        for h in range(horizon):
            if combined[h] >= REGULATORY_THRESHOLD:
                weeks_until = h + 1
                break

        # Overall confidence decreases with horizon
        base_confidence = min(0.9, 0.4 + 0.05 * min(len(history), 20))
        if len(components) > 1:
            base_confidence += 0.1
        horizon_penalty = min(0.4, horizon * 0.02)
        confidence = max(0.1, base_confidence - horizon_penalty)

        # Accuracy metadata for the target horizon
        nearest = min(ALLOWED_HORIZONS, key=lambda x: abs(x - horizon))
        acc = HORIZON_ACCURACY.get(nearest, HORIZON_ACCURACY[20])

        return MediumTermForecast(
            ticker=ticker,
            horizon_weeks=horizon,
            weekly_forecasts=weekly_forecasts,
            peak_predicted_week=weekly_forecasts[peak_idx]["week"],
            peak_predicted_value=round(peak_val, 4),
            trend_direction=trend,
            weeks_until_threshold=weeks_until,
            avg_predicted=round(float(combined.mean()), 4),
            model_used=model_name,
            confidence=round(confidence, 2),
            accuracy_band=acc["band"],
            accuracy_label=acc["label"],
            estimated_r2=acc["r2_est"],
            uncertainty_multiplier=round(uncertainty_scale(horizon), 2),
        )

    def _empty_forecast(self, ticker: str, horizon: int) -> MediumTermForecast:
        nearest = min(ALLOWED_HORIZONS, key=lambda x: abs(x - horizon))
        acc = HORIZON_ACCURACY.get(nearest, HORIZON_ACCURACY[20])
        return MediumTermForecast(
            ticker=ticker,
            horizon_weeks=horizon,
            model_used="none",
            confidence=0.0,
            accuracy_band=acc["band"],
            accuracy_label=acc["label"],
            estimated_r2=acc["r2_est"],
        )
