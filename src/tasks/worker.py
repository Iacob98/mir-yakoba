"""ARQ worker settings and tasks."""

import logging
from arq.connections import RedisSettings

from src.config import settings

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:
    """Initialize worker context on startup."""
    logger.info("Worker started")


async def shutdown(ctx: dict) -> None:
    """Cleanup on worker shutdown."""
    logger.info("Worker shutting down")


class WorkerSettings:
    """ARQ worker configuration."""

    functions: list = []  # Add task functions here as needed
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 300  # 5 minutes
