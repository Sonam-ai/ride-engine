import time

from redis.asyncio import Redis

from app.core.config import settings
from app.spatial.h3_service import SpatialService

ALL_DRIVERS = "drivers:all"
ACTIVE_ZONES = "zones:active"


def driver_key(driver_id: str) -> str:
    return f"driver:{driver_id}"


def cell_drivers_key(cell: str) -> str:
    return f"cell:{cell}:drivers"


def cell_available_key(cell: str) -> str:
    return f"cell:{cell}:available"


class DriverNotFound(Exception):
    pass


class StaleLocationUpdate(Exception):
    pass


def parse_driver(data: dict[str, str]) -> dict:
    """Redis stores everything as text; convert back to proper types."""
    return {
        "driver_id": data["driver_id"],
        "latitude": float(data["latitude"]),
        "longitude": float(data["longitude"]),
        "h3_cell": data["h3_cell"],
        "status": data["status"],
        "last_updated": float(data["last_updated"]),
        "trip_id": data.get("trip_id") or None,
    }


class DriverLocationService:
    def __init__(self, redis: Redis, spatial: SpatialService) -> None:
        self.redis = redis
        self.spatial = spatial

    async def update_location(
        self,
        driver_id: str,
        latitude: float,
        longitude: float,
        timestamp: float,
        status: str | None = None,
    ) -> dict:
        cell = self.spatial.lat_lng_to_h3(latitude, longitude)
        key = driver_key(driver_id)
        existing = await self.redis.hgetall(key)

        if existing and timestamp < float(existing["last_updated"]):
            raise StaleLocationUpdate(f"Update for {driver_id} is older than the stored one")

        if status is None:
            previous = existing.get("status")
            # A driver that pings again after being marked stale is alive again.
            status = "available" if previous in (None, "stale") else previous

        record = {
            "driver_id": driver_id,
            "latitude": str(latitude),
            "longitude": str(longitude),
            "h3_cell": cell,
            "status": status,
            "last_updated": str(timestamp),
        }
        old_cell = existing.get("h3_cell")

        pipe = self.redis.pipeline()
        pipe.hset(key, mapping=record)
        pipe.sadd(ALL_DRIVERS, driver_id)
        pipe.sadd(ACTIVE_ZONES, cell)
        if old_cell and old_cell != cell:
            pipe.srem(cell_drivers_key(old_cell), driver_id)
            pipe.srem(cell_available_key(old_cell), driver_id)
        pipe.sadd(cell_drivers_key(cell), driver_id)
        if status == "available":
            pipe.sadd(cell_available_key(cell), driver_id)
        else:
            pipe.srem(cell_available_key(cell), driver_id)
        await pipe.execute()

        return parse_driver({**existing, **record})

    async def get_driver(self, driver_id: str) -> dict:
        data = await self.redis.hgetall(driver_key(driver_id))
        if not data:
            raise DriverNotFound(driver_id)
        return parse_driver(data)

    async def list_drivers(self, status: str | None = None) -> list[dict]:
        ids = sorted(await self.redis.smembers(ALL_DRIVERS))
        pipe = self.redis.pipeline()
        for driver_id in ids:
            pipe.hgetall(driver_key(driver_id))
        rows = await pipe.execute()
        drivers = [parse_driver(row) for row in rows if row]
        if status:
            drivers = [d for d in drivers if d["status"] == status]
        return drivers

    async def sweep_stale(self) -> int:
        """Mark drivers that stopped pinging as 'stale' and remove them from supply."""
        now = time.time()
        marked = 0
        for driver_id in await self.redis.smembers(ALL_DRIVERS):
            data = await self.redis.hgetall(driver_key(driver_id))
            if not data or data["status"] in ("stale", "offline"):
                continue
            if now - float(data["last_updated"]) > settings.driver_stale_seconds:
                pipe = self.redis.pipeline()
                pipe.hset(driver_key(driver_id), "status", "stale")
                pipe.srem(cell_available_key(data["h3_cell"]), driver_id)
                await pipe.execute()
                marked += 1
        return marked