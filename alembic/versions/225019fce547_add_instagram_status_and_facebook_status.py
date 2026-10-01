"""Add instagram_status and facebook_status

Revision ID: 225019fce547
Revises: f9be7dbc54b4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '225019fce547'
down_revision: Union[str, None] = 'f9be7dbc54b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('enrichment_states', sa.Column('instagram_status', sa.String(length=32), nullable=False, server_default='PENDING'))
    op.add_column('enrichment_states', sa.Column('facebook_status', sa.String(length=32), nullable=False, server_default='PENDING'))
    op.drop_column('enrichment_states', 'social_status')

def downgrade() -> None:
    op.add_column('enrichment_states', sa.Column('social_status', sa.VARCHAR(length=32), autoincrement=False, nullable=False, server_default='PENDING'))
    op.drop_column('enrichment_states', 'facebook_status')
    op.drop_column('enrichment_states', 'instagram_status')
