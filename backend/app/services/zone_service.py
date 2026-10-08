from redis.asyncio import Redis

from app.services.driver_service import ACTIVE_ZONES, cell_available_key, cell_drivers_key
from app.services.ride_service import cell_requests_key
from app.services.surge_service import PRICED_ZONES, zone_key
from app.spatial.h3_service import SpatialService


def surge_level(surge: float) -> str:
    """The label shown on the dashboard comes from the backend, not the frontend."""
    if surge <= 1.05:
        return "LOW"
    if surge <= 1.5:
        return "NORMAL"
    if surge <= 2.5:
        return "HIGH"
    return "VERY_HIGH"


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
            pipe.hget(zone_key(cell), "surge")
            pipe.hget(zone_key(cell), "effective_ratio")
        flat = await pipe.execute()
        zones = []
        for i, cell in enumerate(cells):
            total, available, requests, surge, effective = flat[i * 5 : i * 5 + 5]
            surge_value = float(surge) if surge else 1.0
            zones.append(
                {
                    "h3_id": cell,
                    "total_drivers": total,
                    "available_drivers": available,
                    "open_requests": requests,
                    "demand_supply_ratio": round(requests / max(available, 1), 3),
                    "surge_multiplier": surge_value,
                    "effective_ratio": float(effective) if effective else 0.0,
                    "surge_level": surge_level(surge_value),
                }
            )
        return zones

    async def get_zone(self, cell: str) -> dict:
        self.spatial.validate_cell(cell)
        return (await self._counts([cell]))[0]

    async def list_zones(self) -> list[dict]:
        cells = sorted(set(await self.redis.smembers(ACTIVE_ZONES)) | set(await self.redis.smembers(PRICED_ZONES)))
        zones = await self._counts(cells)
        return [z for z in zones if z["total_drivers"] or z["open_requests"] or z["surge_multiplier"] > 1.0]