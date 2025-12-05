from fastapi import APIRouter, Request, HTTPException

from src.bot.bot import bot, dp
from src.config import settings

router = APIRouter()


@router.post("/webhook/telegram/{secret}")
async def telegram_webhook(secret: str, request: Request):
    """Handle Telegram webhook updates."""
    # Verify secret
    if settings.telegram_webhook_secret and secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    # Get update data
    update_data = await request.json()

    # Process update
    from aiogram.types import Update

    update = Update.model_validate(update_data, context={"bot": bot})
    await dp.feed_update(bot, update)

    return {"ok": True}
