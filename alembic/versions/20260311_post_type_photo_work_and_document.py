"""add photo/work post types and document media type

Revision ID: add_photo_work_document
Revises: add_post_type
Create Date: 2026-03-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_photo_work_document'
down_revision: Union[str, None] = 'add_post_type'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new values to post_type enum
    op.execute("ALTER TYPE post_type ADD VALUE IF NOT EXISTS 'photo'")
    op.execute("ALTER TYPE post_type ADD VALUE IF NOT EXISTS 'work'")

    # Migrate existing artwork → work
    op.execute("UPDATE posts SET post_type = 'work' WHERE post_type = 'artwork'")

    # Add document to media_type enum
    op.execute("ALTER TYPE media_type ADD VALUE IF NOT EXISTS 'document'")


def downgrade() -> None:
    # Migrate work → artwork
    op.execute("UPDATE posts SET post_type = 'artwork' WHERE post_type = 'work'")
    # Migrate photo → article
    op.execute("UPDATE posts SET post_type = 'article' WHERE post_type = 'photo'")
    # Note: PostgreSQL doesn't support removing values from enum types
    # A full enum recreation would be needed for a complete downgrade
