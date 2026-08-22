"""Add feature_snapshots and prediction_ledger tables with Postgres RLS

Revision ID: 20260810_0008
Revises: 20260810_0007
Create Date: 2026-08-10 17:09:00.000000

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "20260810_0008"
down_revision: str | None = "20260810_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feature_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "lead_id",
            UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("feature_version", sa.String(length=32), nullable=False, server_default="v3.0"),
        sa.Column("snapshot_data", JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "prediction_ledger",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "lead_id",
            UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("feature_version", sa.String(length=32), nullable=False, server_default="v3.0"),
        sa.Column("prediction", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # RLS Policies
    op.execute("ALTER TABLE feature_snapshots ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY feature_snapshots_workspace_isolation ON feature_snapshots
        USING (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid);
        """
    )
    op.execute("ALTER TABLE prediction_ledger ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY prediction_ledger_workspace_isolation ON prediction_ledger
        USING (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.drop_table("prediction_ledger")
    op.drop_table("feature_snapshots")
