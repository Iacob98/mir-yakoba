from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MediaUploadResponse(BaseModel):
    """Response after uploading a media file."""

    id: UUID
    filename: str
    original_name: str
    media_type: str
    file_size: int
    mime_type: str
    url: str
    created_at: datetime

    class Config:
        from_attributes = True


class MediaListResponse(BaseModel):
    """List of media items."""

    items: list[MediaUploadResponse]
    total: int = 0


class MediaAttachRequest(BaseModel):
    """Request to attach media to a post."""

    post_id: UUID


class MediaSortRequest(BaseModel):
    """Request to update media sort order."""

    media_ids: list[UUID] = Field(..., description="Media IDs in desired order")
