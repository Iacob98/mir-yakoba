from fastapi import APIRouter

from src.api.v1.auth import router as auth_router
from src.api.v1.media import router as media_router
from src.api.v1.comments import router as comments_router

api_router = APIRouter()


@api_router.get("/")
async def api_root():
    return {"message": "API v1", "version": "0.1.0"}


api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(media_router, prefix="/media", tags=["media"])
api_router.include_router(comments_router, prefix="/comments", tags=["comments"])
