import asyncio
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.bot import bot
from src.config import settings
from src.db.models.post import Post, PostVisibility
from src.db.models.user import AccessLevel, User

logger = logging.getLogger(__name__)


def get_required_access_level(visibility: PostVisibility) -> AccessLevel:
    """Map post visibility to minimum required access level."""
    mapping = {
        PostVisibility.PUBLIC: AccessLevel.PUBLIC,
        PostVisibility.REGISTERED: AccessLevel.REGISTERED,
        PostVisibility.PREMIUM_1: AccessLevel.PREMIUM_1,
        PostVisibility.PREMIUM_2: AccessLevel.PREMIUM_2,
    }
    return mapping.get(visibility, AccessLevel.PUBLIC)


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_users_for_notification(
        self, min_access_level: AccessLevel = AccessLevel.REGISTERED
    ) -> list[User]:
        """Get all active users with at least the specified access level."""
        result = await self.db.execute(
            select(User).where(
                User.is_active == True,
                User.access_level >= min_access_level,
            )
        )
        return list(result.scalars().all())

    async def notify_new_post(self, post: Post) -> int:
        """
        Send notification about new post to eligible users.
        Returns number of successfully sent notifications.
        """
        # Determine minimum access level based on post visibility
        min_level = get_required_access_level(post.visibility)

        # For public posts, notify all registered users
        if min_level == AccessLevel.PUBLIC:
            min_level = AccessLevel.REGISTERED

        users = await self.get_users_for_notification(min_level)

        if not users:
            logger.info("No users to notify for post %s", post.id)
            return 0

        # Build notification message
        post_url = f"{settings.base_url}/posts/{post.slug}"

        visibility_emoji = {
            PostVisibility.PUBLIC: "",
            PostVisibility.REGISTERED: "",
            PostVisibility.PREMIUM_1: " [Premium]",
            PostVisibility.PREMIUM_2: " [Premium+]",
        }

        message = (
            f"<b>Новый пост в Мире Якоба!</b>{visibility_emoji.get(post.visibility, '')}\n\n"
            f"<b>{post.title}</b>\n\n"
        )

        if post.excerpt:
            # Truncate excerpt if too long
            excerpt = post.excerpt[:200] + "..." if len(post.excerpt) > 200 else post.excerpt
            message += f"{excerpt}\n\n"

        message += f'<a href="{post_url}">Читать пост</a>'

        # Send notifications
        success_count = 0
        for user in users:
            try:
                await bot.send_message(user.telegram_id, message)
                success_count += 1
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.warning(
                    "Failed to send notification to user %s: %s",
                    user.telegram_id,
                    str(e)
                )

        logger.info(
            "Sent %d/%d notifications for post %s",
            success_count,
            len(users),
            post.id
        )
        return success_count


async def notify_post_published(db: AsyncSession, post: Post) -> int:
    """Helper function to notify about published post."""
    service = NotificationService(db)
    return await service.notify_new_post(post)
