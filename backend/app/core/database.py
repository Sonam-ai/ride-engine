from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings


def create_db(url: str | None = None) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    url = url or settings.database_url
    if ":memory:" in url:
        # one shared connection, otherwise each connection would get its own empty database
        engine = create_async_engine(url, poolclass=StaticPool)
    else:
        engine = create_async_engine(url)
    return engine, async_sessionmaker(engine, expire_on_commit=False)