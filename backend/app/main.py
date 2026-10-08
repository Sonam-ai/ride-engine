import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.v1 import drivers, h3 as h3_routes, rides, zones
from app.core.config import settings
from app.core.redis_client import create_redis
from app.services.driver_service import DriverLocationService
from app.spatial.h3_service import spatial_service

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ride_engine")


async def _stale_sweeper(app: FastAPI) -> None:
    service = DriverLocationService(app.state.redis, spatial_service)
    while True:
        await asyncio.sleep(settings.sweep_interval_seconds)
        try:
            marked = await service.sweep_stale()
            if marked:
                logger.info("marked %d drivers stale", marked)
        except Exception:
            logger.exception("stale sweep failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = create_redis()
    sweeper = asyncio.create_task(_stale_sweeper(app))
    logger.info("startup complete, redis=%s", settings.redis_url)
    try:
        yield
    finally:
        sweeper.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sweeper
        await app.state.redis.aclose()


app = FastAPI(title="Ride Engine", lifespan=lifespan)
app.include_router(h3_routes.router)
app.include_router(drivers.router)
app.include_router(rides.router)
app.include_router(zones.router)


@app.get("/health")
async def health(request: Request) -> dict:
    redis_ok = False
    client = getattr(request.app.state, "redis", None)
    if client is not None:
        try:
            redis_ok = bool(await client.ping())
        except Exception:
            logger.exception("redis ping failed")
    return {
        "status": "ok" if redis_ok else "degraded",
        "redis": "ok" if redis_ok else "down",
        "city": settings.city_name,
    }