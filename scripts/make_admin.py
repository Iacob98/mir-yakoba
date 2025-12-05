#!/usr/bin/env python3
"""Make a user admin by Telegram ID."""
import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select, update
from src.db.session import async_session_maker
from src.db.models.user import User


async def make_admin(telegram_id: int):
    async with async_session_maker() as db:
        # Check if user exists
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            print(f"User with telegram_id {telegram_id} not found.")
            print("The user needs to start the bot first with /start")
            return

        # Make admin
        user.is_admin = True
        await db.commit()

        print(f"User {user.display_name} (telegram_id: {telegram_id}) is now an admin!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python make_admin.py <telegram_id>")
        sys.exit(1)

    telegram_id = int(sys.argv[1])
    asyncio.run(make_admin(telegram_id))
