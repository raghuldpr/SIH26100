"""add_phase03b_tender_fields

Revision ID: a8d436109f2b
Revises: 652069397f72
Create Date: 2026-08-31 21:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8d436109f2b'
down_revision: Union[str, Sequence[str], None] = '652069397f72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add department, category, bid dates, and created_by to tenders."""
    with op.batch_alter_table('tenders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('department', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('category', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('bid_start_date', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('bid_end_date', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('created_by', sa.UUID(), nullable=True))

    op.create_index(op.f('ix_tenders_department'), 'tenders', ['department'], unique=False)
    op.create_index(op.f('ix_tenders_category'), 'tenders', ['category'], unique=False)
    op.create_index(op.f('ix_tenders_created_by'), 'tenders', ['created_by'], unique=False)


def downgrade() -> None:
    """Downgrade schema: Remove Phase 03B columns from tenders."""
    op.drop_index(op.f('ix_tenders_created_by'), table_name='tenders')
    op.drop_index(op.f('ix_tenders_category'), table_name='tenders')
    op.drop_index(op.f('ix_tenders_department'), table_name='tenders')

    with op.batch_alter_table('tenders', schema=None) as batch_op:
        batch_op.drop_column('created_by')
        batch_op.drop_column('bid_end_date')
        batch_op.drop_column('bid_start_date')
        batch_op.drop_column('category')
        batch_op.drop_column('department')
