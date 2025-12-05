import mimetypes
import os
import re
import uuid
from pathlib import Path
from typing import Optional
from uuid import UUID

import aiofiles
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models.media import Media, MediaType


# Allowed MIME types per media type
ALLOWED_MIME_TYPES = {
    MediaType.IMAGE: {
        "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"
    },
    MediaType.AUDIO: {
        "audio/mpeg", "audio/mp3", "audio/wav", "audio/ogg", "audio/aac",
        "audio/flac", "audio/x-m4a", "audio/mp4"
    },
    MediaType.VIDEO: {
        "video/mp4", "video/webm", "video/ogg", "video/quicktime",
        "video/x-msvideo", "video/x-matroska"
    },
}

# File extensions per media type
ALLOWED_EXTENSIONS = {
    MediaType.IMAGE: {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"},
    MediaType.AUDIO: {".mp3", ".wav", ".ogg", ".aac", ".flac", ".m4a"},
    MediaType.VIDEO: {".mp4", ".webm", ".ogv", ".mov", ".avi", ".mkv"},
}


def sanitize_filename(filename: str) -> str:
    """Remove potentially dangerous characters from filename."""
    # Remove path separators and null bytes
    filename = filename.replace("/", "_").replace("\\", "_").replace("\x00", "")
    # Remove leading dots (hidden files)
    filename = filename.lstrip(".")
    # Only allow safe characters
    filename = re.sub(r"[^\w\-.]", "_", filename)
    # Limit length
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200 - len(ext)] + ext
    return filename or "unnamed"


def get_media_type_from_mime(mime_type: str) -> Optional[MediaType]:
    """Determine MediaType from MIME type."""
    mime_lower = mime_type.lower()
    for media_type, allowed in ALLOWED_MIME_TYPES.items():
        if mime_lower in allowed:
            return media_type
    return None


def get_media_type_from_extension(filename: str) -> Optional[MediaType]:
    """Determine MediaType from file extension."""
    ext = os.path.splitext(filename)[1].lower()
    for media_type, allowed in ALLOWED_EXTENSIONS.items():
        if ext in allowed:
            return media_type
    return None


class MediaService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload_file(
        self,
        file: UploadFile,
        uploader_id: UUID,
        post_id: Optional[UUID] = None,
    ) -> Media:
        """
        Upload a file and create Media record.

        Validates file type and size, saves to disk, creates DB record.
        """
        # Get original filename
        original_name = sanitize_filename(file.filename or "unnamed")

        # Determine media type from content type
        content_type = file.content_type or mimetypes.guess_type(original_name)[0] or ""
        media_type = get_media_type_from_mime(content_type)

        # Fallback to extension-based detection
        if not media_type:
            media_type = get_media_type_from_extension(original_name)

        if not media_type:
            raise ValueError(f"Неподдерживаемый тип файла: {content_type or original_name}")

        # Validate MIME type matches extension
        ext_type = get_media_type_from_extension(original_name)
        if ext_type and ext_type != media_type:
            raise ValueError("Расширение файла не соответствует типу содержимого")

        # Read file content
        content = await file.read()
        file_size = len(content)

        # Validate file size
        max_size = self._get_max_size(media_type)
        if file_size > max_size:
            raise ValueError(
                f"Файл слишком большой. Макс. размер для {media_type.value}: "
                f"{max_size // (1024 * 1024)}МБ"
            )

        # Generate unique filename
        ext = os.path.splitext(original_name)[1].lower() or self._get_default_ext(media_type)
        unique_filename = f"{uuid.uuid4()}{ext}"

        # Determine storage path
        type_dir = media_type.value + "s"  # images, audios, videos
        storage_dir = settings.upload_dir / type_dir
        storage_dir.mkdir(parents=True, exist_ok=True)

        file_path = storage_dir / unique_filename
        relative_path = f"{type_dir}/{unique_filename}"

        # Save file
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        # Create database record
        media = Media(
            post_id=post_id,
            uploader_id=uploader_id,
            media_type=media_type,
            filename=unique_filename,
            original_name=original_name,
            file_path=relative_path,
            file_size=file_size,
            mime_type=content_type,
        )

        self.db.add(media)
        await self.db.commit()
        await self.db.refresh(media)

        return media

    async def save_from_bytes(
        self,
        content: bytes,
        filename: str,
        mime_type: str,
        uploader_id: UUID,
        post_id: Optional[UUID] = None,
        telegram_file_id: Optional[str] = None,
    ) -> Media:
        """
        Save media from bytes (used for Telegram downloads).
        """
        original_name = sanitize_filename(filename)
        media_type = get_media_type_from_mime(mime_type)

        if not media_type:
            media_type = get_media_type_from_extension(original_name)

        if not media_type:
            raise ValueError(f"Неподдерживаемый тип файла: {mime_type}")

        file_size = len(content)
        max_size = self._get_max_size(media_type)
        if file_size > max_size:
            raise ValueError(f"Файл слишком большой для {media_type.value}")

        # Generate unique filename
        ext = os.path.splitext(original_name)[1].lower() or self._get_default_ext(media_type)
        unique_filename = f"{uuid.uuid4()}{ext}"

        # Storage path
        type_dir = media_type.value + "s"
        storage_dir = settings.upload_dir / type_dir
        storage_dir.mkdir(parents=True, exist_ok=True)

        file_path = storage_dir / unique_filename
        relative_path = f"{type_dir}/{unique_filename}"

        # Save file
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        # Create record
        media = Media(
            post_id=post_id,
            uploader_id=uploader_id,
            media_type=media_type,
            filename=unique_filename,
            original_name=original_name,
            file_path=relative_path,
            file_size=file_size,
            mime_type=mime_type,
            telegram_file_id=telegram_file_id,
        )

        self.db.add(media)
        await self.db.commit()
        await self.db.refresh(media)

        return media

    async def attach_to_post(
        self, media_id: UUID, post_id: UUID, requester_id: UUID
    ) -> Optional[Media]:
        """Attach unattached media to a post (requires ownership)."""
        media = await self.get_by_id(media_id)
        if not media:
            return None

        # Only allow owner to attach their own media
        if media.uploader_id != requester_id:
            return None

        media.post_id = post_id
        await self.db.commit()
        await self.db.refresh(media)
        return media

    async def detach_from_post(self, media_id: UUID) -> Optional[Media]:
        """Detach media from post (but keep file)."""
        media = await self.get_by_id(media_id)
        if not media:
            return None

        media.post_id = None
        await self.db.commit()
        await self.db.refresh(media)
        return media

    async def delete_media(self, media_id: UUID, requester_id: Optional[UUID] = None) -> bool:
        """Delete media record and file from disk."""
        media = await self.get_by_id(media_id)
        if not media:
            return False

        # Check ownership if requester specified
        if requester_id and media.uploader_id != requester_id:
            return False

        # Delete file from disk with path traversal protection
        file_path = (settings.upload_dir / media.file_path).resolve()
        upload_dir_resolved = settings.upload_dir.resolve()

        # Ensure the file is within the upload directory
        if not str(file_path).startswith(str(upload_dir_resolved)):
            # Path traversal attempt detected
            return False

        if file_path.exists() and file_path.is_file():
            file_path.unlink()

        # Delete database record
        await self.db.delete(media)
        await self.db.commit()
        return True

    async def get_by_id(self, media_id: UUID) -> Optional[Media]:
        """Get media by ID."""
        result = await self.db.execute(
            select(Media).where(Media.id == media_id)
        )
        return result.scalar_one_or_none()

    async def list_post_media(self, post_id: UUID) -> list[Media]:
        """Get all media for a post, ordered by sort_order."""
        result = await self.db.execute(
            select(Media)
            .where(Media.post_id == post_id)
            .order_by(Media.sort_order, Media.created_at)
        )
        return list(result.scalars().all())

    async def list_unattached(self, uploader_id: UUID) -> list[Media]:
        """Get unattached media for a user."""
        result = await self.db.execute(
            select(Media)
            .where(Media.uploader_id == uploader_id, Media.post_id.is_(None))
            .order_by(Media.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_sort_order(self, media_id: UUID, sort_order: int) -> Optional[Media]:
        """Update media sort order."""
        media = await self.get_by_id(media_id)
        if not media:
            return None

        media.sort_order = sort_order
        await self.db.commit()
        await self.db.refresh(media)
        return media

    def _get_max_size(self, media_type: MediaType) -> int:
        """Get max file size for media type."""
        if media_type == MediaType.IMAGE:
            return settings.max_image_size
        elif media_type == MediaType.AUDIO:
            return settings.max_audio_size
        elif media_type == MediaType.VIDEO:
            return settings.max_video_size
        return settings.max_image_size

    def _get_default_ext(self, media_type: MediaType) -> str:
        """Get default extension for media type."""
        defaults = {
            MediaType.IMAGE: ".jpg",
            MediaType.AUDIO: ".mp3",
            MediaType.VIDEO: ".mp4",
        }
        return defaults.get(media_type, ".bin")

    def get_url(self, media: Media) -> str:
        """Get public URL for media file."""
        return f"/uploads/{media.file_path}"
