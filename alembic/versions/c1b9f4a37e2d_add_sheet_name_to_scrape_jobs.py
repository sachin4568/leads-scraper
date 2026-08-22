"""add_sheet_name_to_scrape_jobs

Revision ID: c1b9f4a37e2d
Revises: 85ecaf65624a
Create Date: 2026-08-22 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c1b9f4a37e2d'
down_revision: Union[str, None] = '85ecaf65624a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add sheet_name column to store the user-given display name separately from niche
    op.add_column('scrape_jobs', sa.Column('sheet_name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('scrape_jobs', 'sheet_name')
