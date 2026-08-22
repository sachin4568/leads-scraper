"""merge heads and conflicts

Revision ID: merge_and_conflicts
Revises: ('a00fc9bfbdda', 'c1b9f4a37e2d')
Create Date: 2026-08-22 11:23:40.703162

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'merge_and_conflicts'
down_revision: Union[str, None] = ('a00fc9bfbdda', 'c1b9f4a37e2d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('canonical_leads', sa.Column('conflicts', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('canonical_leads', 'conflicts')
