"""One-time script to fix post_type enum state after failed migration.

Run: docker compose exec app python scripts/fix_enum.py
"""
import asyncio
from sqlalchemy import text
from src.db.session import async_engine


async def fix():
    async with async_engine.begin() as conn:
        # Check current enum values
        result = await conn.execute(text(
            "SELECT enumlabel FROM pg_enum "
            "JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
            "WHERE pg_type.typname = 'post_type' ORDER BY enumsortorder"
        ))
        current_values = [row[0] for row in result]
        print(f"Current post_type enum values: {current_values}")

        # Check current data
        result = await conn.execute(text("SELECT DISTINCT post_type::text FROM posts"))
        current_data = [row[0] for row in result]
        print(f"Current post_type data: {current_data}")

        # Fix: recreate enum properly
        print("Fixing enum...")
        await conn.execute(text("ALTER TABLE posts ALTER COLUMN post_type DROP DEFAULT"))
        await conn.execute(text("ALTER TABLE posts ALTER COLUMN post_type TYPE text USING post_type::text"))
        await conn.execute(text("DROP TYPE post_type"))

        await conn.execute(text("UPDATE posts SET post_type = UPPER(post_type)"))
        await conn.execute(text("UPDATE posts SET post_type = 'WORK' WHERE post_type = 'ARTWORK'"))

        await conn.execute(text("CREATE TYPE post_type AS ENUM ('ARTICLE', 'PHOTO', 'WORK')"))
        await conn.execute(text("ALTER TABLE posts ALTER COLUMN post_type TYPE post_type USING post_type::post_type"))
        await conn.execute(text("ALTER TABLE posts ALTER COLUMN post_type SET DEFAULT 'ARTICLE'"))

        # Fix media_type
        try:
            await conn.execute(text("ALTER TYPE media_type ADD VALUE IF NOT EXISTS 'DOCUMENT'"))
            print("Added DOCUMENT to media_type")
        except Exception as e:
            print(f"media_type DOCUMENT: {e}")

        # Stamp alembic
        await conn.execute(text("UPDATE alembic_version SET version_num = 'add_photo_work_document'"))

        print("Done! Enum fixed and alembic stamped.")

        # Verify
        result = await conn.execute(text(
            "SELECT enumlabel FROM pg_enum "
            "JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
            "WHERE pg_type.typname = 'post_type' ORDER BY enumsortorder"
        ))
        print(f"New post_type enum values: {[row[0] for row in result]}")


asyncio.run(fix())
