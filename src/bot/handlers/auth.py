from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.db.session import get_db_context
from src.services.auth import AuthService
from src.services.user import UserService


class NicknameChange(StatesGroup):
    waiting_for_nickname = State()

router = Router()


def get_reply_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Persistent reply keyboard at the bottom of the screen."""
    buttons = [
        [KeyboardButton(text="📋 Меню"), KeyboardButton(text="🔐 Войти на сайт")],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="📝 Новый пост")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Get main menu keyboard based on user role."""
    buttons = [
        [InlineKeyboardButton(text="⭐ Мой уровень", callback_data="menu_level")],
        [InlineKeyboardButton(text="✏️ Сменить ник", callback_data="menu_nickname")],
        [InlineKeyboardButton(text="🔐 Получить код входа", callback_data="menu_login")],
    ]
    if is_admin:
        buttons.insert(0, [InlineKeyboardButton(text="📝 Новый пост", callback_data="menu_newpost")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


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
            is_admin = existing_user.is_admin
            await message.answer(
                f"👋 С возвращением, <b>{user.full_name}</b>!",
                reply_markup=get_reply_keyboard(is_admin),
            )
            await message.answer(
                "📋 <b>Главное меню</b>",
                reply_markup=get_main_menu_keyboard(is_admin),
            )
        else:
            # Create new user
            new_user = await auth_service.create_user(
                telegram_id=user.id,
                username=user.username,
                display_name=user.full_name,
            )
            is_admin = new_user.is_admin if new_user else False
            await message.answer(
                f"🎉 Добро пожаловать, <b>{user.full_name}</b>!\n\n"
                f"Ваш аккаунт создан.",
                reply_markup=get_reply_keyboard(is_admin),
            )
            await message.answer(
                "📋 <b>Главное меню</b>",
                reply_markup=get_main_menu_keyboard(is_admin),
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
        "/start - Главное меню\n"
        "/menu - Показать меню\n"
        "/level - Мой уровень и XP\n"
        "/login - Получить код для входа на сайт\n"
        "/newpost - Создать новый пост (для админов)\n"
        "/cancel - Отменить текущее действие\n"
        "/help - Показать эту справку"
    )


def _format_level_message(user_db) -> str:
    """Format level info message for a user."""
    from src.services.level import XP_THRESHOLDS, XP_COMMENT, XP_REPLY, XP_DAILY_LOGIN

    xp = user_db.xp
    level = user_db.level
    max_level = len(XP_THRESHOLDS) - 1

    # Progress bar
    if level < max_level:
        current_th = XP_THRESHOLDS[level]
        next_th = XP_THRESHOLDS[level + 1]
        progress = (xp - current_th) / (next_th - current_th)
        filled = int(progress * 10)
        bar = "▓" * filled + "░" * (10 - filled)
        progress_text = f"{bar}  {xp}/{next_th} XP"
    else:
        bar = "▓" * 10
        progress_text = f"{bar}  {xp} XP (MAX)"

    # Achievements list
    achievements_text = ""
    if user_db.achievements:
        achs = sorted(user_db.achievements, key=lambda a: a.level)
        achievements_text = "\n\n🏆 <b>Достижения:</b>\n"
        for ach in achs:
            achievements_text += f"  • Lv.{ach.level} — {ach.title}\n"

    return (
        f"⭐ <b>Уровень {level}</b>\n"
        f"{progress_text}\n"
        f"{achievements_text}\n"
        f"── <b>Как получить XP</b> ──\n"
        f"💬 Комментарий: +{XP_COMMENT} XP\n"
        f"↩️ Ответ на комментарий: +{XP_REPLY} XP\n"
        f"📅 Ежедневный вход: +{XP_DAILY_LOGIN} XP\n\n"
        f"🎖 Достижения на уровнях: 1, 5, 10"
    )


@router.message(Command("level"))
async def cmd_level(message: Message):
    """Show user's level, XP progress and rules."""
    user = message.from_user

    async with get_db_context() as db:
        auth_service = AuthService(db)
        db_user = await auth_service.get_user_by_telegram_id(user.id)

        if not db_user:
            await message.answer("❌ Вы ещё не зарегистрированы. Нажмите /start")
            return

        await message.answer(_format_level_message(db_user))


# ============= REPLY KEYBOARD HANDLERS =============

@router.message(F.text == "📋 Меню")
async def reply_menu(message: Message):
    """Handle reply keyboard 'Menu' button."""
    user = message.from_user

    async with get_db_context() as db:
        auth_service = AuthService(db)
        existing_user = await auth_service.get_user_by_telegram_id(user.id)
        is_admin = existing_user.is_admin if existing_user else False

    await message.answer(
        "📋 <b>Главное меню</b>",
        reply_markup=get_main_menu_keyboard(is_admin),
    )


@router.message(F.text == "🔐 Войти на сайт")
async def reply_login(message: Message):
    """Handle reply keyboard 'Login' button."""
    user = message.from_user

    async with get_db_context() as db:
        auth_service = AuthService(db)
        existing_user = await auth_service.get_user_by_telegram_id(user.id)

        if not existing_user:
            existing_user = await auth_service.create_user(
                telegram_id=user.id,
                username=user.username,
                display_name=user.full_name,
            )

        code = await auth_service.create_auth_code(user.id)

        await message.answer(
            f"🔐 <b>Ваш код для входа:</b>\n\n"
            f"<code>{code}</code>\n\n"
            f"Введите этот код на сайте для входа.\n"
            f"Код действителен 5 минут."
        )


@router.message(F.text == "📝 Новый пост")
async def reply_newpost(message: Message, state: FSMContext):
    """Handle reply keyboard 'New post' button."""
    from src.bot.handlers.posts import PostCreation
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    user = message.from_user

    async with get_db_context() as db:
        auth_service = AuthService(db)
        db_user = await auth_service.get_user_by_telegram_id(user.id)

        if not db_user or not db_user.is_admin:
            await message.answer("❌ Только администраторы могут создавать посты.")
            return

    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Текстовый пост", callback_data="post_type_text")
    builder.button(text="📷 Фото/Видео пост", callback_data="post_type_photo")
    builder.button(text="🎤 Аудио/Видео пост", callback_data="post_type_voice")
    builder.adjust(1)

    await state.set_state(PostCreation.waiting_for_type)
    await message.answer(
        "📝 <b>Создание нового поста</b>\n\n"
        "Выберите тип поста:",
        reply_markup=builder.as_markup()
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Show main menu."""
    user = message.from_user

    async with get_db_context() as db:
        auth_service = AuthService(db)
        existing_user = await auth_service.get_user_by_telegram_id(user.id)
        is_admin = existing_user.is_admin if existing_user else False

    await message.answer(
        "📋 <b>Главное меню</b>",
        reply_markup=get_main_menu_keyboard(is_admin),
    )


@router.callback_query(F.data == "menu_login")
async def callback_menu_login(callback: CallbackQuery):
    """Handle login button from menu."""
    user = callback.from_user

    async with get_db_context() as db:
        auth_service = AuthService(db)

        existing_user = await auth_service.get_user_by_telegram_id(user.id)

        if not existing_user:
            existing_user = await auth_service.create_user(
                telegram_id=user.id,
                username=user.username,
                display_name=user.full_name,
            )

        code = await auth_service.create_auth_code(user.id)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="menu_back")]
        ])

        await callback.message.edit_text(
            f"🔐 <b>Ваш код для входа:</b>\n\n"
            f"<code>{code}</code>\n\n"
            f"Введите этот код на сайте для входа.\n"
            f"Код действителен 5 минут.",
            reply_markup=keyboard,
        )

    await callback.answer()


@router.callback_query(F.data == "menu_back")
async def callback_menu_back(callback: CallbackQuery):
    """Return to main menu."""
    user = callback.from_user

    async with get_db_context() as db:
        auth_service = AuthService(db)
        existing_user = await auth_service.get_user_by_telegram_id(user.id)
        is_admin = existing_user.is_admin if existing_user else False

    await callback.message.edit_text(
        "📋 <b>Главное меню</b>",
        reply_markup=get_main_menu_keyboard(is_admin),
    )
    await callback.answer()


@router.callback_query(F.data == "menu_newpost")
async def callback_menu_newpost(callback: CallbackQuery, state: FSMContext):
    """Handle new post button from menu - redirect to post creation flow."""
    from src.bot.handlers.posts import PostCreation
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    user = callback.from_user

    async with get_db_context() as db:
        auth_service = AuthService(db)
        db_user = await auth_service.get_user_by_telegram_id(user.id)

        if not db_user or not db_user.is_admin:
            await callback.answer("❌ Только администраторы могут создавать посты.", show_alert=True)
            return

    # Show post type selection
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Текстовый пост", callback_data="post_type_text")
    builder.button(text="🎤 Аудио/Видео пост", callback_data="post_type_voice")
    builder.button(text="◀️ Назад в меню", callback_data="menu_back_clear")
    builder.adjust(1)

    await state.set_state(PostCreation.waiting_for_type)
    await callback.message.edit_text(
        "📝 <b>Создание нового поста</b>\n\n"
        "Выберите тип поста:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "menu_back_clear")
async def callback_menu_back_clear(callback: CallbackQuery, state: FSMContext):
    """Return to main menu and clear state."""
    await state.clear()

    user = callback.from_user

    async with get_db_context() as db:
        auth_service = AuthService(db)
        existing_user = await auth_service.get_user_by_telegram_id(user.id)
        is_admin = existing_user.is_admin if existing_user else False

    await callback.message.edit_text(
        "📋 <b>Главное меню</b>",
        reply_markup=get_main_menu_keyboard(is_admin),
    )
    await callback.answer()


@router.callback_query(F.data == "menu_level")
async def callback_menu_level(callback: CallbackQuery):
    """Show level info from menu."""
    user = callback.from_user

    async with get_db_context() as db:
        auth_service = AuthService(db)
        db_user = await auth_service.get_user_by_telegram_id(user.id)

        if not db_user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="menu_back")]
        ])

        await callback.message.edit_text(
            _format_level_message(db_user),
            reply_markup=keyboard,
        )

    await callback.answer()


@router.callback_query(F.data == "menu_nickname")
async def callback_menu_nickname(callback: CallbackQuery, state: FSMContext):
    """Handle nickname change button from menu."""
    user = callback.from_user

    async with get_db_context() as db:
        auth_service = AuthService(db)
        existing_user = await auth_service.get_user_by_telegram_id(user.id)

        if not existing_user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="menu_back_clear")]
        ])

        await state.set_state(NicknameChange.waiting_for_nickname)
        await callback.message.edit_text(
            f"✏️ <b>Смена ника</b>\n\n"
            f"Текущий ник: <b>{existing_user.display_name}</b>\n\n"
            f"Введите новый ник:",
            reply_markup=keyboard,
        )

    await callback.answer()


@router.message(NicknameChange.waiting_for_nickname)
async def process_nickname_change(message: Message, state: FSMContext):
    """Process new nickname input."""
    user = message.from_user
    new_nickname = message.text.strip() if message.text else ""

    async with get_db_context() as db:
        auth_service = AuthService(db)
        user_service = UserService(db)

        existing_user = await auth_service.get_user_by_telegram_id(user.id)

        if not existing_user:
            await message.answer("❌ Пользователь не найден")
            await state.clear()
            return

        try:
            await user_service.update_display_name(existing_user.id, new_nickname)
            await state.clear()
            await message.answer(
                f"✅ Ник успешно изменён на <b>{new_nickname}</b>!",
                reply_markup=get_main_menu_keyboard(existing_user.is_admin),
            )
        except ValueError as e:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Отмена", callback_data="menu_back_clear")]
            ])
            await message.answer(
                f"❌ {str(e)}\n\nПопробуйте ещё раз:",
                reply_markup=keyboard,
            )
