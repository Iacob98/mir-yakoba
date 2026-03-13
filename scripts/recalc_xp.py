"""Recalculate XP for all users based on existing comments.

Run: docker compose exec app python scripts/recalc_xp.py
"""
import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select, func, update
from src.db.session import async_session_maker
from src.db.models.user import User
from src.db.models.comment import Comment
from src.services.level import XP_COMMENT, XP_REPLY, calculate_level


async def recalc():
    async with async_session_maker() as db:
        # Get all users
        result = await db.execute(select(User))
        users = list(result.scalars().all())

        print(f"Found {len(users)} users")

        for user in users:
            # Count top-level comments
            r = await db.execute(
                select(func.count()).select_from(Comment).where(
                    Comment.author_id == user.id,
                    Comment.parent_id.is_(None),
                )
            )
            comments_count = r.scalar() or 0

            # Count replies
            r = await db.execute(
                select(func.count()).select_from(Comment).where(
                    Comment.author_id == user.id,
                    Comment.parent_id.is_not(None),
                )
            )
            replies_count = r.scalar() or 0

            total_xp = (comments_count * XP_COMMENT) + (replies_count * XP_REPLY)
            level = calculate_level(total_xp)

            if total_xp > 0:
                await db.execute(
                    update(User).where(User.id == user.id).values(xp=total_xp, level=level)
                )
                print(f"  {user.display_name}: {comments_count} comments + {replies_count} replies = {total_xp} XP (Lv.{level})")

        await db.commit()
        print("\nDone!")


asyncio.run(recalc())
