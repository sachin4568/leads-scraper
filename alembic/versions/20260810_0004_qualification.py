"""Phase 4 service intelligence and qualification table with RLS

Revision ID: 20260810_0004
Revises: 20260810_0003
Create Date: 2026-08-10 23:59:00.000000

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260810_0004"
down_revision: str | None = "20260810_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("service_type", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="LOW"),
        sa.Column("breakdown", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE service_scores ENABLE ROW LEVEL SECURITY;")
        op.execute(
            """
            CREATE POLICY service_scores_isolation ON service_scores
            USING (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid);
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS service_scores_isolation ON service_scores;")

    op.drop_table("service_scores")
