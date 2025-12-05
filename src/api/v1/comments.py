from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Cookie, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.services.auth import AuthService
from src.services.comment import CommentService
from src.services.notification import notify_admin_new_comment
from src.services.post import PostService

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


async def get_current_user_optional(
    session: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """Get current user if logged in."""
    if not session:
        return None
    auth_service = AuthService(db)
    return await auth_service.get_user_by_session_token(session)


@router.post("/{post_id}", response_class=HTMLResponse)
async def create_comment(
    request: Request,
    post_id: UUID,
    content: str = Form(...),
    user=Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """Create a new comment. Returns HTML partial for htmx."""
    if not content.strip():
        return HTMLResponse(
            content='<div class="text-red-500 text-sm">Комментарий не может быть пустым</div>',
            status_code=400,
        )

    comment_service = CommentService(db)
    comment = await comment_service.create_comment(
        post_id=post_id,
        author_id=user.id,
        content=content,
    )

    # Notify admin about new comment (don't notify if admin wrote it)
    if not user.is_admin:
        post_service = PostService(db)
        post = await post_service.get_by_id(post_id)
        if post:
            await notify_admin_new_comment(
                db=db,
                comment_author_name=user.display_name,
                post_title=post.title,
                post_slug=post.slug,
                comment_content=content,
            )

    return templates.TemplateResponse(
        "partials/comment.html",
        {"request": request, "comment": comment, "user": user},
    )


@router.get("/{post_id}", response_class=HTMLResponse)
async def list_comments(
    request: Request,
    post_id: UUID,
    page: int = 1,
    user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Get comments for a post. Returns HTML partial."""
    comment_service = CommentService(db)
    comments, total = await comment_service.list_post_comments(
        post_id=post_id,
        page=page,
    )

    return templates.TemplateResponse(
        "partials/comments_list.html",
        {
            "request": request,
            "comments": comments,
            "total": total,
            "post_id": post_id,
            "user": user,
        },
    )


@router.delete("/{comment_id}", response_class=HTMLResponse)
async def delete_comment(
    comment_id: UUID,
    user=Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """Delete a comment. Only owner or admin can delete."""
    comment_service = CommentService(db)
    comment = await comment_service.get_by_id(comment_id)

    if not comment:
        raise HTTPException(status_code=404, detail="Комментарий не найден")

    # Check ownership or admin
    if comment.author_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Нет доступа")

    await comment_service.delete_comment(comment_id)
    return HTMLResponse(content="")


@router.post("/{comment_id}/approve", response_class=HTMLResponse)
async def approve_comment(
    comment_id: UUID,
    user=Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """Approve a comment. Admin only."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Требуется доступ администратора")

    comment_service = CommentService(db)
    comment = await comment_service.approve_comment(comment_id)

    if not comment:
        raise HTTPException(status_code=404, detail="Комментарий не найден")

    return HTMLResponse(
        content='<span class="text-green-600">Одобрено</span>'
    )


@router.post("/{comment_id}/reject", response_class=HTMLResponse)
async def reject_comment(
    comment_id: UUID,
    user=Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """Reject a comment. Admin only."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Требуется доступ администратора")

    comment_service = CommentService(db)
    comment = await comment_service.reject_comment(comment_id)

    if not comment:
        raise HTTPException(status_code=404, detail="Комментарий не найден")

    return HTMLResponse(
        content='<span class="text-red-600">Отклонено</span>'
    )
