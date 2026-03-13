"""User level/XP system with achievement generation."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models.achievement import Achievement
from src.db.models.comment import Comment
from src.db.models.user import User

logger = logging.getLogger(__name__)

# XP thresholds per level (index = level)
XP_THRESHOLDS = [0, 50, 150, 300, 500, 800, 1200, 1700, 2300, 3000, 4000]

# Milestone levels that trigger achievements
MILESTONE_LEVELS = {1, 5, 10}

# XP rewards
XP_COMMENT = 10
XP_REPLY = 15
XP_DAILY_LOGIN = 5

CHAT_API_URL = "https://api.openai.com/v1/chat/completions"

ACHIEVEMENT_TEXT_PROMPT = """Ты генерируешь короткий персонализированный текст для достижения пользователя на блог-платформе.

Пользователь достиг уровня {level}. Его имя: {name}.

Вот примеры его последних комментариев (стиль общения):
{comments}

Напиши короткий текст (2-3 предложения) поздравления с достижением уровня.
Текст должен:
- Отражать стиль общения пользователя (если он шутит - пошути, если серьёзный - будь серьёзным)
- Упоминать уровень
- Быть тёплым и мотивирующим
- Не быть шаблонным

Верни ТОЛЬКО текст поздравления, без кавычек и пояснений."""

ACHIEVEMENT_TITLES = {
    1: "Первый шаг",
    5: "Активный участник",
    10: "Легенда сообщества",
}


def calculate_level(xp: int) -> int:
    """Calculate level from XP amount."""
    for level in range(len(XP_THRESHOLDS) - 1, -1, -1):
        if xp >= XP_THRESHOLDS[level]:
            return level
    return 0


def xp_for_next_level(current_level: int) -> Optional[int]:
    """Get XP needed for next level. None if max level."""
    next_level = current_level + 1
    if next_level >= len(XP_THRESHOLDS):
        return None
    return XP_THRESHOLDS[next_level]


class LevelService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_xp(self, user_id: UUID, amount: int) -> tuple[int, int, Optional[int]]:
        """
        Add XP to user atomically. Returns (new_xp, new_level, milestone_level or None).
        milestone_level is set if the user crossed a milestone.
        """
        # Atomic increment
        result = await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(xp=User.xp + amount)
            .returning(User.xp, User.level)
        )
        row = result.one()
        new_xp, old_level = row[0], row[1]

        new_level = calculate_level(new_xp)

        milestone = None
        if new_level > old_level:
            # Update level
            await self.db.execute(
                update(User).where(User.id == user_id).values(level=new_level)
            )
            # Check if any milestone was crossed
            for lvl in range(old_level + 1, new_level + 1):
                if lvl in MILESTONE_LEVELS:
                    milestone = lvl

        await self.db.commit()
        return new_xp, new_level, milestone

    async def award_daily_xp(self, user_id: UUID) -> bool:
        """Award daily login XP. Returns True if awarded (not already claimed today)."""
        result = await self.db.execute(
            select(User.last_daily_xp).where(User.id == user_id)
        )
        last_daily = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if last_daily and last_daily.date() == now.date():
            return False

        await self.db.execute(
            update(User).where(User.id == user_id).values(last_daily_xp=now)
        )
        await self.add_xp(user_id, XP_DAILY_LOGIN)
        return True

    async def get_user_recent_comments(self, user_id: UUID, limit: int = 20) -> list[str]:
        """Get user's recent comment texts for style analysis."""
        result = await self.db.execute(
            select(Comment.content)
            .where(Comment.author_id == user_id, Comment.is_approved == True)
            .order_by(Comment.created_at.desc())
            .limit(limit)
        )
        return [row[0] for row in result.all()]

    async def generate_achievement_text(
        self, user_name: str, level: int, comments: list[str]
    ) -> str:
        """Generate personalized achievement text using OpenAI."""
        if not settings.openai_api_key:
            return f"Поздравляем, {user_name}! Вы достигли уровня {level}!"

        comments_text = "\n".join(f"- {c[:100]}" for c in comments[:10]) or "- (нет комментариев)"

        prompt = ACHIEVEMENT_TEXT_PROMPT.format(
            level=level, name=user_name, comments=comments_text
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    CHAT_API_URL,
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": prompt},
                        ],
                        "temperature": 0.8,
                        "max_tokens": 300,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Failed to generate achievement text: {e}")
            return f"Поздравляем, {user_name}! Вы достигли уровня {level}!"

    async def create_achievement(
        self, user_id: UUID, level: int, title: str, description: str, image_path: Optional[str] = None
    ) -> Achievement:
        """Create achievement record."""
        achievement = Achievement(
            user_id=user_id,
            level=level,
            title=title,
            description=description,
            image_path=image_path,
        )
        self.db.add(achievement)
        await self.db.commit()
        await self.db.refresh(achievement)
        return achievement
