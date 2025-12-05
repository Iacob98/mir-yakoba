from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UserBrief(BaseModel):
    """Brief user info for comments."""

    id: UUID
    display_name: str

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    """Request to create a comment."""

    content: str = Field(..., min_length=1, max_length=2000)
    parent_id: Optional[UUID] = None


class CommentUpdate(BaseModel):
    """Request to update a comment."""

    content: str = Field(..., min_length=1, max_length=2000)


class CommentResponse(BaseModel):
    """Single comment response."""

    id: UUID
    content: str
    author: UserBrief
    parent_id: Optional[UUID] = None
    is_approved: bool
    created_at: datetime
    replies: list["CommentResponse"] = []

    class Config:
        from_attributes = True


class CommentListResponse(BaseModel):
    """List of comments."""

    items: list[CommentResponse]
    total: int
