"""Phase 5 campaign and email dispatch tables with RLS

Revision ID: 20260810_0005
Revises: 20260810_0004
Create Date: 2026-08-10 00:27:00.000000

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260810_0005"
down_revision: str | None = "20260810_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. outreach_campaigns
    op.create_table(
        "outreach_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("subject_template", sa.String(length=255), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # 2. email_dispatches
    op.create_table(
        "email_dispatches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("outreach_campaigns.id", ondelete="CASCADE"),
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
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Row-Level Security policies
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE outreach_campaigns ENABLE ROW LEVEL SECURITY;")
        op.execute(
            """
            CREATE POLICY outreach_campaigns_isolation ON outreach_campaigns
            USING (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid);
            """
        )
        op.execute("ALTER TABLE email_dispatches ENABLE ROW LEVEL SECURITY;")
        op.execute(
            """
            CREATE POLICY email_dispatches_isolation ON email_dispatches
            USING (workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::uuid);
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS email_dispatches_isolation ON email_dispatches;")
        op.execute("DROP POLICY IF EXISTS outreach_campaigns_isolation ON outreach_campaigns;")

    op.drop_table("email_dispatches")
    op.drop_table("outreach_campaigns")
