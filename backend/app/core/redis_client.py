import fakeredis
import fakeredis.aioredis
import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings


def create_redis() -> Redis:
    """Real Redis if REDIS_URL is a URI, otherwise an isolated in-memory fake."""
    if settings.redis_url == "memory":
        return fakeredis.aioredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=True)
    return aioredis.from_url(settings.redis_url, decode_responses=True)