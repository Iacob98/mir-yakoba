from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, Cookie
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.session import get_db
from src.db.models.user import AuthCode
from src.services.auth import AuthService
from src.bot.bot import send_auth_code

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class RequestCodeRequest(BaseModel):
    telegram_id: int


class RequestCodeResponse(BaseModel):
    success: bool
    message: str


class VerifyCodeRequest(BaseModel):
    telegram_id: int
    code: str


class VerifyCodeResponse(BaseModel):
    success: bool
    message: str


class UserResponse(BaseModel):
    id: str
    telegram_id: int
    username: Optional[str]
    display_name: str
    access_level: int
    is_admin: bool


@router.post("/request-code", response_model=RequestCodeResponse)
@limiter.limit("3/minute")
async def request_code(
    request: Request,
    data: RequestCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a login code. Code will be sent via Telegram bot."""
    auth_service = AuthService(db)

    # Generate code
    code = await auth_service.create_auth_code(data.telegram_id)

    # Send code via Telegram
    sent = await send_auth_code(data.telegram_id, code)

    if not sent:
        raise HTTPException(
            status_code=400,
            detail="Не удалось отправить код. Убедитесь, что вы запустили бота.",
        )

    return RequestCodeResponse(
        success=True,
        message="Код отправлен в Telegram. Проверьте сообщения.",
    )


@router.post("/verify", response_model=VerifyCodeResponse)
@limiter.limit("5/minute")
async def verify_code(
    request: Request,
    data: VerifyCodeRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Verify login code and create session."""
    auth_service = AuthService(db)

    # Verify code
    user = await auth_service.verify_auth_code(data.telegram_id, data.code)

    if not user:
        raise HTTPException(
            status_code=400,
            detail="Неверный или просроченный код.",
        )

    # Create session
    token = await auth_service.create_session(user.id)

    # Set cookie
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=not settings.debug,
        max_age=30 * 24 * 60 * 60,  # 30 days
        samesite="lax",
    )

    return VerifyCodeResponse(
        success=True,
        message="Вход выполнен!",
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    session: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """Get current logged-in user."""
    if not session:
        raise HTTPException(status_code=401, detail="Не авторизован")

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_session_token(session)

    if not user:
        raise HTTPException(status_code=401, detail="Недействительная сессия")

    return UserResponse(
        id=str(user.id),
        telegram_id=user.telegram_id,
        username=user.username,
        display_name=user.display_name,
        access_level=user.access_level.value,
        is_admin=user.is_admin,
    )


@router.post("/logout")
async def logout(
    response: Response,
    session: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """Logout and invalidate session."""
    if session:
        auth_service = AuthService(db)
        await auth_service.invalidate_session(session)

    response.delete_cookie("session")
    return {"success": True, "message": "Вы вышли из системы"}


@router.post("/verify-by-code", response_class=HTMLResponse)
@limiter.limit("5/minute")
async def verify_by_code_only(
    request: Request,
    response: Response,
    code: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Verify login code (finds telegram_id from code). Returns HTML for htmx."""
    from datetime import datetime, timezone

    # Find the auth code and get telegram_id from it
    # Normalize code to uppercase for case-insensitive comparison
    normalized_code = code.strip().upper()
    result = await db.execute(
        select(AuthCode).where(
            AuthCode.code == normalized_code,
            AuthCode.expires_at > datetime.now(timezone.utc),
            AuthCode.used == False,
        )
    )
    auth_code = result.scalar_one_or_none()

    if not auth_code:
        return HTMLResponse(
            content="""
            <div class="p-4 bg-red-50 text-red-700 rounded-lg mb-4">
                Неверный или просроченный код. Пожалуйста, получите новый код у бота.
            </div>
            <a href="/login" class="text-blue-500 hover:underline">Попробовать снова</a>
            """,
            status_code=200,
        )

    # Mark code as used
    auth_code.used = True

    # Get or create user
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_telegram_id(auth_code.telegram_id)

    if not user:
        user = await auth_service.create_user(auth_code.telegram_id)

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    # Create session
    token = await auth_service.create_session(user.id)

    # Create response with HX-Redirect header for htmx
    html_response = HTMLResponse(
        content=f"""
        <div class="p-4 bg-green-50 text-green-700 rounded-lg mb-4">
            Добро пожаловать, {user.display_name}! Перенаправление...
        </div>
        """,
        status_code=200,
    )

    # Set cookie
    html_response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=not settings.debug,
        max_age=30 * 24 * 60 * 60,  # 30 days
        samesite="lax",
    )

    # Tell htmx to do a full page redirect
    html_response.headers["HX-Redirect"] = "/"

    return html_response
