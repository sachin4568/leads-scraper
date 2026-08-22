"""add_service_to_scrape_jobs

Revision ID: 85ecaf65624a
Revises: 5ea23b8c484a
Create Date: 2026-08-19 23:54:25.792950

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '85ecaf65624a'
down_revision: Union[str, None] = '5ea23b8c484a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add column to scrape_jobs table
    op.add_column('scrape_jobs', sa.Column('service', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('scrape_jobs', 'service')
