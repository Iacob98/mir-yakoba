"""Bot instance - separated to avoid circular imports."""

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode

from src.config import settings

# Create session for local API server if configured
session = None
if settings.telegram_api_server:
    api = TelegramAPIServer.from_base(settings.telegram_api_server, is_local=True)
    session = AiohttpSession(api=api)

# Create bot instance
bot = Bot(
    token=settings.telegram_bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    session=session,
)
