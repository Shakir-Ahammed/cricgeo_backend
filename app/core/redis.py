"""
Redis client setup for CricGeo backend.
Used for live match state caching and background job queuing.

Rules:
- Redis is cache/live-state only — never primary storage
- Always write to PostgreSQL first, then Redis
- If Redis is unavailable, fall back to PostgreSQL reads gracefully
"""

from typing import Optional
import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings

# Module-level singleton — None until init_redis() is called
_redis: Optional[Redis] = None


async def init_redis() -> None:
    """
    Initialize the async Redis connection pool.
    Must be called once at application startup before any endpoint touches Redis.
    """
    global _redis
    _redis = await aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        health_check_interval=30,
    )
    # Verify the connection is actually reachable at startup
    await _redis.ping()


async def close_redis() -> None:
    """
    Close the Redis connection pool.
    Must be called at application shutdown.
    """
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def get_redis() -> Redis:
    """
    Return the active Redis client.
    Raises RuntimeError if called before init_redis().
    """
    if _redis is None:
        raise RuntimeError(
            "Redis is not initialized. Call init_redis() during application startup."
        )
    return _redis
