"""phase09_compliance_engine_tables

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-01 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'g7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Create requirements, bidder_evidence, and compliance_results tables."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = insp.get_table_names()

    # 1. requirements table
    if "requirements" not in table_names:
        op.create_table(
            'requirements',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('requirement_id', sa.UUID(), nullable=False),
            sa.Column('tender_id', sa.UUID(), nullable=False),
            sa.Column('category', sa.String(length=100), nullable=False),
            sa.Column('field', sa.String(length=200), nullable=False),
            sa.Column('rule_type', sa.String(length=50), nullable=False),
            sa.Column(
                'rule_definition',
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=False,
            ),
            sa.Column('mandatory', sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_requirements_requirement_id'), 'requirements', ['requirement_id'], unique=False)
        op.create_index(op.f('ix_requirements_tender_id'), 'requirements', ['tender_id'], unique=False)
        op.create_index(op.f('ix_requirements_category'), 'requirements', ['category'], unique=False)
        op.create_index(op.f('ix_requirements_field'), 'requirements', ['field'], unique=False)
        op.create_index(op.f('ix_requirements_rule_type'), 'requirements', ['rule_type'], unique=False)
        op.create_index('ix_requirements_tender_category', 'requirements', ['tender_id', 'category'], unique=False)

    # 2. bidder_evidence table
    if "bidder_evidence" not in table_names:
        op.create_table(
            'bidder_evidence',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('evidence_id', sa.UUID(), nullable=False),
            sa.Column('bidder_id', sa.UUID(), nullable=False),
            sa.Column('field', sa.String(length=200), nullable=False),
            sa.Column(
                'value',
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column('source_document', sa.String(length=500), nullable=True),
            sa.Column('confidence', sa.Float(), nullable=False, server_default=sa.text("1.0")),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['bidder_id'], ['bidders.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.CheckConstraint('confidence >= 0.0 AND confidence <= 1.0', name='check_bidder_evidence_confidence_range'),
        )
        op.create_index(op.f('ix_bidder_evidence_evidence_id'), 'bidder_evidence', ['evidence_id'], unique=False)
        op.create_index(op.f('ix_bidder_evidence_bidder_id'), 'bidder_evidence', ['bidder_id'], unique=False)
        op.create_index(op.f('ix_bidder_evidence_field'), 'bidder_evidence', ['field'], unique=False)
        op.create_index('ix_bidder_evidence_bidder_field', 'bidder_evidence', ['bidder_id', 'field'], unique=False)

    # 3. compliance_results table
    if "compliance_results" not in table_names:
        op.create_table(
            'compliance_results',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('requirement_id', sa.UUID(), nullable=False),
            sa.Column('bidder_id', sa.UUID(), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('reason', sa.Text(), nullable=False),
            sa.Column('evidence_reference', sa.String(length=500), nullable=True),
            sa.Column('rule_type', sa.String(length=50), nullable=True),
            sa.Column('operator_used', sa.String(length=50), nullable=True),
            sa.Column(
                'actual_value',
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column(
                'required_value',
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            ),
            sa.Column('evaluated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['requirement_id'], ['requirements.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['bidder_id'], ['bidders.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_compliance_results_requirement_id'), 'compliance_results', ['requirement_id'], unique=False)
        op.create_index(op.f('ix_compliance_results_bidder_id'), 'compliance_results', ['bidder_id'], unique=False)
        op.create_index(op.f('ix_compliance_results_status'), 'compliance_results', ['status'], unique=False)
        op.create_index('ix_compliance_results_bidder_req', 'compliance_results', ['bidder_id', 'requirement_id'], unique=False)
        op.create_index('ix_compliance_results_evaluated_at', 'compliance_results', ['evaluated_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema: Drop compliance_results, bidder_evidence, requirements tables."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = insp.get_table_names()

    if "compliance_results" in table_names:
        op.drop_index('ix_compliance_results_evaluated_at', table_name='compliance_results')
        op.drop_index('ix_compliance_results_bidder_req', table_name='compliance_results')
        op.drop_index(op.f('ix_compliance_results_status'), table_name='compliance_results')
        op.drop_index(op.f('ix_compliance_results_bidder_id'), table_name='compliance_results')
        op.drop_index(op.f('ix_compliance_results_requirement_id'), table_name='compliance_results')
        op.drop_table('compliance_results')

    if "bidder_evidence" in table_names:
        op.drop_index('ix_bidder_evidence_bidder_field', table_name='bidder_evidence')
        op.drop_index(op.f('ix_bidder_evidence_field'), table_name='bidder_evidence')
        op.drop_index(op.f('ix_bidder_evidence_bidder_id'), table_name='bidder_evidence')
        op.drop_index(op.f('ix_bidder_evidence_evidence_id'), table_name='bidder_evidence')
        op.drop_table('bidder_evidence')

    if "requirements" in table_names:
        op.drop_index('ix_requirements_tender_category', table_name='requirements')
        op.drop_index(op.f('ix_requirements_rule_type'), table_name='requirements')
        op.drop_index(op.f('ix_requirements_field'), table_name='requirements')
        op.drop_index(op.f('ix_requirements_category'), table_name='requirements')
        op.drop_index(op.f('ix_requirements_tender_id'), table_name='requirements')
        op.drop_index(op.f('ix_requirements_requirement_id'), table_name='requirements')
        op.drop_table('requirements')
