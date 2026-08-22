"""add_scrape_job_counters

Revision ID: 36fa7c922ae4
Revises: 20260810_0008
Create Date: 2026-08-19 23:51:24.792950

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '36fa7c922ae4'
down_revision: Union[str, None] = '20260810_0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create scrape_job_execution_logs table
    op.create_table('scrape_job_execution_logs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('job_id', sa.UUID(), nullable=False),
    sa.Column('source', sa.String(length=64), nullable=False),
    sa.Column('query', sa.String(length=255), nullable=False),
    sa.Column('page', sa.Integer(), nullable=False),
    sa.Column('records_received', sa.Integer(), nullable=False),
    sa.Column('records_valid', sa.Integer(), nullable=False),
    sa.Column('records_rejected', sa.Integer(), nullable=False),
    sa.Column('new_count', sa.Integer(), nullable=False),
    sa.Column('updated_count', sa.Integer(), nullable=False),
    sa.Column('duplicate_count', sa.Integer(), nullable=False),
    sa.Column('failed_count', sa.Integer(), nullable=False),
    sa.Column('error_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['scrape_jobs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scrape_job_execution_logs_job_id'), 'scrape_job_execution_logs', ['job_id'], unique=False)

    # Add columns to scrape_jobs
    op.add_column('scrape_jobs', sa.Column('discovered_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('scrape_jobs', sa.Column('valid_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('scrape_jobs', sa.Column('new_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('scrape_jobs', sa.Column('updated_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('scrape_jobs', sa.Column('duplicate_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('scrape_jobs', sa.Column('failed_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('scrape_jobs', sa.Column('current_source', sa.String(length=64), nullable=True))
    op.add_column('scrape_jobs', sa.Column('current_query', sa.String(length=255), nullable=True))
    op.add_column('scrape_jobs', sa.Column('progress_percent', sa.Float(), nullable=False, server_default='0.0'))


def downgrade() -> None:
    # Drop columns from scrape_jobs
    op.drop_column('scrape_jobs', 'progress_percent')
    op.drop_column('scrape_jobs', 'current_query')
    op.drop_column('scrape_jobs', 'current_source')
    op.drop_column('scrape_jobs', 'failed_count')
    op.drop_column('scrape_jobs', 'duplicate_count')
    op.drop_column('scrape_jobs', 'updated_count')
    op.drop_column('scrape_jobs', 'new_count')
    op.drop_column('scrape_jobs', 'valid_count')
    op.drop_column('scrape_jobs', 'discovered_count')

    # Drop scrape_job_execution_logs table
    op.drop_index(op.f('ix_scrape_job_execution_logs_job_id'), table_name='scrape_job_execution_logs')
    op.drop_table('scrape_job_execution_logs')
