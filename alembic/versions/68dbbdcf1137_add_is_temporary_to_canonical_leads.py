"""add is_temporary to canonical_leads

Revision ID: 68dbbdcf1137
Revises: 85ecaf65624a
Create Date: 2026-08-21 23:35:06.266033

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '68dbbdcf1137'
down_revision: Union[str, None] = '85ecaf65624a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('canonical_leads', sa.Column('is_temporary', sa.Boolean(), server_default='true', nullable=False))


def downgrade() -> None:
    op.drop_column('canonical_leads', 'is_temporary')
