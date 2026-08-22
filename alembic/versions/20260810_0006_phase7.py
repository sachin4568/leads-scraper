"""Phase 7 human feedback table with RLS

Revision ID: 20260810_0006
Revises: 20260810_0005
Create Date: 2026-08-10 02:08:00.000000

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260810_0006"
down_revision: str | None = "20260810_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "human_feedback",
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
        sa.Column("rating", sa.String(length=32), nullable=False),
        sa.Column("service_label", sa.String(length=64), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE human_feedback ENABLE ROW LEVEL SECURITY;")
        op.execute(
            """
            CREATE POLICY human_feedback_isolation ON human_feedback
            USING (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid);
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS human_feedback_isolation ON human_feedback;")

    op.drop_table("human_feedback")
