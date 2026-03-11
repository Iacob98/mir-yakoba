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
    # The old migration created post_type enum with UPPERCASE values (ARTICLE, ARTWORK).
    # Our models use lowercase. Recreate enum with correct lowercase values.

    # 1. Convert column to text temporarily
    op.execute("ALTER TABLE posts ALTER COLUMN post_type DROP DEFAULT")
    op.execute("ALTER TABLE posts ALTER COLUMN post_type TYPE text USING post_type::text")
    op.execute("DROP TYPE post_type")

    # 2. Normalize existing data to lowercase
    op.execute("UPDATE posts SET post_type = LOWER(post_type)")

    # 3. Migrate artwork → work
    op.execute("UPDATE posts SET post_type = 'work' WHERE post_type = 'artwork'")

    # 4. Create new enum with correct values
    op.execute("CREATE TYPE post_type AS ENUM ('article', 'photo', 'work')")

    # 5. Convert column back to enum
    op.execute("ALTER TABLE posts ALTER COLUMN post_type TYPE post_type USING post_type::post_type")
    op.execute("ALTER TABLE posts ALTER COLUMN post_type SET DEFAULT 'article'")

    # Add document to media_type enum
    op.execute("ALTER TYPE media_type ADD VALUE IF NOT EXISTS 'document'")


def downgrade() -> None:
    # Convert column to text, recreate old enum
    op.execute("ALTER TABLE posts ALTER COLUMN post_type DROP DEFAULT")
    op.execute("ALTER TABLE posts ALTER COLUMN post_type TYPE text USING post_type::text")
    op.execute("DROP TYPE post_type")

    op.execute("UPDATE posts SET post_type = 'artwork' WHERE post_type = 'work'")
    op.execute("UPDATE posts SET post_type = 'article' WHERE post_type = 'photo'")

    op.execute("CREATE TYPE post_type AS ENUM ('ARTICLE', 'ARTWORK')")
    op.execute("ALTER TABLE posts ALTER COLUMN post_type TYPE post_type USING UPPER(post_type)::post_type")
    op.execute("ALTER TABLE posts ALTER COLUMN post_type SET DEFAULT 'ARTICLE'")
