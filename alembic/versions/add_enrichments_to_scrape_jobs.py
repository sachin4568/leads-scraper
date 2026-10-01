"""Add enrichments to scrape_jobs

Revision ID: c4e5f6a7b8d9
Revises: b3f4c8d2e9a1
Create Date: 2026-08-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = 'c4e5f6a7b8d9'
down_revision = 'b3f4c8d2e9a1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('scrape_jobs', sa.Column('enrichments', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('scrape_jobs', 'enrichments')
