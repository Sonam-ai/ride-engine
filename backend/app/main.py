import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy import text

from app.api.v1 import drivers, h3 as h3_routes, rides, simulation, stats, zones
from app.core.config import settings
from app.core.container import Container
from app.workers.loops import start_workers

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("ride_engine")


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = await Container.create()
    app.state.container = container
    tasks = start_workers(container)
    logger.info("startup complete: redis=%s database=%s", settings.redis_url, settings.database_url)
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(*tasks, return_exceptions=True)
        await container.close()


app = FastAPI(title="Ride Engine", lifespan=lifespan)
for module in (h3_routes, drivers, rides, zones, stats, simulation):
    app.include_router(module.router)


@app.get("/health")
async def health(request: Request) -> dict:
    container = getattr(request.app.state, "container", None)
    redis_ok = db_ok = False
    if container is not None:
        try:
            redis_ok = bool(await container.redis.ping())
        except Exception:
            logger.exception("redis health check failed")
        try:
            async with container.session_factory() as session:
                await session.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            logger.exception("database health check failed")
    return {
        "status": "ok" if redis_ok and db_ok else "degraded",
        "redis": "ok" if redis_ok else "down",
        "database": "ok" if db_ok else "down",
        "city": settings.city_name,
    }