"""phase06_document_model_enhancement

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-31 22:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add processing_status, processing_error, and extracted_data to documents."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "documents" in insp.get_table_names():
        doc_columns = [col["name"] for col in insp.get_columns("documents")]
        doc_indexes = [idx["name"] for idx in insp.get_indexes("documents")]

        with op.batch_alter_table('documents', schema=None) as batch_op:
            if 'processing_status' not in doc_columns:
                batch_op.add_column(
                    sa.Column(
                        'processing_status',
                        sa.Enum(
                            'NOT_PROCESSED',
                            'PROCESSING',
                            'PROCESSED',
                            'FAILED',
                            name='processingstatus',
                            native_enum=False,
                            length=50,
                        ),
                        nullable=False,
                        server_default='NOT_PROCESSED',
                    )
                )
            if 'processing_error' not in doc_columns:
                batch_op.add_column(
                    sa.Column(
                        'processing_error',
                        sa.Text(),
                        nullable=True,
                    )
                )
            if 'extracted_data' not in doc_columns:
                batch_op.add_column(
                    sa.Column(
                        'extracted_data',
                        sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'),
                        nullable=True,
                    )
                )

        # Create indexes if not present
        if 'ix_documents_processing_status' not in doc_indexes:
            op.create_index(
                op.f('ix_documents_processing_status'),
                'documents',
                ['processing_status'],
                unique=False,
            )
        if 'ix_documents_status' not in doc_indexes:
            op.create_index(
                op.f('ix_documents_status'),
                'documents',
                ['status'],
                unique=False,
            )
        if 'ix_documents_document_type' not in doc_indexes:
            op.create_index(
                op.f('ix_documents_document_type'),
                'documents',
                ['document_type'],
                unique=False,
            )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "documents" in insp.get_table_names():
        doc_indexes = [idx["name"] for idx in insp.get_indexes("documents")]
        if 'ix_documents_processing_status' in doc_indexes:
            op.drop_index(op.f('ix_documents_processing_status'), table_name='documents')

        with op.batch_alter_table('documents', schema=None) as batch_op:
            batch_op.drop_column('extracted_data')
            batch_op.drop_column('processing_error')
            batch_op.drop_column('processing_status')
