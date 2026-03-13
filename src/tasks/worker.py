"""ARQ worker settings and tasks."""

import logging
from arq.connections import RedisSettings

from src.config import settings

logger = logging.getLogger(__name__)


async def ping(ctx: dict) -> str:
    """Health check task."""
    return "pong"


async def process_achievement(ctx: dict, user_id: str, milestone_level: int) -> None:
    """Generate achievement image + personalized text and send via Telegram."""
    from uuid import UUID

    from src.db.session import async_session_maker
    from src.services.level import LevelService, ACHIEVEMENT_TITLES
    from src.services.achievement_image import generate_achievement_image
    from src.bot.instance import bot

    logger.info(f"Processing achievement for user {user_id}, level {milestone_level}")

    async with async_session_maker() as db:
        level_service = LevelService(db)

        # Get user
        from sqlalchemy import select
        from src.db.models.user import User
        result = await db.execute(select(User).where(User.id == UUID(user_id)))
        user = result.scalar_one_or_none()
        if not user:
            logger.error(f"User {user_id} not found")
            return

        # Get user's recent comments for style analysis
        comments = await level_service.get_user_recent_comments(user.id)

        # Generate personalized text
        title = ACHIEVEMENT_TITLES.get(milestone_level, f"Уровень {milestone_level}")
        description = await level_service.generate_achievement_text(
            user.display_name, milestone_level, comments
        )

        # Generate image
        image_path = generate_achievement_image(
            user_name=user.display_name,
            level=milestone_level,
            title=title,
            description=description,
        )

        # Save achievement to DB
        await level_service.create_achievement(
            user_id=user.id,
            level=milestone_level,
            title=title,
            description=description,
            image_path=image_path,
        )

        # Send via Telegram
        try:
            from aiogram.types import FSInputFile
            file_path = settings.upload_dir / image_path
            animation = FSInputFile(str(file_path))

            caption = (
                f"<b>{title}</b>\n\n"
                f"{description}\n\n"
                f"Уровень: {milestone_level} | XP: {user.xp}"
            )

            await bot.send_animation(
                user.telegram_id,
                animation=animation,
                caption=caption,
            )
            logger.info(f"Achievement notification sent to {user.telegram_id}")
        except Exception as e:
            logger.error(f"Failed to send achievement to {user.telegram_id}: {e}")


async def startup(ctx: dict) -> None:
    """Initialize worker context on startup."""
    logger.info("Worker started")


async def shutdown(ctx: dict) -> None:
    """Cleanup on worker shutdown."""
    logger.info("Worker shutting down")


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [ping, process_achievement]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 300  # 5 minutes
