"""modeles et promotions

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-23 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('model_versions',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('run_id', sa.String(length=64), nullable=True),
    sa.Column('source', sa.String(length=255), nullable=True),
    sa.Column('status', sa.Enum('candidate', 'production', 'previous', 'rejected', 'archived', name='model_version_status'), nullable=False),
    sa.Column('dataset_version', sa.String(length=40), nullable=True),
    sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('baseline_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('labels_count', sa.Integer(), nullable=True),
    sa.Column('promoted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_model_versions')),
    sa.UniqueConstraint('name', 'version', name='uq_model_versions_name_version')
    )
    op.create_table('model_promotions',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('model_version_id', sa.Uuid(), nullable=False),
    sa.Column('decision', sa.Enum('promoted', 'rejected', name='promotion_decision'), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('candidate_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('baseline_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('previous_version', sa.Integer(), nullable=True),
    sa.Column('decided_by', sa.String(length=60), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['model_version_id'], ['model_versions.id'], name=op.f('fk_model_promotions_model_version_id_model_versions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_model_promotions'))
    )
    op.create_index(op.f('ix_model_promotions_model_version_id'), 'model_promotions', ['model_version_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_model_promotions_model_version_id'), table_name='model_promotions')
    op.drop_table('model_promotions')
    op.drop_table('model_versions')
    sa.Enum(name='promotion_decision').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='model_version_status').drop(op.get_bind(), checkfirst=True)
