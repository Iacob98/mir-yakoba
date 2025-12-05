from typing import Optional
from uuid import UUID

import bleach
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models.comment import Comment

# Constants
MAX_COMMENT_LENGTH = 2000


class CommentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_comment(
        self,
        post_id: UUID,
        author_id: UUID,
        content: str,
        parent_id: Optional[UUID] = None,
    ) -> Comment:
        """Create a new comment."""
        # Sanitize content - no HTML allowed in comments
        clean_content = bleach.clean(content.strip(), tags=[], strip=True)

        # Validate length
        if len(clean_content) > MAX_COMMENT_LENGTH:
            raise ValueError(f"Comment exceeds maximum length of {MAX_COMMENT_LENGTH}")

        if not clean_content:
            raise ValueError("Comment cannot be empty")

        comment = Comment(
            post_id=post_id,
            author_id=author_id,
            content=clean_content,
            parent_id=parent_id,
            is_approved=True,  # Auto-approve for now
        )

        self.db.add(comment)
        await self.db.commit()
        await self.db.refresh(comment)

        # Load author relationship
        await self.db.refresh(comment, ["author"])

        return comment

    async def get_by_id(self, comment_id: UUID) -> Optional[Comment]:
        """Get comment by ID with author loaded."""
        result = await self.db.execute(
            select(Comment)
            .where(Comment.id == comment_id)
            .options(selectinload(Comment.author))
        )
        return result.scalar_one_or_none()

    async def update_comment(self, comment_id: UUID, content: str) -> Optional[Comment]:
        """Update comment content."""
        comment = await self.get_by_id(comment_id)
        if not comment:
            return None

        # Sanitize content - no HTML allowed
        clean_content = bleach.clean(content.strip(), tags=[], strip=True)

        # Validate length
        if len(clean_content) > MAX_COMMENT_LENGTH:
            raise ValueError(f"Comment exceeds maximum length of {MAX_COMMENT_LENGTH}")

        if not clean_content:
            raise ValueError("Comment cannot be empty")

        comment.content = clean_content
        await self.db.commit()
        await self.db.refresh(comment)
        return comment

    async def delete_comment(self, comment_id: UUID) -> bool:
        """Delete a comment (cascades to replies)."""
        comment = await self.get_by_id(comment_id)
        if not comment:
            return False

        await self.db.delete(comment)
        await self.db.commit()
        return True

    async def list_post_comments(
        self,
        post_id: UUID,
        page: int = 1,
        per_page: int = 50,
        include_unapproved: bool = False,
    ) -> tuple[list[Comment], int]:
        """
        Get top-level comments for a post with authors.
        Replies are loaded via relationship.
        """
        query = (
            select(Comment)
            .where(
                Comment.post_id == post_id,
                Comment.parent_id.is_(None),  # Only top-level
            )
            .options(selectinload(Comment.author))
        )

        if not include_unapproved:
            query = query.where(Comment.is_approved == True)

        # Count total
        count_query = select(func.count()).select_from(
            query.subquery()
        )
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get page
        query = (
            query.order_by(Comment.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        result = await self.db.execute(query)
        comments = list(result.scalars().all())

        # Load replies for each comment
        for comment in comments:
            await self._load_replies(comment)

        return comments, total

    async def _load_replies(self, comment: Comment, depth: int = 0, max_depth: int = 3):
        """Recursively load replies up to max_depth."""
        if depth >= max_depth:
            return

        result = await self.db.execute(
            select(Comment)
            .where(Comment.parent_id == comment.id, Comment.is_approved == True)
            .options(selectinload(Comment.author))
            .order_by(Comment.created_at.asc())
        )
        replies = list(result.scalars().all())

        # SQLAlchemy dynamic attribute
        comment.__dict__["_replies"] = replies

        for reply in replies:
            await self._load_replies(reply, depth + 1, max_depth)

    async def approve_comment(self, comment_id: UUID) -> Optional[Comment]:
        """Approve a comment."""
        comment = await self.get_by_id(comment_id)
        if not comment:
            return None

        comment.is_approved = True
        await self.db.commit()
        await self.db.refresh(comment)
        return comment

    async def reject_comment(self, comment_id: UUID) -> Optional[Comment]:
        """Reject/unapprove a comment."""
        comment = await self.get_by_id(comment_id)
        if not comment:
            return None

        comment.is_approved = False
        await self.db.commit()
        await self.db.refresh(comment)
        return comment

    async def list_pending_comments(
        self,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Comment], int]:
        """Get unapproved comments for moderation."""
        query = (
            select(Comment)
            .where(Comment.is_approved == False)
            .options(selectinload(Comment.author))
        )

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get page
        query = (
            query.order_by(Comment.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        result = await self.db.execute(query)
        comments = list(result.scalars().all())

        return comments, total

    async def count_post_comments(self, post_id: UUID) -> int:
        """Count approved comments for a post."""
        result = await self.db.execute(
            select(func.count())
            .select_from(Comment)
            .where(Comment.post_id == post_id, Comment.is_approved == True)
        )
        return result.scalar() or 0
