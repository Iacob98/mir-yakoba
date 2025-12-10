from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.db.models.user import AccessLevel
from src.db.models.post import PostStatus, PostVisibility
from src.services.auth import AuthService
from src.services.notification import notify_post_published
from src.services.post import PostService
from src.services.settings import SettingsService
from src.services.user import UserService

templates_path = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=templates_path)

web_router = APIRouter()


async def get_current_user_optional(
    session: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """Get current user if logged in, None otherwise."""
    if not session:
        return None
    auth_service = AuthService(db)
    return await auth_service.get_user_by_session_token(session)


async def require_user(
    session: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """Require authenticated user, redirect to login if not."""
    if not session:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_session_token(session)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user


@web_router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    settings_service = SettingsService(db)
    hero = await settings_service.get_hero_settings()
    return templates.TemplateResponse(
        "pages/home.html",
        {"request": request, "title": "Home", "user": user, "hero": hero},
    )


@web_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        "pages/login.html",
        {"request": request, "title": "Login"},
    )


@web_router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    user=Depends(require_user),
):
    """User profile page."""
    return templates.TemplateResponse(
        "pages/profile.html",
        {"request": request, "title": "Профиль", "user": user},
    )


@web_router.post("/profile/update-nickname")
async def update_nickname(
    request: Request,
    display_name: str = Form(...),
    user=Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user's display name."""
    user_service = UserService(db)
    error = None
    success = None

    try:
        await user_service.update_display_name(user.id, display_name)
        success = "Ник успешно изменён"
        user.display_name = display_name.strip()
    except ValueError as e:
        error = str(e)

    return templates.TemplateResponse(
        "pages/profile.html",
        {"request": request, "title": "Профиль", "user": user, "error": error, "success": success},
    )


@web_router.get("/partials/posts", response_class=HTMLResponse)
async def posts_partial(
    request: Request,
    page: int = 1,
    user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return posts list as HTML partial for htmx."""
    # Admins see all content regardless of their access_level
    if user and user.is_admin:
        access_level = AccessLevel.PREMIUM_2
    else:
        access_level = user.access_level if user else AccessLevel.PUBLIC
    post_service = PostService(db)

    posts, total = await post_service.list_posts(
        user_access_level=access_level,
        page=page,
        per_page=10,
    )

    has_more = (page * 10) < total
    next_page = page + 1 if has_more else None

    return templates.TemplateResponse(
        "partials/posts_list.html",
        {
            "request": request,
            "posts": posts,
            "has_more": has_more,
            "next_page": next_page,
        },
    )


async def require_admin(
    session: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """Require admin user, redirect to login if not."""
    if not session:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_session_token(session)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Требуется доступ администратора")
    return user


# ============= ADMIN ROUTES =============

@web_router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin dashboard with stats and recent posts."""
    post_service = PostService(db)

    # Get all posts for admin (no visibility filter)
    posts, total = await post_service.list_posts(
        user_access_level=AccessLevel.PREMIUM_2,
        include_drafts=True,
        page=1,
        per_page=20,
    )

    # Calculate stats
    published_count = sum(1 for p in posts if p.status == PostStatus.PUBLISHED)
    draft_count = sum(1 for p in posts if p.status == PostStatus.DRAFT)

    stats = {
        "posts": total,
        "published": published_count,
        "drafts": draft_count,
    }

    return templates.TemplateResponse(
        "admin/dashboard.html",
        {"request": request, "user": user, "posts": posts, "stats": stats},
    )


@web_router.get("/admin/posts/new", response_class=HTMLResponse)
async def admin_new_post(
    request: Request,
    user=Depends(require_admin),
):
    """New post form."""
    return templates.TemplateResponse(
        "admin/post_edit.html",
        {"request": request, "user": user, "post": None},
    )


@web_router.post("/admin/posts/new", response_class=HTMLResponse)
async def admin_create_post(
    request: Request,
    title: str = Form(...),
    content_md: str = Form(""),
    excerpt: str = Form(""),
    visibility: str = Form("public"),
    status: str = Form("draft"),
    media_ids: str = Form(""),
    content_blocks: str = Form(""),
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new post."""
    from uuid import UUID
    import json
    from src.services.media import MediaService

    # Parse content_blocks JSON if provided
    blocks_data = None
    if content_blocks.strip():
        try:
            blocks_data = json.loads(content_blocks)
        except json.JSONDecodeError:
            pass

    post_service = PostService(db)

    post = await post_service.create_post(
        title=title,
        content_md=content_md or "",
        author_id=user.id,
        excerpt=excerpt or None,
        visibility=PostVisibility(visibility),
        status=PostStatus(status),
        content_blocks=blocks_data,
    )

    # Attach uploaded media to the post
    if media_ids.strip():
        media_service = MediaService(db)
        ids = [mid.strip() for mid in media_ids.split(",") if mid.strip()]
        for idx, mid in enumerate(ids):
            try:
                await media_service.attach_to_post(UUID(mid), post.id, user.id)
                await media_service.update_sort_order(UUID(mid), idx)
            except (ValueError, Exception):
                pass  # Skip invalid IDs

    # Send notifications if post is published
    if status == "published":
        await notify_post_published(db, post)

    return RedirectResponse(
        url=f"/admin/posts/{post.id}/edit",
        status_code=302,
    )


@web_router.get("/admin/posts/{post_id}/edit", response_class=HTMLResponse)
async def admin_edit_post(
    request: Request,
    post_id: str,
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Edit post form."""
    post_service = PostService(db)
    post = await post_service.get_post_by_id(post_id)

    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")

    return templates.TemplateResponse(
        "admin/post_edit.html",
        {"request": request, "user": user, "post": post},
    )


@web_router.post("/admin/posts/{post_id}/edit", response_class=HTMLResponse)
async def admin_update_post(
    request: Request,
    post_id: str,
    title: str = Form(...),
    content_md: str = Form(""),
    excerpt: str = Form(""),
    visibility: str = Form("public"),
    status: str = Form("draft"),
    media_ids: str = Form(""),
    content_blocks: str = Form(""),
    cover_image_id: str = Form(""),
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a post."""
    from uuid import UUID
    import json
    from src.services.media import MediaService

    # Parse content_blocks JSON if provided
    blocks_data = None
    if content_blocks.strip():
        try:
            blocks_data = json.loads(content_blocks)
        except json.JSONDecodeError:
            pass

    # Parse cover_image_id
    cover_uuid = None
    if cover_image_id.strip():
        try:
            cover_uuid = UUID(cover_image_id.strip())
        except ValueError:
            pass

    post_service = PostService(db)

    # Check if post is being published for the first time
    old_post = await post_service.get_post_by_id(post_id)
    was_published = old_post and old_post.status == PostStatus.PUBLISHED

    post = await post_service.update_post(
        post_id=post_id,
        title=title,
        content_md=content_md or "",
        excerpt=excerpt or None,
        visibility=PostVisibility(visibility),
        status=PostStatus(status),
        content_blocks=blocks_data,
        cover_image_id=cover_uuid,
    )

    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")

    # Send notifications if post is being published for the first time
    if status == "published" and not was_published:
        await notify_post_published(db, post)

    # Sync media attachments
    # Only process if we actually received media_ids from the form
    # (prevents accidental data loss if JS didn't run)
    media_service = MediaService(db)
    new_ids = set(mid.strip() for mid in media_ids.split(",") if mid.strip())

    # Get current media
    current_media = await media_service.list_post_media(post.id)
    current_ids = set(str(m.id) for m in current_media)

    # Attach new media
    for mid in new_ids - current_ids:
        try:
            await media_service.attach_to_post(UUID(mid), post.id, user.id)
        except (ValueError, Exception):
            pass

    # Detach removed media - but only if we received actual media_ids
    # If new_ids is empty but current media exists, preserve it
    # (this prevents data loss when form submits before JS collects IDs)
    if new_ids or not current_ids:
        for mid in current_ids - new_ids:
            try:
                await media_service.detach_from_post(UUID(mid))
            except (ValueError, Exception):
                pass

    return RedirectResponse(
        url=f"/admin/posts/{post.id}/edit",
        status_code=302,
    )


@web_router.delete("/admin/posts/{post_id}")
async def admin_delete_post(
    post_id: str,
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a post."""
    post_service = PostService(db)
    deleted = await post_service.delete_post(post_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Пост не найден")

    return {"success": True}


@web_router.post("/admin/posts/{post_id}/toggle-pin", response_class=HTMLResponse)
async def admin_toggle_pin(
    post_id: str,
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Toggle pin status of a post."""
    from uuid import UUID

    try:
        uuid_id = UUID(post_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный ID поста")

    post_service = PostService(db)
    post = await post_service.toggle_pin(uuid_id)

    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")

    return RedirectResponse(url="/admin", status_code=302)


# ============= ADMIN SETTINGS ROUTES =============

@web_router.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings(
    request: Request,
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Site settings page."""
    settings_service = SettingsService(db)
    hero = await settings_service.get_hero_settings()

    return templates.TemplateResponse(
        "admin/settings.html",
        {"request": request, "user": user, "settings": hero},
    )


@web_router.post("/admin/settings", response_class=HTMLResponse)
async def admin_save_settings(
    request: Request,
    hero_title: str = Form(...),
    hero_subtitle: str = Form(...),
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Save site settings."""
    import shutil
    from fastapi import UploadFile, File

    settings_service = SettingsService(db)

    # Save text settings
    await settings_service.set("hero_title", hero_title)
    await settings_service.set("hero_subtitle", hero_subtitle)

    # Handle avatar upload
    form = await request.form()
    avatar_file = form.get("avatar")
    if avatar_file and hasattr(avatar_file, "filename") and avatar_file.filename:
        # Save avatar file
        static_dir = Path(__file__).parent.parent.parent / "static"
        avatar_path = static_dir / "avatar.jpg"

        # Save uploaded file
        content = await avatar_file.read()
        with open(avatar_path, "wb") as f:
            f.write(content)

        await settings_service.set("avatar_path", "avatar.jpg")

    return RedirectResponse(url="/admin/settings", status_code=302)


# ============= ADMIN USER ROUTES =============

@web_router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_list(
    request: Request,
    page: int = 1,
    search: str = "",
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """User management page."""
    user_service = UserService(db)

    users, total = await user_service.list_users(
        page=page,
        per_page=20,
        search=search if search else None,
    )

    has_more = (page * 20) < total

    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "user": user,
            "users": users,
            "total": total,
            "page": page,
            "search": search,
            "has_more": has_more,
            "access_levels": AccessLevel,
        },
    )


@web_router.get("/admin/users/{user_id}", response_class=HTMLResponse)
async def admin_user_edit(
    request: Request,
    user_id: str,
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Edit user page."""
    user_service = UserService(db)
    target_user = await user_service.get_by_id_str(user_id)

    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return templates.TemplateResponse(
        "admin/user_edit.html",
        {
            "request": request,
            "user": user,
            "target_user": target_user,
            "access_levels": AccessLevel,
        },
    )


@web_router.post("/admin/users/{user_id}/access-level", response_class=HTMLResponse)
async def admin_update_access_level(
    request: Request,
    user_id: str,
    access_level: str = Form(...),
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update user's access level."""
    user_service = UserService(db)

    try:
        level = AccessLevel(int(access_level))
    except (ValueError, KeyError):
        raise HTTPException(status_code=400, detail="Неверный уровень доступа")

    from uuid import UUID
    try:
        uuid_id = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный ID пользователя")

    updated_user = await user_service.update_access_level(uuid_id, level)

    if not updated_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return RedirectResponse(
        url=f"/admin/users/{user_id}",
        status_code=302,
    )


@web_router.post("/admin/users/{user_id}/toggle-admin", response_class=HTMLResponse)
async def admin_toggle_admin(
    request: Request,
    user_id: str,
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Toggle user's admin status."""
    user_service = UserService(db)

    from uuid import UUID
    try:
        uuid_id = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный ID пользователя")

    # Don't allow removing your own admin status
    if uuid_id == user.id:
        raise HTTPException(status_code=400, detail="Нельзя изменить собственный статус админа")

    updated_user = await user_service.toggle_admin(uuid_id)

    if not updated_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return RedirectResponse(
        url=f"/admin/users/{user_id}",
        status_code=302,
    )


@web_router.post("/admin/users/{user_id}/toggle-active", response_class=HTMLResponse)
async def admin_toggle_active(
    request: Request,
    user_id: str,
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Toggle user's active status."""
    user_service = UserService(db)

    from uuid import UUID
    try:
        uuid_id = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный ID пользователя")

    # Don't allow deactivating yourself
    if uuid_id == user.id:
        raise HTTPException(status_code=400, detail="Нельзя деактивировать себя")

    target_user = await user_service.get_by_id(uuid_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if target_user.is_active:
        await user_service.deactivate_user(uuid_id)
    else:
        await user_service.activate_user(uuid_id)

    return RedirectResponse(
        url=f"/admin/users/{user_id}",
        status_code=302,
    )


# ============= PUBLIC POST ROUTES =============

@web_router.get("/posts/{slug}", response_class=HTMLResponse)
async def post_detail(
    request: Request,
    slug: str,
    user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """View a single post."""
    post_service = PostService(db)
    # Admins see all content
    if user and user.is_admin:
        user_access = AccessLevel.PREMIUM_2
    else:
        user_access = user.access_level if user else AccessLevel.PUBLIC

    post = await post_service.get_post_by_slug(slug, user_access_level=user_access)

    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")

    # Increment view count
    await post_service.increment_view_count(post.id)

    return templates.TemplateResponse(
        "pages/post_detail.html",
        {"request": request, "user": user, "post": post},
    )


# ============= SEARCH ROUTES =============

@web_router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: str = "",
    page: int = 1,
    user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Search posts page."""
    post_service = PostService(db)
    # Admins see all content
    if user and user.is_admin:
        user_access = AccessLevel.PREMIUM_2
    else:
        user_access = user.access_level if user else AccessLevel.PUBLIC

    posts = []
    total = 0
    has_more = False

    if q.strip():
        posts, total = await post_service.search_posts(
            query=q,
            user_access_level=user_access,
            page=page,
            per_page=10,
        )
        has_more = (page * 10) < total

    return templates.TemplateResponse(
        "pages/search.html",
        {
            "request": request,
            "user": user,
            "query": q,
            "posts": posts,
            "total": total,
            "page": page,
            "has_more": has_more,
        },
    )


@web_router.get("/partials/search-results", response_class=HTMLResponse)
async def search_results_partial(
    request: Request,
    q: str = "",
    page: int = 1,
    user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Search results partial for htmx."""
    post_service = PostService(db)
    # Admins see all content
    if user and user.is_admin:
        user_access = AccessLevel.PREMIUM_2
    else:
        user_access = user.access_level if user else AccessLevel.PUBLIC

    posts = []
    total = 0

    if q.strip():
        posts, total = await post_service.search_posts(
            query=q,
            user_access_level=user_access,
            page=page,
            per_page=10,
        )

    return templates.TemplateResponse(
        "partials/search_results.html",
        {
            "request": request,
            "query": q,
            "posts": posts,
            "total": total,
        },
    )
