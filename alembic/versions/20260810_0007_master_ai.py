"""Add raw_status, verification_status, genuineness_status, genuineness_score to leads table

Revision ID: 20260810_0007
Revises: 20260810_0006
Create Date: 2026-08-10 16:21:00.000000

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260810_0007"
down_revision: str | None = "20260810_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("raw_status", sa.String(length=32), nullable=False, server_default="PERSISTED"),
    )
    op.add_column(
        "leads",
        sa.Column(
            "verification_status", sa.String(length=32), nullable=False, server_default="UNVERIFIED"
        ),
    )
    op.add_column(
        "leads",
        sa.Column(
            "genuineness_status",
            sa.String(length=32),
            nullable=False,
            server_default="NEEDS_REVIEW",
        ),
    )
    op.add_column(
        "leads",
        sa.Column("genuineness_score", sa.Float(), nullable=False, server_default="0.5"),
    )


def downgrade() -> None:
    op.drop_column("leads", "genuineness_score")
    op.drop_column("leads", "genuineness_status")
    op.drop_column("leads", "verification_status")
    op.drop_column("leads", "raw_status")
