"""phase21_gem_tender_fields

Revision ID: j0e1f2a3b4c5
Revises: i9d0e1f2a3b4
Create Date: 2026-09-06 16:38:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j0e1f2a3b4c5'
down_revision: Union[str, Sequence[str], None] = 'i9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add source and gem_bid_id to tenders table."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "tenders" in insp.get_table_names():
        tender_columns = [col["name"] for col in insp.get_columns("tenders")]
        tender_indexes = [idx["name"] for idx in insp.get_indexes("tenders")]

        with op.batch_alter_table('tenders', schema=None) as batch_op:
            if 'source' not in tender_columns:
                batch_op.add_column(
                    sa.Column(
                        'source',
                        sa.String(length=50),
                        nullable=False,
                        server_default='MANUAL',
                    )
                )
            if 'gem_bid_id' not in tender_columns:
                batch_op.add_column(
                    sa.Column(
                        'gem_bid_id',
                        sa.String(length=100),
                        nullable=True,
                    )
                )

        if 'ix_tenders_gem_bid_id' not in tender_indexes:
            op.create_index(
                op.f('ix_tenders_gem_bid_id'),
                'tenders',
                ['gem_bid_id'],
                unique=True,
            )


def downgrade() -> None:
    """Downgrade schema: Remove gem_bid_id and source from tenders table."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "tenders" in insp.get_table_names():
        tender_indexes = [idx["name"] for idx in insp.get_indexes("tenders")]
        if 'ix_tenders_gem_bid_id' in tender_indexes:
            op.drop_index(op.f('ix_tenders_gem_bid_id'), table_name='tenders')

        with op.batch_alter_table('tenders', schema=None) as batch_op:
            batch_op.drop_column('gem_bid_id')
            batch_op.drop_column('source')
