"""Add EnrichmentState model

Revision ID: 7652bf0c23c6
Revises: c4e5f6a7b8d9
Create Date: 2026-09-04 14:55:28.797763

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7652bf0c23c6'
down_revision: Union[str, None] = 'c4e5f6a7b8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('enrichment_states',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('raw_lead_id', sa.UUID(), nullable=False),
    sa.Column('website_status', sa.String(length=32), nullable=False, server_default='PENDING'),
    sa.Column('email_status', sa.String(length=32), nullable=False, server_default='PENDING'),
    sa.Column('social_status', sa.String(length=32), nullable=False, server_default='PENDING'),
    sa.Column('seo_status', sa.String(length=32), nullable=False, server_default='PENDING'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['raw_lead_id'], ['raw_leads.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_enrichment_states_raw_lead_id'), 'enrichment_states', ['raw_lead_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_enrichment_states_raw_lead_id'), table_name='enrichment_states')
    op.drop_table('enrichment_states')
