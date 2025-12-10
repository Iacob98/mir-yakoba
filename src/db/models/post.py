import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.db.models.comment import Comment
    from src.db.models.media import Media
    from src.db.models.user import User


class PostStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class PostVisibility(str, enum.Enum):
    PUBLIC = "public"
    REGISTERED = "registered"
    PREMIUM_1 = "premium_1"
    PREMIUM_2 = "premium_2"


class Post(Base, TimestampMixin):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    slug: Mapped[str] = mapped_column(String(280), unique=True, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str] = mapped_column(Text, nullable=False)
    content_blocks: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    excerpt: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    visibility: Mapped[PostVisibility] = mapped_column(
        Enum(PostVisibility, name="post_visibility"),
        default=PostVisibility.PUBLIC,
        nullable=False,
    )
    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus, name="post_status"),
        default=PostStatus.DRAFT,
        nullable=False,
    )

    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Pinning
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pinned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Telegram reference
    telegram_message_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    # Cover image
    cover_image_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    author: Mapped[Optional["User"]] = relationship(
        "User", back_populates="posts", lazy="selectin"
    )
    media: Mapped[list["Media"]] = relationship(
        "Media", back_populates="post", lazy="selectin", cascade="all, delete-orphan",
        foreign_keys="Media.post_id"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="post", lazy="selectin", cascade="all, delete-orphan"
    )
    cover_image: Mapped[Optional["Media"]] = relationship(
        "Media", foreign_keys=[cover_image_id], lazy="selectin"
    )

    @property
    def featured_image(self) -> Optional[str]:
        """Get cover image URL or first image from media."""
        if self.cover_image:
            return f"/uploads/{self.cover_image.file_path}"
        # Fallback to first image in media
        for m in self.media:
            if m.media_type.value == "image":
                return f"/uploads/{m.file_path}"
        return None

    __table_args__ = (
        Index("ix_posts_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_posts_visibility_status", "visibility", "status", "published_at"),
    )
