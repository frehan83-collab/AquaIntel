"""Add offshore farm columns to localities table.

Extends the Locality model with fields specific to offshore aquaculture:
farm_type, max_depth_m, current_speed_avg_ms, wave_exposure_class,
structural_stress_rating, cage_volume_m3, distance_to_shore_km.

All columns are nullable for backward compatibility with existing inshore farms.

Reference: SalMar Ocean Farm 1 (2017, Frohavet), Ocean Farm 2 (construction 2025+)

Revision ID: 012
Revises: 011
Create Date: 2026-04-06
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("localities", sa.Column("farm_type", sa.String(32), server_default="inshore"))
    op.add_column("localities", sa.Column("max_depth_m", sa.Float, nullable=True))
    op.add_column("localities", sa.Column("current_speed_avg_ms", sa.Float, nullable=True))
    op.add_column("localities", sa.Column("wave_exposure_class", sa.String(32), nullable=True))
    op.add_column("localities", sa.Column("structural_stress_rating", sa.Float, nullable=True))
    op.add_column("localities", sa.Column("cage_volume_m3", sa.Float, nullable=True))
    op.add_column("localities", sa.Column("distance_to_shore_km", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("localities", "distance_to_shore_km")
    op.drop_column("localities", "cage_volume_m3")
    op.drop_column("localities", "structural_stress_rating")
    op.drop_column("localities", "wave_exposure_class")
    op.drop_column("localities", "current_speed_avg_ms")
    op.drop_column("localities", "max_depth_m")
    op.drop_column("localities", "farm_type")
