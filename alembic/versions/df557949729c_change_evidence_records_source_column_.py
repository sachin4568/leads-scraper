"""Change evidence_records source column to Text

Revision ID: df557949729c
Revises: 225019fce547
Create Date: 2026-09-05 00:03:16.526227

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'df557949729c'
down_revision: Union[str, None] = '225019fce547'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('evidence_records', 'source',
               existing_type=sa.VARCHAR(length=64),
               type_=sa.Text(),
               existing_nullable=False)


def downgrade() -> None:
    op.alter_column('evidence_records', 'source',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=64),
               existing_nullable=False)
