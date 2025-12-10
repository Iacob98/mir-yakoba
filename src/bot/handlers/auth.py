from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from src.db.session import get_db_context
from src.services.auth import AuthService

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command."""
    user = message.from_user

    async with get_db_context() as db:
        auth_service = AuthService(db)

        # Check if user exists
        existing_user = await auth_service.get_user_by_telegram_id(user.id)

        if existing_user:
            await auth_service.update_user_info(
                existing_user,
                username=user.username,
                display_name=user.full_name,
            )
            await message.answer(
                f"👋 С возвращением, <b>{user.full_name}</b>!\n\n"
                f"Используйте /login для получения кода входа на сайт.\n"
                f"Используйте /newpost для создания нового поста (только для админов)."
            )
        else:
            # Create new user
            await auth_service.create_user(
                telegram_id=user.id,
                username=user.username,
                display_name=user.full_name,
            )
            await message.answer(
                f"🎉 Добро пожаловать, <b>{user.full_name}</b>!\n\n"
                f"Ваш аккаунт создан.\n\n"
                f"Используйте /login для получения кода входа на сайт.\n"
                f"Используйте /newpost для создания нового поста (только для админов)."
            )


@router.message(Command("login"))
async def cmd_login(message: Message):
    """Handle /login command - generate auth code."""
    user = message.from_user

    async with get_db_context() as db:
        auth_service = AuthService(db)

        # Check if user exists
        existing_user = await auth_service.get_user_by_telegram_id(user.id)

        if not existing_user:
            # Create user first
            existing_user = await auth_service.create_user(
                telegram_id=user.id,
                username=user.username,
                display_name=user.full_name,
            )

        # Generate auth code
        code = await auth_service.create_auth_code(user.id)

        await message.answer(
            f"🔐 <b>Ваш код для входа:</b>\n\n"
            f"<code>{code}</code>\n\n"
            f"Введите этот код на сайте для входа.\n"
            f"Код действителен 5 минут."
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    await message.answer(
        "📚 <b>Доступные команды:</b>\n\n"
        "/start - Запустить бота\n"
        "/login - Получить код для входа на сайт\n"
        "/newpost - Создать новый пост (для админов)\n"
        "/testnotify - Тестовое уведомление (для админов)\n"
        "/cancel - Отменить текущее действие\n"
        "/help - Показать эту справку"
    )


@router.message(Command("testnotify"))
async def cmd_test_notify(message: Message):
    """Handle /testnotify command - send test notification (admin only)."""
    user = message.from_user

    async with get_db_context() as db:
        auth_service = AuthService(db)
        existing_user = await auth_service.get_user_by_telegram_id(user.id)

        if not existing_user or not existing_user.is_admin:
            await message.answer("❌ Эта команда доступна только администраторам.")
            return

    # Send test notification that looks like a real post notification
    test_message = (
        "<b>Новый пост в Мире Якоба!</b>\n\n"
        "<b>Пример заголовка поста</b>\n\n"
        "Это тестовое уведомление, которое показывает как будет "
        "выглядеть уведомление о новом посте для пользователей."
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Читать пост", url="https://google.com")]
    ])

    await message.answer(
        test_message,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )
