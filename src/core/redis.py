from typing import Optional

from redis.asyncio import Redis, from_url

from src.config import settings

redis_client: Optional[Redis] = None


async def get_redis() -> Redis:
    global redis_client
    if redis_client is None:
        redis_client = from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return redis_client


async def close_redis() -> None:
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None
