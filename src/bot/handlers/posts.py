import io
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.db.session import get_db_context
from src.services.auth import AuthService

logger = logging.getLogger(__name__)
router = Router()


class PostCreation(StatesGroup):
    waiting_for_type = State()          # выбор типа поста (текст/аудио/фото)
    waiting_for_title = State()
    waiting_for_content = State()       # Текст или голосовое/кружочек
    confirm_save_audio = State()        # подтверждение сохранения аудио
    waiting_for_visibility = State()
    waiting_for_media = State()
    waiting_for_publish_choice = State()  # Черновик или опубликовать


@router.message(Command("newpost"))
async def cmd_newpost(message: Message, state: FSMContext):
    """Start creating a new post."""
    user = message.from_user

    async with get_db_context() as db:
        auth_service = AuthService(db)
        db_user = await auth_service.get_user_by_telegram_id(user.id)

        if not db_user or not db_user.is_admin:
            await message.answer("❌ Только администраторы могут создавать посты.")
            return

    # Show post type selection
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


@router.callback_query(F.data.startswith("post_type_"), PostCreation.waiting_for_type)
async def process_post_type(callback: CallbackQuery, state: FSMContext):
    """Process post type selection."""
    from aiogram.exceptions import TelegramBadRequest

    if "voice" in callback.data:
        post_type = "voice"
    elif "photo" in callback.data:
        post_type = "photo"
    else:
        post_type = "text"

    logger.info(f"User {callback.from_user.id} selected post type: {post_type}")
    await state.update_data(post_type=post_type)

    type_labels = {
        "text": "📝 Текстовый",
        "photo": "📷 Фото/Видео",
        "voice": "🎤 Аудио/Видео",
    }
    type_label = type_labels.get(post_type, post_type)

    if post_type == "photo":
        # Photo posts go straight to media upload, title is optional
        await state.set_state(PostCreation.waiting_for_media)
        await state.update_data(content="", media_ids=[])

        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Готово - Создать пост", callback_data="media_done")
        builder.adjust(1)

        msg_text = (
            f"✅ Тип: <b>{type_label}</b>\n\n"
            "Отправляйте <b>фото и видео</b> по одному.\n"
            "Когда закончите — нажмите <b>Готово</b>.\n\n"
            "Можете также отправить текст — он станет заголовком поста."
        )
        try:
            await callback.message.edit_text(msg_text, reply_markup=builder.as_markup())
        except TelegramBadRequest:
            await callback.message.answer(msg_text, reply_markup=builder.as_markup())
    else:
        await state.set_state(PostCreation.waiting_for_title)
        msg_text = f"✅ Тип: <b>{type_label}</b>\n\nОтправьте <b>заголовок</b> поста:"
        try:
            await callback.message.edit_text(msg_text)
        except TelegramBadRequest:
            await callback.message.answer(msg_text)

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass  # Query timeout - ignore


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel current action."""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нечего отменять.")
        return

    await state.clear()
    await message.answer("✅ Действие отменено.")


@router.message(PostCreation.waiting_for_title)
async def process_title(message: Message, state: FSMContext):
    """Process post title."""
    logger.info(f"process_title handler called, message type: {message.content_type}")

    if not message.text:
        await message.answer("⚠️ Пожалуйста, отправьте текстовый заголовок.")
        return

    title = message.text.strip()

    if len(title) < 3:
        await message.answer("Заголовок слишком короткий. Минимум 3 символа.")
        return

    if len(title) > 256:
        await message.answer("Заголовок слишком длинный. Максимум 256 символов.")
        return

    await state.update_data(title=title)
    await state.set_state(PostCreation.waiting_for_content)

    # Show different message based on post type
    data = await state.get_data()
    post_type = data.get("post_type", "text")
    logger.info(f"User {message.from_user.id} set title, post_type={post_type}, moving to waiting_for_content")

    if post_type == "voice":
        await message.answer(
            f"✅ Заголовок: <b>{title}</b>\n\n"
            "Теперь отправьте <b>голосовое сообщение</b> или <b>видео-кружочек</b>:"
        )
    else:
        await message.answer(
            f"✅ Заголовок: <b>{title}</b>\n\n"
            "Теперь отправьте <b>текст</b> поста (поддерживается Markdown):"
        )


@router.message(PostCreation.waiting_for_content, F.text)
async def process_content_text(message: Message, state: FSMContext):
    """Process text content."""
    data = await state.get_data()
    post_type = data.get("post_type", "text")

    # Check if user should send voice/video instead
    if post_type == "voice":
        await message.answer("⚠️ Отправьте голосовое сообщение или видео-кружочек, не текст.")
        return

    content = message.text.strip()

    if len(content) < 10:
        await message.answer("Текст слишком короткий. Минимум 10 символов.")
        return

    await state.update_data(content=content)
    await _show_visibility_keyboard(message, state)


@router.message(PostCreation.waiting_for_content, F.voice)
async def process_content_voice(message: Message, state: FSMContext, bot: Bot):
    """Process voice message content - transcribe and ask to save."""
    from src.services.transcription import TranscriptionService
    from src.services.media import MediaService
    from src.db.session import get_db_context
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    data = await state.get_data()
    post_type = data.get("post_type", "text")

    # Check if user should send text instead
    if post_type != "voice":
        await message.answer("⚠️ Отправьте текст, не голосовое сообщение.")
        return

    await message.answer("🎤 Транскрибирую голосовое сообщение...")

    # Download voice file
    try:
        file = await bot.get_file(message.voice.file_id)
        file_bytes = io.BytesIO()
        await bot.download_file(file.file_path, file_bytes)
        voice_content = file_bytes.getvalue()
    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки файла: {e}")
        return

    # Transcribe
    transcription_service = TranscriptionService()
    try:
        text = await transcription_service.transcribe_bytes(
            content=voice_content,
            filename=f"voice_{message.voice.file_unique_id}.ogg"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка транскрибации: {e}")
        return

    if not text or not text.strip():
        await message.answer("❌ Не удалось распознать речь в сообщении.")
        return

    # Format transcription with AI
    text = await transcription_service.format_transcription(text)

    # Save audio immediately to avoid storing bytes in Redis
    async with get_db_context() as db:
        auth_service = AuthService(db)
        user = await auth_service.get_user_by_telegram_id(message.from_user.id)
        if user:
            media_service = MediaService(db)
            media = await media_service.save_from_bytes(
                content=voice_content,
                filename=f"voice_{message.voice.file_unique_id}.ogg",
                mime_type="audio/ogg",
                uploader_id=user.id,
                telegram_file_id=message.voice.file_id,
            )
            voice_media_id = str(media.id)
        else:
            voice_media_id = None

    # Store transcription and media ID (not bytes!)
    await state.update_data(
        content=text,
        voice_media_id=voice_media_id,
        media_type_label="аудио",
    )

    # Ask about saving audio
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, сохранить аудио", callback_data="audio_save_yes"),
            InlineKeyboardButton(text="❌ Только текст", callback_data="audio_save_no"),
        ]
    ])

    await state.set_state(PostCreation.confirm_save_audio)
    await message.answer(
        f"📝 <b>Транскрипция:</b>\n\n{text}\n\n"
        "Сохранить оригинальное аудио к посту?",
        reply_markup=keyboard,
    )


@router.message(PostCreation.waiting_for_content, F.video_note)
async def process_content_video_note(message: Message, state: FSMContext, bot: Bot):
    """Process video note (circle video) content - transcribe and ask to save."""
    from src.services.transcription import TranscriptionService
    from src.services.media import MediaService
    from src.db.session import get_db_context
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    data = await state.get_data()
    post_type = data.get("post_type", "text")

    # Check if user should send text instead
    if post_type != "voice":
        await message.answer("⚠️ Отправьте текст, не видео-кружочек.")
        return

    await message.answer("🎬 Транскрибирую видео-кружочек...")

    # Download video note
    try:
        file = await bot.get_file(message.video_note.file_id)
        file_bytes = io.BytesIO()
        await bot.download_file(file.file_path, file_bytes)
        video_content = file_bytes.getvalue()
    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки файла: {e}")
        return

    # Transcribe
    transcription_service = TranscriptionService()
    try:
        text = await transcription_service.transcribe_bytes(
            content=video_content,
            filename=f"video_note_{message.video_note.file_unique_id}.mp4"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка транскрибации: {e}")
        return

    if not text or not text.strip():
        await message.answer("❌ Не удалось распознать речь в видео.")
        return

    # Format transcription with AI
    text = await transcription_service.format_transcription(text)

    # Save video immediately to avoid storing bytes in Redis
    async with get_db_context() as db:
        auth_service = AuthService(db)
        user = await auth_service.get_user_by_telegram_id(message.from_user.id)
        if user:
            media_service = MediaService(db)
            media = await media_service.save_from_bytes(
                content=video_content,
                filename=f"video_note_{message.video_note.file_unique_id}.mp4",
                mime_type="video/mp4",
                uploader_id=user.id,
                telegram_file_id=message.video_note.file_id,
            )
            voice_media_id = str(media.id)
        else:
            voice_media_id = None

    # Store transcription and media ID (not bytes!)
    await state.update_data(
        content=text,
        voice_media_id=voice_media_id,
        media_type_label="видео",
    )

    # Ask about saving video
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, сохранить видео", callback_data="audio_save_yes"),
            InlineKeyboardButton(text="❌ Только текст", callback_data="audio_save_no"),
        ]
    ])

    await state.set_state(PostCreation.confirm_save_audio)
    await message.answer(
        f"📝 <b>Транскрипция:</b>\n\n{text}\n\n"
        "Сохранить оригинальное видео к посту?",
        reply_markup=keyboard,
    )


@router.message(PostCreation.waiting_for_content, F.audio)
async def process_content_audio_file(message: Message, state: FSMContext, bot: Bot):
    """Process regular audio file content - transcribe and ask to save."""
    from src.services.transcription import TranscriptionService
    from src.services.media import MediaService
    from src.db.session import get_db_context
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    logger.info(f"Received audio file from user {message.from_user.id}")

    data = await state.get_data()
    post_type = data.get("post_type", "text")
    logger.info(f"Current post_type: {post_type}")

    # Check if user should send text instead
    if post_type != "voice":
        await message.answer("⚠️ Отправьте текст, не аудиофайл.")
        return

    await message.answer("🎤 Транскрибирую аудиофайл...")

    # Download audio file
    try:
        file = await bot.get_file(message.audio.file_id)
        file_bytes = io.BytesIO()
        await bot.download_file(file.file_path, file_bytes)
        audio_content = file_bytes.getvalue()
    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки файла: {e}")
        return

    # Transcribe
    filename = message.audio.file_name or f"audio_{message.audio.file_unique_id}.mp3"
    transcription_service = TranscriptionService()
    try:
        text = await transcription_service.transcribe_bytes(
            content=audio_content,
            filename=filename
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка транскрибации: {e}")
        return

    if not text or not text.strip():
        await message.answer("❌ Не удалось распознать речь в аудио.")
        return

    # Format transcription with AI
    text = await transcription_service.format_transcription(text)

    # Save audio immediately to avoid storing bytes in Redis
    async with get_db_context() as db:
        auth_service = AuthService(db)
        user = await auth_service.get_user_by_telegram_id(message.from_user.id)
        if user:
            media_service = MediaService(db)
            media = await media_service.save_from_bytes(
                content=audio_content,
                filename=filename,
                mime_type=message.audio.mime_type or "audio/mpeg",
                uploader_id=user.id,
                telegram_file_id=message.audio.file_id,
            )
            voice_media_id = str(media.id)
        else:
            voice_media_id = None

    # Store transcription and media ID (not bytes!)
    await state.update_data(
        content=text,
        voice_media_id=voice_media_id,
        media_type_label="аудио",
    )

    # Ask about saving audio
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, сохранить аудио", callback_data="audio_save_yes"),
            InlineKeyboardButton(text="❌ Только текст", callback_data="audio_save_no"),
        ]
    ])

    await state.set_state(PostCreation.confirm_save_audio)
    await message.answer(
        f"📝 <b>Транскрипция:</b>\n\n{text}\n\n"
        "Сохранить оригинальное аудио к посту?",
        reply_markup=keyboard,
    )


@router.message(PostCreation.waiting_for_content, F.video)
async def process_content_video_file(message: Message, state: FSMContext, bot: Bot):
    """Process regular video file content - transcribe and ask to save."""
    from src.services.transcription import TranscriptionService
    from src.services.media import MediaService
    from src.db.session import get_db_context
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    data = await state.get_data()
    post_type = data.get("post_type", "text")

    # Check if user should send text instead
    if post_type != "voice":
        await message.answer("⚠️ Отправьте текст, не видеофайл.")
        return

    await message.answer("🎬 Транскрибирую видеофайл...")

    # Download video file
    try:
        file = await bot.get_file(message.video.file_id)
        file_bytes = io.BytesIO()
        await bot.download_file(file.file_path, file_bytes)
        video_content = file_bytes.getvalue()
    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки файла: {e}")
        return

    # Transcribe
    filename = message.video.file_name or f"video_{message.video.file_unique_id}.mp4"
    transcription_service = TranscriptionService()
    try:
        text = await transcription_service.transcribe_bytes(
            content=video_content,
            filename=filename
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка транскрибации: {e}")
        return

    if not text or not text.strip():
        await message.answer("❌ Не удалось распознать речь в видео.")
        return

    # Format transcription with AI
    text = await transcription_service.format_transcription(text)

    # Save video immediately to avoid storing bytes in Redis
    async with get_db_context() as db:
        auth_service = AuthService(db)
        user = await auth_service.get_user_by_telegram_id(message.from_user.id)
        if user:
            media_service = MediaService(db)
            media = await media_service.save_from_bytes(
                content=video_content,
                filename=filename,
                mime_type=message.video.mime_type or "video/mp4",
                uploader_id=user.id,
                telegram_file_id=message.video.file_id,
            )
            voice_media_id = str(media.id)
        else:
            voice_media_id = None

    # Store transcription and media ID (not bytes!)
    await state.update_data(
        content=text,
        voice_media_id=voice_media_id,
        media_type_label="видео",
    )

    # Ask about saving video
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, сохранить видео", callback_data="audio_save_yes"),
            InlineKeyboardButton(text="❌ Только текст", callback_data="audio_save_no"),
        ]
    ])

    await state.set_state(PostCreation.confirm_save_audio)
    await message.answer(
        f"📝 <b>Транскрипция:</b>\n\n{text}\n\n"
        "Сохранить оригинальное видео к посту?",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("audio_save_"), PostCreation.confirm_save_audio)
async def process_audio_save_choice(callback: CallbackQuery, state: FSMContext):
    """Process user's choice to save or discard original audio/video."""
    from aiogram.exceptions import TelegramBadRequest

    save_audio = "yes" in callback.data
    await state.update_data(save_original_audio=save_audio)

    data = await state.get_data()
    media_type_label = data.get("media_type_label", "аудио")
    status = f"с {media_type_label}" if save_audio else f"без {media_type_label}"

    try:
        await callback.message.edit_text(
            f"✅ {status.capitalize()}\n\n"
            f"📝 Контент сохранён.\n\n"
            "Теперь выберите уровень видимости:"
        )
    except TelegramBadRequest:
        await callback.message.answer(
            f"✅ {status.capitalize()}\n\n"
            f"📝 Контент сохранён.\n\n"
            "Теперь выберите уровень видимости:"
        )

    await _show_visibility_keyboard(callback.message, state, edit=False)

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass  # Query timeout - ignore


async def _show_visibility_keyboard(message: Message, state: FSMContext, edit: bool = False):
    """Show visibility selection keyboard."""
    await state.set_state(PostCreation.waiting_for_visibility)

    builder = InlineKeyboardBuilder()
    builder.button(text="🌍 Публичный", callback_data="vis_public")
    builder.button(text="👤 Для зарегистрированных", callback_data="vis_registered")
    builder.button(text="⭐ Premium 1", callback_data="vis_premium_1")
    builder.button(text="💎 Premium 2", callback_data="vis_premium_2")
    builder.adjust(2)

    text = "Выберите уровень видимости:"
    if edit:
        await message.edit_text(text, reply_markup=builder.as_markup())
    else:
        await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("vis_"), PostCreation.waiting_for_visibility)
async def process_visibility(callback: CallbackQuery, state: FSMContext):
    """Process visibility selection and ask about media or publishing."""
    from aiogram.exceptions import TelegramBadRequest

    visibility = callback.data.replace("vis_", "")
    data = await state.get_data()
    post_type = data.get("post_type")

    # For photo posts, media was already collected — go to publish
    if post_type == "photo":
        await state.update_data(visibility=visibility)
        await state.set_state(PostCreation.waiting_for_publish_choice)

        builder = InlineKeyboardBuilder()
        builder.button(text="🚀 Опубликовать сейчас", callback_data="publish_now")
        builder.button(text="📝 Сохранить как черновик", callback_data="publish_draft")
        builder.adjust(1)

        try:
            await callback.message.edit_text(
                "📄 <b>Последний шаг</b>\n\nВыберите действие:",
                reply_markup=builder.as_markup(),
            )
        except TelegramBadRequest:
            await callback.message.answer(
                "📄 <b>Последний шаг</b>\n\nВыберите действие:",
                reply_markup=builder.as_markup(),
            )

        try:
            await callback.answer()
        except TelegramBadRequest:
            pass
        return

    await state.update_data(visibility=visibility, media_ids=[])
    await state.set_state(PostCreation.waiting_for_media)

    visibility_labels = {
        "public": "🌍 Публичный",
        "registered": "👤 Для зарегистрированных",
        "premium_1": "⭐ Premium 1",
        "premium_2": "💎 Premium 2",
    }
    vis_label = visibility_labels.get(visibility, visibility)

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Готово - Создать пост", callback_data="media_done")
    builder.button(text="❌ Пропустить медиа", callback_data="media_skip")
    builder.adjust(1)

    try:
        await callback.message.edit_text(
            f"✅ Видимость: <b>{vis_label}</b>\n\n"
            "Теперь можете отправить <b>медиафайлы</b> (фото, аудио, видео).\n"
            "Отправляйте файлы по одному, затем нажмите 'Готово'.\n\n"
            "Или нажмите 'Пропустить медиа' для создания поста без файлов.",
            reply_markup=builder.as_markup(),
        )
    except TelegramBadRequest:
        await callback.message.answer(
            f"✅ Видимость: <b>{vis_label}</b>\n\n"
            "Теперь можете отправить <b>медиафайлы</b> (фото, аудио, видео).\n"
            "Отправляйте файлы по одному, затем нажмите 'Готово'.\n\n"
            "Или нажмите 'Пропустить медиа' для создания поста без файлов.",
            reply_markup=builder.as_markup(),
        )

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass  # Query timeout - ignore


@router.message(PostCreation.waiting_for_media, F.text)
async def process_media_text(message: Message, state: FSMContext):
    """Handle text during media upload — use as title for photo posts."""
    data = await state.get_data()
    post_type = data.get("post_type")

    if post_type == "photo":
        title = message.text.strip()
        await state.update_data(title=title)
        await message.answer(
            f"✅ Заголовок: <b>{title}</b>\n\n"
            "Продолжайте отправлять фото/видео или нажмите <b>Готово</b>."
        )
    else:
        await message.answer("⚠️ Отправьте медиафайл или нажмите <b>Готово</b>.")


@router.message(PostCreation.waiting_for_media, F.photo)
async def process_media_photo(message: Message, state: FSMContext, bot: Bot):
    """Process uploaded photo."""
    await _save_telegram_media(message, state, bot, "image")


@router.message(PostCreation.waiting_for_media, F.audio)
async def process_media_audio(message: Message, state: FSMContext, bot: Bot):
    """Process uploaded audio."""
    await _save_telegram_media(message, state, bot, "audio")


@router.message(PostCreation.waiting_for_media, F.video)
async def process_media_video(message: Message, state: FSMContext, bot: Bot):
    """Process uploaded video."""
    await _save_telegram_media(message, state, bot, "video")


@router.message(PostCreation.waiting_for_media, F.document)
async def process_media_document(message: Message, state: FSMContext, bot: Bot):
    """Process uploaded document (check if it's media)."""
    doc = message.document
    mime = doc.mime_type or ""

    if mime.startswith("image/"):
        await _save_telegram_media(message, state, bot, "image", is_document=True)
    elif mime.startswith("audio/"):
        await _save_telegram_media(message, state, bot, "audio", is_document=True)
    elif mime.startswith("video/"):
        await _save_telegram_media(message, state, bot, "video", is_document=True)
    elif mime == "application/pdf":
        await _save_telegram_media(message, state, bot, "document", is_document=True)
    else:
        await message.answer("⚠️ Неподдерживаемый тип файла. Отправьте изображение, аудио, видео или PDF.")


async def _save_telegram_media(
    message: Message,
    state: FSMContext,
    bot: Bot,
    media_type: str,
    is_document: bool = False,
):
    """Download and save media from Telegram."""
    from src.services.media import MediaService
    from src.db.session import get_db_context
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    # Get file info
    if media_type == "image" and not is_document:
        file = message.photo[-1]  # Largest size
        file_id = file.file_id
        filename = f"photo_{file.file_unique_id}.jpg"
        mime_type = "image/jpeg"
    elif media_type == "audio" and not is_document:
        file = message.audio
        file_id = file.file_id
        filename = file.file_name or f"audio_{file.file_unique_id}.mp3"
        mime_type = file.mime_type or "audio/mpeg"
    elif media_type == "video" and not is_document:
        file = message.video
        file_id = file.file_id
        filename = file.file_name or f"video_{file.file_unique_id}.mp4"
        mime_type = file.mime_type or "video/mp4"
    else:  # document
        file = message.document
        file_id = file.file_id
        filename = file.file_name or f"file_{file.file_unique_id}"
        mime_type = file.mime_type or "application/octet-stream"

    # Download file
    try:
        tg_file = await bot.get_file(file_id)
        file_bytes = io.BytesIO()
        await bot.download_file(tg_file.file_path, file_bytes)
        content = file_bytes.getvalue()
    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки файла: {e}")
        return

    # Save to database
    async with get_db_context() as db:
        auth_service = AuthService(db)
        user = await auth_service.get_user_by_telegram_id(message.from_user.id)

        if not user:
            await message.answer("❌ Пользователь не найден.")
            return

        media_service = MediaService(db)
        try:
            media = await media_service.save_from_bytes(
                content=content,
                filename=filename,
                mime_type=mime_type,
                uploader_id=user.id,
                telegram_file_id=file_id,
            )

            # Add to state
            data = await state.get_data()
            media_ids = data.get("media_ids", [])
            media_ids.append(str(media.id))
            await state.update_data(media_ids=media_ids)

            # Show confirmation with Done button
            media_type_labels = {
                "image": "Фото",
                "audio": "Аудио",
                "video": "Видео",
                "document": "Документ",
            }
            type_label = media_type_labels.get(media_type, "Файл")

            builder = InlineKeyboardBuilder()
            builder.button(text="✅ Готово - Создать пост", callback_data="media_done")
            builder.adjust(1)

            await message.answer(
                f"✅ {type_label} сохранено! (всего {len(media_ids)} файлов)\n\n"
                "Отправьте ещё файлы или нажмите <b>Готово</b>.",
                reply_markup=builder.as_markup(),
            )
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")


@router.callback_query(F.data == "media_done", PostCreation.waiting_for_media)
@router.callback_query(F.data == "media_skip", PostCreation.waiting_for_media)
async def process_media_done(callback: CallbackQuery, state: FSMContext):
    """Finish media upload and ask about visibility or publishing."""
    from aiogram.exceptions import TelegramBadRequest

    data = await state.get_data()
    post_type = data.get("post_type")

    # For photo posts, check that at least one media was uploaded
    if post_type == "photo":
        media_ids = data.get("media_ids", [])
        if not media_ids and callback.data == "media_done":
            try:
                await callback.answer("Отправьте хотя бы одно фото или видео", show_alert=True)
            except Exception:
                pass
            return

    # For photo posts, go to visibility selection first (they skipped it earlier)
    if post_type == "photo":
        await _show_visibility_keyboard(callback.message, state, edit=False)
        try:
            await callback.answer()
        except TelegramBadRequest:
            pass
        return

    # For other post types, go straight to publish choice
    await state.set_state(PostCreation.waiting_for_publish_choice)

    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Опубликовать сейчас", callback_data="publish_now")
    builder.button(text="📝 Сохранить как черновик", callback_data="publish_draft")
    builder.adjust(1)

    try:
        await callback.message.edit_text(
            "📄 <b>Последний шаг</b>\n\n"
            "Выберите действие:",
            reply_markup=builder.as_markup(),
        )
    except TelegramBadRequest:
        await callback.message.answer(
            "📄 <b>Последний шаг</b>\n\n"
            "Выберите действие:",
            reply_markup=builder.as_markup(),
        )

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.in_({"publish_now", "publish_draft"}), PostCreation.waiting_for_publish_choice)
async def process_publish_choice(callback: CallbackQuery, state: FSMContext):
    """Create post with chosen status."""
    data = await state.get_data()
    publish_now = callback.data == "publish_now"
    await state.clear()

    from src.services.post import PostService
    from src.services.media import MediaService
    from src.db.session import get_db_context
    from uuid import UUID

    async with get_db_context() as db:
        auth_service = AuthService(db)
        user = await auth_service.get_user_by_telegram_id(callback.from_user.id)

        if not user:
            await callback.message.edit_text("❌ Пользователь не найден.")
            return

        from src.db.models.post import PostVisibility, PostStatus, PostType

        # Determine title — for photo posts it's optional
        post_type = data.get("post_type", "text")
        title = data.get("title", "").strip()
        content = data.get("content", "").strip()

        if not title:
            # Auto-generate title from date
            from datetime import datetime
            title = f"Фото {datetime.now().strftime('%d.%m.%Y %H:%M')}"

        # Photo posts from bot → PHOTO type, text/voice → ARTICLE
        db_post_type = PostType.PHOTO if post_type == "photo" else PostType.ARTICLE

        post_service = PostService(db)
        post = await post_service.create_post(
            author_id=user.id,
            title=title,
            content_md=content or "",
            visibility=PostVisibility(data.get("visibility", "public")),
            post_type=db_post_type,
        )

        # Publish if requested
        if publish_now:
            post = await post_service.publish_post(post.id)
            status_text = "Опубликован"
            # Send notifications
            from src.services.notification import notify_post_published
            await notify_post_published(db, post)
        else:
            status_text = "Черновик"

        media_service = MediaService(db)

        # Attach original voice/video if requested (already saved earlier)
        if data.get("save_original_audio") and data.get("voice_media_id"):
            voice_media_uuid = UUID(data["voice_media_id"])
            await media_service.attach_to_post(voice_media_uuid, post.id, user.id)
            await media_service.update_sort_order(voice_media_uuid, 0)

        # Attach additional media to post
        media_ids = data.get("media_ids", [])
        first_image_id = None
        if media_ids:
            start_idx = 1 if data.get("save_original_audio") and data.get("voice_media_id") else 0
            for idx, mid in enumerate(media_ids):
                await media_service.attach_to_post(UUID(mid), post.id, user.id)
                await media_service.update_sort_order(UUID(mid), start_idx + idx)
                # Track first image for cover
                if first_image_id is None:
                    media_item = await media_service.get_by_id(UUID(mid))
                    if media_item and media_item.media_type.value == "image":
                        first_image_id = UUID(mid)

        # Set first image as cover for photo posts
        if post_type == "photo" and first_image_id:
            await post_service.update_post(post.id, cover_image_id=first_image_id)

        from src.config import settings
        post_url = f"{settings.base_url}/posts/{post.slug}"

        # Build status message
        extras = []
        if data.get("save_original_audio") and data.get("voice_media_id"):
            extras.append(data.get("media_type_label", "аудио"))
        if media_ids:
            extras.append(f"{len(media_ids)} файл(ов)")
        media_text = f"\nМедиа: {', '.join(extras)}" if extras else ""

        from aiogram.exceptions import TelegramBadRequest

        try:
            await callback.message.edit_text(
                f"✅ <b>Пост создан!</b>\n\n"
                f"📝 {post.title}\n"
                f"👁 Видимость: {data.get('visibility', 'public')}\n"
                f"📄 Статус: {status_text}{media_text}\n\n"
                f"<a href='{post_url}'>Открыть пост</a>"
            )
        except TelegramBadRequest:
            await callback.message.answer(
                f"✅ <b>Пост создан!</b>\n\n"
                f"📝 {post.title}\n"
                f"👁 Видимость: {data.get('visibility', 'public')}\n"
                f"📄 Статус: {status_text}{media_text}\n\n"
                f"<a href='{post_url}'>Открыть пост</a>"
            )

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass  # Query timeout - ignore


# ============= FALLBACK HANDLER =============
# Must be at the END so it only catches callbacks that weren't handled by specific handlers

@router.callback_query(F.data.in_({"media_done", "media_skip", "publish_now", "publish_draft"}))
@router.callback_query(F.data.startswith("vis_"))
@router.callback_query(F.data.startswith("audio_save_"))
@router.callback_query(F.data.startswith("post_type_"))
async def handle_stale_callback(callback: CallbackQuery):
    """Handle callbacks when state is lost (e.g., after bot restart)."""
    from aiogram.exceptions import TelegramBadRequest

    logger.warning(f"Stale callback from user {callback.from_user.id}: {callback.data}")

    try:
        await callback.message.edit_text(
            "⚠️ Сессия устарела. Пожалуйста, начните заново с /newpost"
        )
    except TelegramBadRequest:
        await callback.message.answer(
            "⚠️ Сессия устарела. Пожалуйста, начните заново с /newpost"
        )

    try:
        await callback.answer("Сессия устарела")
    except TelegramBadRequest:
        pass
