from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Cookie, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.services.auth import AuthService
from src.services.media import MediaService
from src.schemas.media import MediaUploadResponse, MediaListResponse, MediaSortRequest

router = APIRouter()

templates_path = Path(__file__).parent.parent.parent.parent / "templates"
templates = Jinja2Templates(directory=templates_path)


async def get_current_user_required(
    session: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """Require authenticated user."""
    if not session:
        raise HTTPException(status_code=401, detail="Не авторизован")
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_session_token(session)
    if not user:
        raise HTTPException(status_code=401, detail="Недействительная сессия")
    return user


@router.post("/upload", response_class=HTMLResponse)
async def upload_media(
    request: Request,
    file: UploadFile = File(...),
    post_id: Optional[UUID] = Form(None),
    user=Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a media file (image, audio, or video).

    - Supports images (jpg, png, gif, webp, svg) up to 10MB
    - Supports audio (mp3, wav, ogg, aac, flac) up to 50MB
    - Supports video (mp4, webm, mov, avi) up to 100MB

    Optionally attach to a post immediately by providing post_id.
    Returns HTML partial for htmx integration.
    """
    media_service = MediaService(db)

    try:
        media = await media_service.upload_file(
            file=file,
            uploader_id=user.id,
            post_id=post_id,
        )
    except ValueError as e:
        return HTMLResponse(
            content=f'<div class="text-red-500 text-sm p-2">{str(e)}</div>',
            status_code=400,
        )

    # Return HTML partial for htmx
    return templates.TemplateResponse(
        "partials/media_item.html",
        {"request": request, "media": media},
    )


@router.get("/{media_id}", response_model=MediaUploadResponse)
async def get_media(
    media_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get media metadata by ID."""
    media_service = MediaService(db)
    media = await media_service.get_by_id(media_id)

    if not media:
        raise HTTPException(status_code=404, detail="Медиа не найдено")

    return MediaUploadResponse(
        id=media.id,
        filename=media.filename,
        original_name=media.original_name,
        media_type=media.media_type.value,
        file_size=media.file_size,
        mime_type=media.mime_type,
        url=media_service.get_url(media),
        created_at=media.created_at,
    )


@router.post("/{media_id}/attach/{post_id}", response_model=MediaUploadResponse)
async def attach_media_to_post(
    media_id: UUID,
    post_id: UUID,
    user=Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """Attach media to a post."""
    media_service = MediaService(db)
    media = await media_service.get_by_id(media_id)

    if not media:
        raise HTTPException(status_code=404, detail="Медиа не найдено")

    # Check ownership or admin
    if media.uploader_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Нет доступа")

    # Pass user.id if admin, otherwise service will verify ownership
    requester_id = media.uploader_id if user.is_admin else user.id
    media = await media_service.attach_to_post(media_id, post_id, requester_id)

    return MediaUploadResponse(
        id=media.id,
        filename=media.filename,
        original_name=media.original_name,
        media_type=media.media_type.value,
        file_size=media.file_size,
        mime_type=media.mime_type,
        url=media_service.get_url(media),
        created_at=media.created_at,
    )


@router.delete("/{media_id}", response_class=HTMLResponse)
async def delete_media(
    media_id: UUID,
    user=Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """Delete media file and record. Returns empty for htmx swap."""
    media_service = MediaService(db)
    media = await media_service.get_by_id(media_id)

    if not media:
        raise HTTPException(status_code=404, detail="Медиа не найдено")

    # Check ownership or admin
    if media.uploader_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Нет доступа")

    # Pass user.id if admin, otherwise service will verify ownership
    requester_id = media.uploader_id if user.is_admin else user.id
    await media_service.delete_media(media_id, requester_id)
    # Return empty content - htmx will remove the element
    return HTMLResponse(content="")


@router.get("/post/{post_id}", response_model=MediaListResponse)
async def list_post_media(
    post_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all media for a post."""
    media_service = MediaService(db)
    media_list = await media_service.list_post_media(post_id)

    return MediaListResponse(
        items=[
            MediaUploadResponse(
                id=m.id,
                filename=m.filename,
                original_name=m.original_name,
                media_type=m.media_type.value,
                file_size=m.file_size,
                mime_type=m.mime_type,
                url=media_service.get_url(m),
                created_at=m.created_at,
            )
            for m in media_list
        ],
        total=len(media_list),
    )


@router.post("/post/{post_id}/reorder")
async def reorder_post_media(
    post_id: UUID,
    data: MediaSortRequest,
    user=Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """Update sort order of media in a post."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Требуется доступ администратора")

    media_service = MediaService(db)

    for idx, media_id in enumerate(data.media_ids):
        await media_service.update_sort_order(media_id, idx)

    return {"success": True, "message": "Порядок обновлён"}


@router.post("/upload-editorjs")
async def upload_for_editorjs(
    file: UploadFile = File(...),
    user=Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload endpoint for Editor.js Image tool.
    Returns JSON in the format Editor.js expects:
    {"success": 1, "file": {"url": "..."}}
    """
    media_service = MediaService(db)

    try:
        media = await media_service.upload_file(
            file=file,
            uploader_id=user.id,
            post_id=None,
        )
    except ValueError as e:
        return {"success": 0, "error": str(e)}

    return {
        "success": 1,
        "file": {
            "url": f"/uploads/{media.file_path}",
            "id": str(media.id),
        }
    }
