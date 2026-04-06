"""Database models for Algal Bloom Early Warning."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Column, Integer, Float, String, DateTime, Text, ForeignKey,
    UniqueConstraint, Index,
)

from core.models import Base


class ChlorophyllReading(Base):
    """Satellite-derived chlorophyll-a concentration from CMEMS."""
    __tablename__ = "chlorophyll_readings"
    __table_args__ = (
        UniqueConstraint("date", "grid_cell_id", name="uq_chl_date_cell"),
        Index("ix_chl_date", "date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    grid_cell_id = Column(String(32), nullable=False)  # e.g. "60.50_5.25"
    chl_a_mg_m3 = Column(Float, nullable=False)
    dataset_id = Column(String(128), default="cmems_obs-oc_atl_bgc-plankton_nrt_l3-multi-1km_P1D")
    fetched_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC))


class BloomRiskAssessment(Base):
    """Computed bloom risk per farm locality."""
    __tablename__ = "bloom_risk_assessments"
    __table_args__ = (
        Index("ix_bloom_risk_locality", "locality_no", "assessed_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    locality_no = Column(Integer, ForeignKey("localities.locality_no"), nullable=False)
    assessed_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC), nullable=False)
    chl_a_value = Column(Float)
    sst_value = Column(Float)
    chl_a_trend = Column(Float)  # mg/m3 per day (positive = rising)
    risk_level = Column(String(16), nullable=False)  # LOW / ELEVATED / HIGH / CRITICAL
    risk_score = Column(Float)  # 0-100
    nearest_grid_cell_id = Column(String(32))
    contributing_factors = Column(Text)  # JSON: list of factor strings


class BloomAlert(Base):
    """Alert sent to a fish farmer about bloom risk."""
    __tablename__ = "bloom_alerts"
    __table_args__ = (
        Index("ix_bloom_alert_locality", "locality_no", "sent_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    locality_no = Column(Integer, ForeignKey("localities.locality_no"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    risk_level = Column(String(16), nullable=False)
    sent_at = Column(DateTime, default=lambda: dt.datetime.now(dt.UTC), nullable=False)
    channel = Column(String(16), nullable=False)  # sms / email / dashboard
    delivery_status = Column(String(16), default="sent")  # sent / delivered / failed
    message_text = Column(Text)
