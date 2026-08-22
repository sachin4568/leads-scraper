"""add_job_id_and_lead_code_to_leads

Revision ID: 5ea23b8c484a
Revises: 36fa7c922ae4
Create Date: 2026-08-19 23:53:25.792950

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5ea23b8c484a'
down_revision: Union[str, None] = '36fa7c922ae4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to leads table
    op.add_column('leads', sa.Column('job_id', sa.UUID(), nullable=True))
    op.add_column('leads', sa.Column('lead_code', sa.String(length=32), nullable=True))
    
    # Create foreign key constraint
    op.create_foreign_key(
        'fk_leads_job_id_scrape_jobs',
        'leads', 'scrape_jobs',
        ['job_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index(op.f('ix_leads_job_id'), 'leads', ['job_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_leads_job_id'), table_name='leads')
    op.drop_constraint('fk_leads_job_id_scrape_jobs', 'leads', type_='foreignkey')
    op.drop_column('leads', 'lead_code')
    op.drop_column('leads', 'job_id')
