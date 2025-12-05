import hashlib
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models.user import AccessLevel, AuthCode, Session, User


def generate_auth_code() -> str:
    """Generate an 8-character alphanumeric auth code."""
    # Use uppercase letters and digits (excluding confusing chars like 0/O, 1/I/L)
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


def generate_session_token() -> str:
    """Generate a secure session token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_auth_code(self, telegram_id: int) -> str:
        """Create a new auth code for Telegram user."""
        # Invalidate any existing codes
        await self.db.execute(
            AuthCode.__table__.update()
            .where(AuthCode.telegram_id == telegram_id, AuthCode.used == False)
            .values(used=True)
        )

        code = generate_auth_code()
        auth_code = AuthCode(
            code=code,
            telegram_id=telegram_id,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.auth_code_expire_minutes),
        )
        self.db.add(auth_code)
        await self.db.commit()
        return code

    async def verify_auth_code(
        self, telegram_id: int, code: str
    ) -> Optional[User]:
        """Verify auth code and return user if valid."""
        # Normalize code to uppercase for comparison
        normalized_code = code.strip().upper()
        result = await self.db.execute(
            select(AuthCode).where(
                AuthCode.telegram_id == telegram_id,
                AuthCode.code == normalized_code,
                AuthCode.expires_at > datetime.now(timezone.utc),
                AuthCode.used == False,
            )
        )
        auth_code = result.scalar_one_or_none()

        if not auth_code:
            return None

        # Mark code as used
        auth_code.used = True

        # Get or create user
        user = await self.get_user_by_telegram_id(telegram_id)
        if not user:
            user = await self.create_user(telegram_id)

        # Update last login
        user.last_login = datetime.now(timezone.utc)
        await self.db.commit()

        return user

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        result = await self.db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> User:
        """Create a new user."""
        user = User(
            telegram_id=telegram_id,
            username=username,
            display_name=display_name or f"User_{telegram_id}",
            access_level=AccessLevel.REGISTERED,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def create_session(self, user_id: UUID) -> str:
        """Create a new session and return the token."""
        token = generate_session_token()
        token_hash = hash_token(token)

        session = Session(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.session_expire_days),
        )
        self.db.add(session)
        await self.db.commit()

        return token

    async def get_user_by_session_token(self, token: str) -> Optional[User]:
        """Get user by session token."""
        token_hash = hash_token(token)
        result = await self.db.execute(
            select(Session)
            .where(
                Session.token_hash == token_hash,
                Session.expires_at > datetime.now(timezone.utc),
            )
        )
        session = result.scalar_one_or_none()

        if not session:
            return None

        return await self.get_user_by_id(session.user_id)

    async def invalidate_session(self, token: str) -> bool:
        """Invalidate a session token."""
        token_hash = hash_token(token)
        result = await self.db.execute(
            select(Session).where(Session.token_hash == token_hash)
        )
        session = result.scalar_one_or_none()

        if session:
            await self.db.delete(session)
            await self.db.commit()
            return True
        return False

    async def update_user_info(
        self,
        user: User,
        username: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> User:
        """Update user info from Telegram."""
        if username:
            user.username = username
        if display_name:
            user.display_name = display_name
        await self.db.commit()
        await self.db.refresh(user)
        return user
