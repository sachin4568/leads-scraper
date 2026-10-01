"""Add evidence_type and classification to EvidenceRecord

Revision ID: f9be7dbc54b4
Revises: 7652bf0c23c6
Create Date: 2026-09-04 10:55:10.024560

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f9be7dbc54b4'
down_revision: Union[str, None] = '7652bf0c23c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('evidence_records', sa.Column('evidence_type', sa.String(length=64), nullable=True))
    op.add_column('evidence_records', sa.Column('classification', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_evidence_type'), 'evidence_records', ['lead_id', 'evidence_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_evidence_type'), table_name='evidence_records')
    op.drop_column('evidence_records', 'classification')
    op.drop_column('evidence_records', 'evidence_type')
