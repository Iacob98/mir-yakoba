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
    # Recreate post_type enum: old (ARTICLE, ARTWORK) → new (ARTICLE, PHOTO, WORK)
    # SQLAlchemy uses enum member .name (uppercase) as DB values.

    # 1. Convert column to text
    op.execute("ALTER TABLE posts ALTER COLUMN post_type DROP DEFAULT")
    op.execute("ALTER TABLE posts ALTER COLUMN post_type TYPE text USING post_type::text")
    op.execute("DROP TYPE post_type")

    # 2. Normalize: ensure uppercase + rename ARTWORK → WORK
    op.execute("UPDATE posts SET post_type = UPPER(post_type)")
    op.execute("UPDATE posts SET post_type = 'WORK' WHERE post_type = 'ARTWORK'")

    # 3. Create new enum
    op.execute("CREATE TYPE post_type AS ENUM ('ARTICLE', 'PHOTO', 'WORK')")

    # 4. Convert back
    op.execute("ALTER TABLE posts ALTER COLUMN post_type TYPE post_type USING post_type::post_type")
    op.execute("ALTER TABLE posts ALTER COLUMN post_type SET DEFAULT 'ARTICLE'")

    # 5. Add DOCUMENT to media_type enum
    op.execute("ALTER TYPE media_type ADD VALUE IF NOT EXISTS 'DOCUMENT'")


def downgrade() -> None:
    op.execute("ALTER TABLE posts ALTER COLUMN post_type DROP DEFAULT")
    op.execute("ALTER TABLE posts ALTER COLUMN post_type TYPE text USING post_type::text")
    op.execute("DROP TYPE post_type")

    op.execute("UPDATE posts SET post_type = 'ARTWORK' WHERE post_type = 'WORK'")
    op.execute("UPDATE posts SET post_type = 'ARTICLE' WHERE post_type = 'PHOTO'")

    op.execute("CREATE TYPE post_type AS ENUM ('ARTICLE', 'ARTWORK')")
    op.execute("ALTER TABLE posts ALTER COLUMN post_type TYPE post_type USING post_type::post_type")
    op.execute("ALTER TABLE posts ALTER COLUMN post_type SET DEFAULT 'ARTICLE'")
