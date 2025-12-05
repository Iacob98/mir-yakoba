"""add site_settings and post pinning

Revision ID: 0177d568136b
Revises: 66811f4fa88b
Create Date: 2025-12-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0177d568136b'
down_revision: Union[str, None] = '66811f4fa88b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create site_settings table
    op.create_table(
        'site_settings',
        sa.Column('key', sa.String(64), primary_key=True),
        sa.Column('value', sa.Text(), nullable=True),
    )

    # Add pinning columns to posts
    op.add_column('posts', sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('posts', sa.Column('pinned_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove pinning columns from posts
    op.drop_column('posts', 'pinned_at')
    op.drop_column('posts', 'is_pinned')

    # Drop site_settings table
    op.drop_table('site_settings')
