"""add canonical_lead_id to evidence_records

Revision ID: a00fc9bfbdda
Revises: 68dbbdcf1137
Create Date: 2026-08-21 23:40:11.266033

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a00fc9bfbdda'
down_revision: Union[str, None] = '68dbbdcf1137'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('evidence_records', sa.Column('canonical_lead_id', sa.String(36), nullable=True))
    op.create_index(op.f('ix_evidence_records_canonical_lead_id'), 'evidence_records', ['canonical_lead_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_evidence_records_canonical_lead_id'), table_name='evidence_records')
    op.drop_column('evidence_records', 'canonical_lead_id')
