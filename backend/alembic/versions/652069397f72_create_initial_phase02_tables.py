"""create_initial_phase02_tables

Revision ID: 652069397f72
Revises: 
Create Date: 2026-08-31 20:55:12.162794

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '652069397f72'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Create users, tenders, bidders, and documents tables."""
    # 1. users table (no foreign keys)
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column(
            'role',
            sa.Enum('ADMIN', 'BUYER', 'BIDDER', 'REVIEWER', name='userrole', native_enum=False, length=50),
            nullable=False,
        ),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)

    # 2. tenders table (no foreign keys)
    op.create_table(
        'tenders',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tender_number', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('organization', sa.String(length=255), nullable=False),
        sa.Column(
            'status',
            sa.Enum('DRAFT', 'PUBLISHED', 'EVALUATING', 'CLOSED', 'ARCHIVED', name='tenderstatus', native_enum=False, length=50),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tenders_tender_number'), 'tenders', ['tender_number'], unique=True)
    op.create_index(op.f('ix_tenders_status'), 'tenders', ['status'], unique=False)
    op.create_index(op.f('ix_tenders_organization'), 'tenders', ['organization'], unique=False)

    # 3. bidders table (foreign key -> users.id)
    op.create_table(
        'bidders',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('organization_name', sa.String(length=255), nullable=False),
        sa.Column('registration_number', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_bidders_user_id'), 'bidders', ['user_id'], unique=False)
    op.create_index(op.f('ix_bidders_organization_name'), 'bidders', ['organization_name'], unique=False)
    op.create_index(op.f('ix_bidders_registration_number'), 'bidders', ['registration_number'], unique=False)

    # 4. documents table (foreign keys -> tenders.id, bidders.id)
    op.create_table(
        'documents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tender_id', sa.UUID(), nullable=False),
        sa.Column('bidder_id', sa.UUID(), nullable=True),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column(
            'document_type',
            sa.Enum('TENDER_NOTICE', 'TECHNICAL_BID', 'FINANCIAL_BID', 'COMPLIANCE_DECLARATION', 'CERTIFICATE', 'OTHER', name='documenttype', native_enum=False, length=50),
            nullable=False,
        ),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['bidder_id'], ['bidders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_documents_tender_id'), 'documents', ['tender_id'], unique=False)
    op.create_index(op.f('ix_documents_bidder_id'), 'documents', ['bidder_id'], unique=False)
    op.create_index(op.f('ix_documents_document_type'), 'documents', ['document_type'], unique=False)


def downgrade() -> None:
    """Downgrade schema in reverse dependency order."""
    # 1. Drop documents table
    op.drop_index(op.f('ix_documents_document_type'), table_name='documents')
    op.drop_index(op.f('ix_documents_bidder_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_tender_id'), table_name='documents')
    op.drop_table('documents')

    # 2. Drop bidders table
    op.drop_index(op.f('ix_bidders_registration_number'), table_name='bidders')
    op.drop_index(op.f('ix_bidders_organization_name'), table_name='bidders')
    op.drop_index(op.f('ix_bidders_user_id'), table_name='bidders')
    op.drop_table('bidders')

    # 3. Drop tenders table
    op.drop_index(op.f('ix_tenders_organization'), table_name='tenders')
    op.drop_index(op.f('ix_tenders_status'), table_name='tenders')
    op.drop_index(op.f('ix_tenders_tender_number'), table_name='tenders')
    op.drop_table('tenders')

    # 4. Drop users table
    op.drop_index(op.f('ix_users_role'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
