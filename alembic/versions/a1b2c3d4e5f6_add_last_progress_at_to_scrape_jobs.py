"""Add last_progress_at to scrape_jobs

Revision ID: a1b2c3d4e5f6
Revises: df557949729c
Create Date: 2026-09-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "df557949729c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scrape_jobs", sa.Column("last_progress_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("scrape_jobs", "last_progress_at")
