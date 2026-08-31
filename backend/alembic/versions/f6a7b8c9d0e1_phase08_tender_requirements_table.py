"""phase08_tender_requirements_table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-01 00:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Create tender_requirements table with JSONB parameters, constraints, and indexes."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "tender_requirements" not in insp.get_table_names():
        op.create_table(
            'tender_requirements',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('tender_id', sa.UUID(), nullable=False),
            sa.Column('requirement_type', sa.String(length=50), nullable=False),
            sa.Column('rule', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column(
                'parameters',
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=False,
            ),
            sa.Column('mandatory', sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column('confidence', sa.Float(), nullable=False, server_default=sa.text("1.0")),
            sa.Column('source_page', sa.Integer(), nullable=True),
            sa.Column('source_section', sa.String(length=255), nullable=True),
            sa.Column('source_text', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.CheckConstraint('confidence >= 0.0 AND confidence <= 1.0', name='check_tender_requirement_confidence_range'),
        )

        op.create_index(op.f('ix_tender_requirements_tender_id'), 'tender_requirements', ['tender_id'], unique=False)
        op.create_index(op.f('ix_tender_requirements_requirement_type'), 'tender_requirements', ['requirement_type'], unique=False)
        op.create_index(op.f('ix_tender_requirements_rule'), 'tender_requirements', ['rule'], unique=False)
        op.create_index('ix_tender_requirements_tender_type', 'tender_requirements', ['tender_id', 'requirement_type'], unique=False)


def downgrade() -> None:
    """Downgrade schema: Drop tender_requirements table and indexes."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "tender_requirements" in insp.get_table_names():
        op.drop_index('ix_tender_requirements_tender_type', table_name='tender_requirements')
        op.drop_index(op.f('ix_tender_requirements_rule'), table_name='tender_requirements')
        op.drop_index(op.f('ix_tender_requirements_requirement_type'), table_name='tender_requirements')
        op.drop_index(op.f('ix_tender_requirements_tender_id'), table_name='tender_requirements')
        op.drop_table('tender_requirements')
