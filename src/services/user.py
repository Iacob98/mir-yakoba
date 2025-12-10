from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.user import User, AccessLevel


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_str(self, user_id: str) -> Optional[User]:
        """Get user by ID string."""
        try:
            uuid_id = UUID(user_id)
        except ValueError:
            return None
        return await self.get_by_id(uuid_id)

    async def list_users(
        self,
        page: int = 1,
        per_page: int = 20,
        search: Optional[str] = None,
    ) -> tuple[list[User], int]:
        """List users with pagination and optional search."""
        query = select(User)

        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                (User.username.ilike(search_pattern)) |
                (User.display_name.ilike(search_pattern))
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get page
        query = (
            query.order_by(User.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        result = await self.db.execute(query)
        users = list(result.scalars().all())

        return users, total

    async def update_access_level(
        self,
        user_id: UUID,
        access_level: AccessLevel,
    ) -> Optional[User]:
        """Update user's access level."""
        user = await self.get_by_id(user_id)
        if not user:
            return None

        user.access_level = access_level
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def count_admins(self) -> int:
        """Count active admin users."""
        result = await self.db.execute(
            select(func.count())
            .select_from(User)
            .where(User.is_admin == True, User.is_active == True)
        )
        return result.scalar() or 0

    async def toggle_admin(self, user_id: UUID) -> Optional[User]:
        """Toggle user's admin status."""
        user = await self.get_by_id(user_id)
        if not user:
            return None

        # Prevent removing the last admin
        if user.is_admin:
            admin_count = await self.count_admins()
            if admin_count <= 1:
                raise ValueError("Cannot remove the last admin")

        user.is_admin = not user.is_admin
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def set_admin(self, user_id: UUID, is_admin: bool) -> Optional[User]:
        """Set user's admin status."""
        user = await self.get_by_id(user_id)
        if not user:
            return None

        # Prevent removing the last admin
        if user.is_admin and not is_admin:
            admin_count = await self.count_admins()
            if admin_count <= 1:
                raise ValueError("Cannot remove the last admin")

        user.is_admin = is_admin
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def deactivate_user(self, user_id: UUID) -> Optional[User]:
        """Deactivate a user."""
        user = await self.get_by_id(user_id)
        if not user:
            return None

        # Prevent deactivating the last admin
        if user.is_admin:
            admin_count = await self.count_admins()
            if admin_count <= 1:
                raise ValueError("Cannot deactivate the last admin")

        user.is_active = False
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def activate_user(self, user_id: UUID) -> Optional[User]:
        """Activate a user."""
        user = await self.get_by_id(user_id)
        if not user:
            return None

        user.is_active = True
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def count_users(self) -> int:
        """Get total user count."""
        result = await self.db.execute(
            select(func.count()).select_from(User)
        )
        return result.scalar() or 0

    async def count_by_access_level(self) -> dict[str, int]:
        """Get user counts by access level."""
        counts = {}
        for level in AccessLevel:
            result = await self.db.execute(
                select(func.count())
                .select_from(User)
                .where(User.access_level == level)
            )
            counts[level.name.lower()] = result.scalar() or 0
        return counts

    async def update_display_name(
        self, user_id: UUID, new_display_name: str
    ) -> Optional[User]:
        """Update user's display name."""
        user = await self.get_by_id(user_id)
        if not user:
            return None

        new_display_name = new_display_name.strip()
        if not new_display_name:
            raise ValueError("Ник не может быть пустым")
        if len(new_display_name) > 128:
            raise ValueError("Ник слишком длинный (макс. 128 символов)")

        user.display_name = new_display_name
        await self.db.commit()
        await self.db.refresh(user)
        return user
