"""add cover image to posts

Revision ID: add_cover_image
Revises: 0177d568136b
Create Date: 2025-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_cover_image'
down_revision: Union[str, None] = '0177d568136b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('posts', sa.Column('cover_image_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_posts_cover_image_id',
        'posts', 'media',
        ['cover_image_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_posts_cover_image_id', 'posts', type_='foreignkey')
    op.drop_column('posts', 'cover_image_id')
