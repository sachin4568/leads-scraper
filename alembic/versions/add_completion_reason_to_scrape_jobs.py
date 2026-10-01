"""Add completion_reason and fetched_count to scrape_jobs

Revision ID: b3f4c8d2e9a1
Revises: merge_and_conflicts_merge_heads_and_conflicts
Create Date: 2026-08-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = 'b3f4c8d2e9a1'
down_revision = 'merge_and_conflicts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('scrape_jobs', sa.Column('completion_reason', sa.String(64), nullable=True))
    op.add_column('scrape_jobs', sa.Column('fetched_count', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('scrape_jobs', 'fetched_count')
    op.drop_column('scrape_jobs', 'completion_reason')
