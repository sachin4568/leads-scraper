"""Phase 3 enrichment, audit log, and suppression tables with RLS

Revision ID: 20260810_0003
Revises: 20260810_0002
Create Date: 2026-08-10 17:54:00.000000

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260810_0003"
down_revision: str | None = "20260810_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. evidence_records
    op.create_table(
        "evidence_records",
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
        sa.Column("field_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="UNVERIFIED"),
        sa.Column("confidence_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 2. audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource", sa.String(length=120), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 3. suppression_lists
    op.create_table(
        "suppression_lists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("entry_value", sa.String(length=320), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "workspace_id", "entry_type", "entry_value", name="uq_suppression_entry"
        ),
    )

    # Row-Level Security policies
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE evidence_records ENABLE ROW LEVEL SECURITY;")
        op.execute(
            """
            CREATE POLICY evidence_records_isolation ON evidence_records
            USING (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid);
            """
        )
        op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;")
        op.execute(
            """
            CREATE POLICY audit_logs_isolation ON audit_logs
            USING (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid);
            """
        )
        op.execute("ALTER TABLE suppression_lists ENABLE ROW LEVEL SECURITY;")
        op.execute(
            """
            CREATE POLICY suppression_lists_isolation ON suppression_lists
            USING (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid);
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS suppression_lists_isolation ON suppression_lists;")
        op.execute("DROP POLICY IF EXISTS audit_logs_isolation ON audit_logs;")
        op.execute("DROP POLICY IF EXISTS evidence_records_isolation ON evidence_records;")

    op.drop_table("suppression_lists")
    op.drop_table("audit_logs")
    op.drop_table("evidence_records")
