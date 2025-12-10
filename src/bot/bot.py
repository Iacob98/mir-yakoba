from aiogram import Bot, Dispatcher, Router
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

# Create dispatcher
dp = Dispatcher()

# Create main router
main_router = Router()

# Import and include handlers
from src.bot.handlers.auth import router as auth_router
from src.bot.handlers.posts import router as posts_router

main_router.include_router(auth_router)
main_router.include_router(posts_router)

dp.include_router(main_router)


async def send_auth_code(telegram_id: int, code: str) -> bool:
    """Send auth code to user via Telegram."""
    try:
        await bot.send_message(
            telegram_id,
            f"🔐 <b>Your login code:</b>\n\n"
            f"<code>{code}</code>\n\n"
            f"This code expires in {settings.auth_code_expire_minutes} minutes.\n"
            f"Don't share it with anyone!",
            parse_mode=ParseMode.HTML,
        )
        return True
    except Exception:
        return False


async def notify_user(telegram_id: int, message: str) -> bool:
    """Send notification to user."""
    try:
        await bot.send_message(telegram_id, message, parse_mode=ParseMode.HTML)
        return True
    except Exception:
        return False
