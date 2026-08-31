"""phase05_bidder_and_document_management

Revision ID: d4e5f6a7b8c9
Revises: c1f5928d3e41
Create Date: 2026-08-31 22:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c1f5928d3e41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Update bidders table, create tender_bidders, update documents table."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1. Update / Create columns on bidders table
    if "bidders" not in insp.get_table_names():
        op.create_table(
            'bidders',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('company_name', sa.String(length=255), nullable=False),
            sa.Column('registration_number', sa.String(length=100), nullable=True),
            sa.Column('gst_number', sa.String(length=50), nullable=True),
            sa.Column('pan_number', sa.String(length=50), nullable=True),
            sa.Column('udyam_number', sa.String(length=50), nullable=True),
            sa.Column('contact_person', sa.String(length=255), nullable=True),
            sa.Column('email', sa.String(length=255), nullable=True),
            sa.Column('phone', sa.String(length=50), nullable=True),
            sa.Column('address', sa.Text(), nullable=True),
            sa.Column(
                'status',
                sa.Enum('ACTIVE', 'INACTIVE', 'SUSPENDED', name='bidderstatus', native_enum=False, length=50),
                nullable=False,
                server_default='ACTIVE',
            ),
            sa.Column('user_id', sa.UUID(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_bidders_company_name'), 'bidders', ['company_name'], unique=False)
        op.create_index(op.f('ix_bidders_registration_number'), 'bidders', ['registration_number'], unique=False)
        op.create_index(op.f('ix_bidders_gst_number'), 'bidders', ['gst_number'], unique=False)
        op.create_index(op.f('ix_bidders_pan_number'), 'bidders', ['pan_number'], unique=False)
        op.create_index(op.f('ix_bidders_email'), 'bidders', ['email'], unique=False)
        op.create_index(op.f('ix_bidders_status'), 'bidders', ['status'], unique=False)
    else:
        bidder_indexes = [idx["name"] for idx in insp.get_indexes("bidders")]
        if 'ix_bidders_organization_name' in bidder_indexes:
            op.drop_index('ix_bidders_organization_name', table_name='bidders')

        bidder_columns = [col["name"] for col in insp.get_columns("bidders")]
        with op.batch_alter_table('bidders', schema=None) as batch_op:
            batch_op.alter_column('user_id', existing_type=sa.UUID(), nullable=True)
            if 'company_name' not in bidder_columns:
                batch_op.add_column(sa.Column('company_name', sa.String(length=255), nullable=False, server_default='Company'))
            if 'organization_name' in bidder_columns:
                batch_op.drop_column('organization_name')
            if 'gst_number' not in bidder_columns:
                batch_op.add_column(sa.Column('gst_number', sa.String(length=50), nullable=True))
            if 'pan_number' not in bidder_columns:
                batch_op.add_column(sa.Column('pan_number', sa.String(length=50), nullable=True))
            if 'udyam_number' not in bidder_columns:
                batch_op.add_column(sa.Column('udyam_number', sa.String(length=50), nullable=True))
            if 'contact_person' not in bidder_columns:
                batch_op.add_column(sa.Column('contact_person', sa.String(length=255), nullable=True))
            if 'email' not in bidder_columns:
                batch_op.add_column(sa.Column('email', sa.String(length=255), nullable=True))
            if 'phone' not in bidder_columns:
                batch_op.add_column(sa.Column('phone', sa.String(length=50), nullable=True))
            if 'address' not in bidder_columns:
                batch_op.add_column(sa.Column('address', sa.Text(), nullable=True))
            if 'status' not in bidder_columns:
                batch_op.add_column(
                    sa.Column(
                        'status',
                        sa.Enum('ACTIVE', 'INACTIVE', 'SUSPENDED', name='bidderstatus', native_enum=False, length=50),
                        nullable=False,
                        server_default='ACTIVE',
                    )
                )

        op.create_index(op.f('ix_bidders_company_name'), 'bidders', ['company_name'], unique=False)
        op.create_index(op.f('ix_bidders_gst_number'), 'bidders', ['gst_number'], unique=False)
        op.create_index(op.f('ix_bidders_pan_number'), 'bidders', ['pan_number'], unique=False)
        op.create_index(op.f('ix_bidders_email'), 'bidders', ['email'], unique=False)
        op.create_index(op.f('ix_bidders_status'), 'bidders', ['status'], unique=False)

    # 2. Create tender_bidders association table
    if "tender_bidders" not in insp.get_table_names():
        op.create_table(
            'tender_bidders',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('tender_id', sa.UUID(), nullable=False),
            sa.Column('bidder_id', sa.UUID(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['bidder_id'], ['bidders.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('tender_id', 'bidder_id', name='uq_tender_bidder'),
        )
        op.create_index(op.f('ix_tender_bidders_tender_id'), 'tender_bidders', ['tender_id'], unique=False)
        op.create_index(op.f('ix_tender_bidders_bidder_id'), 'tender_bidders', ['bidder_id'], unique=False)

    # 3. Update documents table
    if "documents" in insp.get_table_names():
        doc_columns = [col["name"] for col in insp.get_columns("documents")]
        with op.batch_alter_table('documents', schema=None) as batch_op:
            batch_op.alter_column('tender_id', existing_type=sa.UUID(), nullable=True)
            if 'original_filename' not in doc_columns:
                batch_op.add_column(sa.Column('original_filename', sa.String(length=255), nullable=False, server_default='document.pdf'))
            if 'file_name' in doc_columns:
                batch_op.drop_column('file_name')
            if 'storage_path' not in doc_columns:
                batch_op.add_column(sa.Column('storage_path', sa.String(length=1000), nullable=False, server_default='storage/document.pdf'))
            if 'file_path' in doc_columns:
                batch_op.drop_column('file_path')
            if 'status' not in doc_columns:
                batch_op.add_column(
                    sa.Column(
                        'status',
                        sa.Enum('UPLOADED', 'PROCESSING', 'VERIFIED', 'REJECTED', name='documentstatus', native_enum=False, length=50),
                        nullable=False,
                        server_default='UPLOADED',
                    )
                )
            if 'created_at' not in doc_columns:
                batch_op.add_column(
                    sa.Column(
                        'created_at',
                        sa.DateTime(timezone=True),
                        server_default=sa.func.now(),
                        nullable=False,
                    )
                )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('tender_bidders')
