"""add_tender_bid_end_date_index_and_constraint

Revision ID: c1f5928d3e41
Revises: a8d436109f2b
Create Date: 2026-08-31 22:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1f5928d3e41'
down_revision: Union[str, Sequence[str], None] = 'a8d436109f2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add bid_end_date index and check constraint on tenders table."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    indexes = [idx["name"] for idx in insp.get_indexes("tenders")]

    with op.batch_alter_table('tenders', schema=None) as batch_op:
        if 'ix_tenders_bid_end_date' not in indexes:
            batch_op.create_index(batch_op.f('ix_tenders_bid_end_date'), ['bid_end_date'], unique=False)
        batch_op.create_check_constraint(
            'check_tender_bid_end_after_start_date',
            'bid_end_date >= bid_start_date',
        )


def downgrade() -> None:
    """Downgrade schema: Remove check constraint and bid_end_date index."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    indexes = [idx["name"] for idx in insp.get_indexes("tenders")]

    with op.batch_alter_table('tenders', schema=None) as batch_op:
        batch_op.drop_constraint('check_tender_bid_end_after_start_date', type_='check')
        if 'ix_tenders_bid_end_date' in indexes:
            batch_op.drop_index(batch_op.f('ix_tenders_bid_end_date'))
