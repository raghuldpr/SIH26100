"""phase12_verification_persistence

Revision ID: i9d0e1f2a3b4
Revises: h8c9d0e1f2a3
Create Date: 2026-09-02 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'i9d0e1f2a3b4'
down_revision: Union[str, Sequence[str], None] = 'h8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Create verification_executions and verification_audit_events tables."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = insp.get_table_names()

    # 1. verification_executions table
    if "verification_executions" not in table_names:
        op.create_table(
            'verification_executions',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('verification_id', sa.String(length=100), nullable=False),
            sa.Column('request_id', sa.String(length=100), nullable=False),
            sa.Column('tender_id', sa.UUID(), nullable=False),
            sa.Column('bidder_id', sa.UUID(), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='QUEUED'),
            sa.Column('request_hash', sa.String(length=64), nullable=False),
            sa.Column('result_hash', sa.String(length=64), nullable=True),
            sa.Column('overall_compliance', sa.String(length=50), nullable=True),
            sa.Column('decision', sa.String(length=50), nullable=True),
            sa.Column('risk_level', sa.String(length=50), nullable=True),
            sa.Column('risk_score', sa.Float(), nullable=True),
            sa.Column('overall_confidence', sa.Float(), nullable=True),
            sa.Column('compliance_summary', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
            sa.Column('requirements', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
            sa.Column('agent_results', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
            sa.Column('risk_assessment', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
            sa.Column('evidence_snapshot', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
            sa.Column('document_hashes', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
            sa.Column('reasons', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
            sa.Column('failed_requirements', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
            sa.Column('warnings', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
            sa.Column('inconclusive_checks', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
            sa.Column('missing_documents', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
            sa.Column('error', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['bidder_id'], ['bidders.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_verification_executions_verification_id'), 'verification_executions', ['verification_id'], unique=True)
        op.create_index(op.f('ix_verification_executions_request_id'), 'verification_executions', ['request_id'], unique=False)
        op.create_index(op.f('ix_verification_executions_tender_id'), 'verification_executions', ['tender_id'], unique=False)
        op.create_index(op.f('ix_verification_executions_bidder_id'), 'verification_executions', ['bidder_id'], unique=False)
        op.create_index(op.f('ix_verification_executions_status'), 'verification_executions', ['status'], unique=False)
        op.create_index(op.f('ix_verification_executions_request_hash'), 'verification_executions', ['request_hash'], unique=False)
        op.create_index(op.f('ix_verification_executions_result_hash'), 'verification_executions', ['result_hash'], unique=False)
        op.create_index(op.f('ix_verification_executions_overall_compliance'), 'verification_executions', ['overall_compliance'], unique=False)
        op.create_index(op.f('ix_verification_executions_risk_level'), 'verification_executions', ['risk_level'], unique=False)
        op.create_index(op.f('ix_verification_executions_created_at'), 'verification_executions', ['created_at'], unique=False)
        op.create_index('ix_verification_executions_tender_bidder', 'verification_executions', ['tender_id', 'bidder_id'], unique=False)

    # 2. verification_audit_events table
    if "verification_audit_events" not in table_names:
        op.create_table(
            'verification_audit_events',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('verification_id', sa.String(length=100), nullable=False),
            sa.Column('tender_id', sa.UUID(), nullable=False),
            sa.Column('bidder_id', sa.UUID(), nullable=False),
            sa.Column('event_type', sa.String(length=100), nullable=False),
            sa.Column('result_hash', sa.String(length=64), nullable=True),
            sa.Column('details', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['verification_id'], ['verification_executions.verification_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_verification_audit_events_verification_id'), 'verification_audit_events', ['verification_id'], unique=False)
        op.create_index(op.f('ix_verification_audit_events_tender_id'), 'verification_audit_events', ['tender_id'], unique=False)
        op.create_index(op.f('ix_verification_audit_events_bidder_id'), 'verification_audit_events', ['bidder_id'], unique=False)
        op.create_index(op.f('ix_verification_audit_events_event_type'), 'verification_audit_events', ['event_type'], unique=False)
        op.create_index(op.f('ix_verification_audit_events_created_at'), 'verification_audit_events', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema: Drop verification_audit_events and verification_executions tables."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = insp.get_table_names()

    if "verification_audit_events" in table_names:
        op.drop_table('verification_audit_events')

    if "verification_executions" in table_names:
        op.drop_table('verification_executions')
