"""phase11_document_sha256

Revision ID: h8c9d0e1f2a3
Revises: g7b8c9d0e1f2
Create Date: 2026-09-02 10:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h8c9d0e1f2a3'
down_revision: Union[str, Sequence[str], None] = 'g7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add sha256 checksum column and index to documents table."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "documents" in insp.get_table_names():
        doc_columns = [col["name"] for col in insp.get_columns("documents")]
        doc_indexes = [idx["name"] for idx in insp.get_indexes("documents")]

        with op.batch_alter_table('documents', schema=None) as batch_op:
            if 'sha256' not in doc_columns:
                batch_op.add_column(
                    sa.Column(
                        'sha256',
                        sa.String(length=64),
                        nullable=True,
                    )
                )

        if 'ix_documents_sha256' not in doc_indexes:
            op.create_index(
                op.f('ix_documents_sha256'),
                'documents',
                ['sha256'],
                unique=False,
            )


def downgrade() -> None:
    """Downgrade schema: Remove sha256 column and index from documents table."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "documents" in insp.get_table_names():
        doc_indexes = [idx["name"] for idx in insp.get_indexes("documents")]
        if 'ix_documents_sha256' in doc_indexes:
            op.drop_index(op.f('ix_documents_sha256'), table_name='documents')

        with op.batch_alter_table('documents', schema=None) as batch_op:
            batch_op.drop_column('sha256')
