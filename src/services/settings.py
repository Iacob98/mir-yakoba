from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.settings import SiteSettings


# Default settings values
DEFAULTS = {
    "hero_title": "Добро пожаловать в Мир Якоба",
    "hero_subtitle": "Одно место для всех моих фото, видео, мыслей и историй — без алгоритмов и цензуры.",
    "avatar_path": "avatar.jpg",
}


class SettingsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a setting value by key."""
        result = await self.db.execute(
            select(SiteSettings).where(SiteSettings.key == key)
        )
        setting = result.scalar_one_or_none()
        if setting:
            return setting.value
        # Return from defaults if not in DB
        return DEFAULTS.get(key, default)

    async def set(self, key: str, value: str) -> None:
        """Set a setting value."""
        result = await self.db.execute(
            select(SiteSettings).where(SiteSettings.key == key)
        )
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            setting = SiteSettings(key=key, value=value)
            self.db.add(setting)
        await self.db.commit()

    async def get_all(self) -> dict[str, str]:
        """Get all settings as a dictionary."""
        result = await self.db.execute(select(SiteSettings))
        settings = {s.key: s.value for s in result.scalars().all()}
        # Fill in defaults for missing keys
        for key, default_value in DEFAULTS.items():
            if key not in settings:
                settings[key] = default_value
        return settings

    async def get_hero_settings(self) -> dict[str, str]:
        """Get hero section settings for the home page."""
        return {
            "title": await self.get("hero_title"),
            "subtitle": await self.get("hero_subtitle"),
            "avatar": await self.get("avatar_path"),
        }
