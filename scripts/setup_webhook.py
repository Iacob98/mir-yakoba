#!/usr/bin/env python3
"""Setup Telegram webhook."""
import asyncio
import sys

from aiogram import Bot

sys.path.insert(0, "/app")
from src.config import settings


async def setup_webhook():
    bot = Bot(token=settings.telegram_bot_token)

    # Delete any existing webhook
    await bot.delete_webhook()

    webhook_url = f"{settings.base_url}/webhook/telegram/{settings.telegram_webhook_secret}"
    print(f"Setting webhook to: {webhook_url}")

    result = await bot.set_webhook(
        url=webhook_url,
        allowed_updates=["message", "callback_query"],
    )

    if result:
        print("Webhook set successfully!")
    else:
        print("Failed to set webhook")

    info = await bot.get_webhook_info()
    print(f"Webhook info: {info}")

    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(setup_webhook())
