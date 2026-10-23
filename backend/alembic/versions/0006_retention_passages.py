"""retention des passages

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-23 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('passages', sa.Column('images_purged_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('passages', sa.Column('anonymized_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('passages', 'anonymized_at')
    op.drop_column('passages', 'images_purged_at')
