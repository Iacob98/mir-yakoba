#!/usr/bin/env python3
"""Run bot in polling mode for local development."""
import asyncio
import logging
import signal
import sys

sys.path.insert(0, "/app")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from src.config import settings


async def main():
    # Import and configure bot
    from aiogram import Bot, Dispatcher
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.fsm.storage.redis import RedisStorage

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Use Redis storage for FSM to persist state across restarts
    # Set TTL to 1 hour so users have time to write long posts
    storage = RedisStorage.from_url(
        settings.redis_url,
        state_ttl=3600,  # 1 hour
        data_ttl=3600,   # 1 hour
    )
    dp = Dispatcher(storage=storage)

    # Import and include handlers
    from src.bot.handlers.auth import router as auth_router
    from src.bot.handlers.posts import router as posts_router
    from aiogram import Router
    from aiogram.types import Update

    logger = logging.getLogger(__name__)

    # Debug middleware to log all updates
    @dp.update.outer_middleware()
    async def debug_middleware(handler, event: Update, data):
        state = data.get("state")
        current_state = await state.get_state() if state else None
        user_id = None
        content_type = None

        if event.message:
            user_id = event.message.from_user.id
            content_type = event.message.content_type
        elif event.callback_query:
            user_id = event.callback_query.from_user.id
            content_type = "callback_query"

        logger.info(f"UPDATE: user={user_id}, type={content_type}, state={current_state}")
        return await handler(event, data)

    main_router = Router()
    main_router.include_router(auth_router)
    main_router.include_router(posts_router)
    dp.include_router(main_router)

    # Handle shutdown gracefully
    def handle_signal(sig, frame):
        print("Received SIGTERM signal")
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, handle_signal)

    # Delete webhook first (required for polling)
    await bot.delete_webhook(drop_pending_updates=True)

    print("Starting bot in polling mode...")
    print("Press Ctrl+C to stop")

    try:
        await dp.start_polling(bot, polling_timeout=30)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
