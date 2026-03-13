"""Recalculate XP for all users based on existing comments.
Creates missing achievements and sends notifications via Telegram.

Run: docker compose exec app python scripts/recalc_xp.py
"""
import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select, func, update
from src.db.session import async_session_maker
from src.db.models.user import User
from src.db.models.comment import Comment
from src.db.models.achievement import Achievement
from src.services.level import (
    XP_COMMENT, XP_REPLY, calculate_level,
    MILESTONE_LEVELS, ACHIEVEMENT_TITLES, LevelService,
)
from src.services.achievement_image import generate_achievement_image


async def recalc():
    async with async_session_maker() as db:
        result = await db.execute(select(User))
        users = list(result.scalars().all())

        print(f"Found {len(users)} users")

        users_with_milestones = []

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

                # Check which milestones this user has reached
                reached = [m for m in MILESTONE_LEVELS if level >= m]
                if reached:
                    # Check which achievements already exist
                    r = await db.execute(
                        select(Achievement.level).where(Achievement.user_id == user.id)
                    )
                    existing = {row[0] for row in r.all()}
                    missing = [m for m in reached if m not in existing]

                    if missing:
                        users_with_milestones.append((user, missing))

        await db.commit()

        # Generate achievements for users who crossed milestones
        if users_with_milestones:
            print(f"\nGenerating {sum(len(m) for _, m in users_with_milestones)} missing achievements...")

            from src.bot.instance import bot

            for user, milestones in users_with_milestones:
                level_service = LevelService(db)
                comments = await level_service.get_user_recent_comments(user.id)

                for milestone in sorted(milestones):
                    title = ACHIEVEMENT_TITLES.get(milestone, f"Уровень {milestone}")
                    description = await level_service.generate_achievement_text(
                        user.display_name, milestone, comments
                    )

                    image_path = generate_achievement_image(
                        user_name=user.display_name,
                        level=milestone,
                        title=title,
                        description=description,
                    )

                    await level_service.create_achievement(
                        user_id=user.id,
                        level=milestone,
                        title=title,
                        description=description,
                        image_path=image_path,
                    )
                    print(f"  Created: {user.display_name} — {title}")

                    # Send via Telegram
                    try:
                        from aiogram.types import FSInputFile
                        from src.config import settings

                        file_path = settings.upload_dir / image_path
                        animation = FSInputFile(str(file_path))
                        caption = (
                            f"<b>{title}</b>\n\n"
                            f"{description}\n\n"
                            f"Уровень: {milestone} | XP: {user.xp}"
                        )
                        await bot.send_animation(
                            user.telegram_id,
                            animation=animation,
                            caption=caption,
                        )
                        print(f"  Sent to {user.display_name} ({user.telegram_id})")
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        print(f"  Failed to send to {user.display_name}: {e}")

            await bot.session.close()
        else:
            print("\nNo missing achievements.")

        print("\nDone!")


asyncio.run(recalc())
