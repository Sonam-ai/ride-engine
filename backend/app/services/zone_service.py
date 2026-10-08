from redis.asyncio import Redis

from app.services.driver_service import ACTIVE_ZONES, cell_available_key, cell_drivers_key
from app.services.ride_service import cell_requests_key
from app.spatial.h3_service import SpatialService


class ZoneService:
    def __init__(self, redis: Redis, spatial: SpatialService) -> None:
        self.redis = redis
        self.spatial = spatial

    async def _counts(self, cells: list[str]) -> list[dict]:
        pipe = self.redis.pipeline()
        for cell in cells:
            pipe.scard(cell_drivers_key(cell))
            pipe.scard(cell_available_key(cell))
            pipe.scard(cell_requests_key(cell))
        flat = await pipe.execute()
        zones = []
        for i, cell in enumerate(cells):
            total, available, requests = flat[i * 3 : i * 3 + 3]
            zones.append(
                {
                    "h3_id": cell,
                    "total_drivers": total,
                    "available_drivers": available,
                    "open_requests": requests,
                    "demand_supply_ratio": round(requests / max(available, 1), 3),
                }
            )
        return zones

    async def get_zone(self, cell: str) -> dict:
        self.spatial.validate_cell(cell)
        return (await self._counts([cell]))[0]

    async def list_zones(self) -> list[dict]:
        cells = sorted(await self.redis.smembers(ACTIVE_ZONES))
        zones = await self._counts(cells)
        return [z for z in zones if z["total_drivers"] or z["open_requests"]]