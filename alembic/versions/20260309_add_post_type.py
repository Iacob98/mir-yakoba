"""add post_type to posts

Revision ID: add_post_type
Revises: add_cover_image
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_post_type'
down_revision: Union[str, None] = 'add_cover_image'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the enum type
    post_type_enum = sa.Enum('ARTICLE', 'ARTWORK', name='post_type')
    post_type_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        'posts',
        sa.Column(
            'post_type',
            sa.Enum('ARTICLE', 'ARTWORK', name='post_type'),
            nullable=False,
            server_default='ARTICLE',
        ),
    )


def downgrade() -> None:
    op.drop_column('posts', 'post_type')
    sa.Enum(name='post_type').drop(op.get_bind(), checkfirst=True)
