import fakeredis
import fakeredis.aioredis
import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings


def create_redis(url: str | None = None) -> Redis:
    """Real Redis if the URL is a URI, otherwise an isolated in-memory fake."""
    url = url or settings.redis_url

    if url == "memory":
        return fakeredis.aioredis.FakeRedis(
            server=fakeredis.FakeServer(),
            decode_responses=True,
        )

    return aioredis.from_url(url, decode_responses=True)