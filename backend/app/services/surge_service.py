import logging
import time

from redis.asyncio import Redis

from app.algorithms.surge import SurgePricingEngine, SurgeResult
from app.core.config import settings
from app.core.events import EventBus
from app.services.driver_service import ACTIVE_ZONES, cell_available_key
from app.services.persistence import PersistenceService
from app.services.ride_service import cell_requests_key
from app.spatial.h3_service import SpatialService

logger = logging.getLogger("ride_engine.surge")

PRICED_ZONES = "zones:priced"


def zone_key(cell: str) -> str:
    return f"zone:{cell}"


class SurgeService:
    def __init__(
        self, redis: Redis, spatial: SpatialService, engine: SurgePricingEngine,
        persistence: PersistenceService, events: EventBus | None = None,
    ) -> None:
        self.redis, self.spatial, self.engine = redis, spatial, engine
        self.persistence, self.events = persistence, events

    async def preview(self, cell: str) -> tuple[SurgeResult, int, int]:
        """Surge a rider would see right now for this cell. Read-only."""
        cells = [cell, *self.spatial.get_neighbors(cell)]
        pipe = self.redis.pipeline()
        for c in cells:
            pipe.scard(cell_available_key(c))
            pipe.scard(cell_requests_key(c))
        pipe.hget(zone_key(cell), "surge")
        flat = await pipe.execute()
        n = len(cells)
        supplies = [flat[2 * i] for i in range(n)]
        demands = [flat[2 * i + 1] for i in range(n)]
        previous = float(flat[2 * n]) if flat[2 * n] else self.engine.min_surge
        neighbor_ratios = [self.engine.ratio(demands[i], supplies[i]) for i in range(1, n)]
        return self.engine.compute(demands[0], supplies[0], neighbor_ratios, previous), supplies[0], demands[0]

    async def update_all(self) -> dict[str, SurgeResult]:
        """Recompute surge for every active cell and its neighbors; keep history of real changes."""
        active = await self.redis.smembers(ACTIVE_ZONES)
        cells = set(active) | set(await self.redis.smembers(PRICED_ZONES))
        for cell in active:
            cells.update(self.spatial.get_neighbors(cell))
        ordered = sorted(cells)
        if not ordered:
            return {}

        lo = self.engine.min_surge
        pipe = self.redis.pipeline()
        for cell in ordered:
            pipe.scard(cell_available_key(cell))
            pipe.scard(cell_requests_key(cell))
            pipe.hget(zone_key(cell), "surge")
            pipe.hget(zone_key(cell), "persisted_surge")
        flat = await pipe.execute()
        inputs = {}
        for i, cell in enumerate(ordered):
            supply, demand, prev, persisted = flat[i * 4 : i * 4 + 4]
            inputs[cell] = (supply, demand, float(prev) if prev else lo, float(persisted) if persisted else lo)
        ratios = {c: self.engine.ratio(d, s) for c, (s, d, _, _) in inputs.items()}

        results: dict[str, SurgeResult] = {}
        history, changed = [], []
        now = time.time()
        pipe = self.redis.pipeline()
        for cell, (supply, demand, prev, persisted) in inputs.items():
            neighbor_ratios = [ratios.get(n, 0.0) for n in self.spatial.get_neighbors(cell)]
            result = self.engine.compute(demand, supply, neighbor_ratios, prev)
            results[cell] = result
            mapping = {
                "surge": str(result.surge), "local_ratio": str(result.local_ratio),
                "effective_ratio": str(result.effective_ratio),
                "supply": str(supply), "demand": str(demand), "updated_at": str(now),
            }
            if abs(result.surge - persisted) >= settings.surge_history_min_delta:
                history.append(
                    {
                        "h3_id": cell, "surge_multiplier": result.surge, "supply": supply,
                        "demand": demand, "demand_supply_ratio": result.local_ratio,
                    }
                )
                mapping["persisted_surge"] = str(result.surge)
            pipe.hset(zone_key(cell), mapping=mapping)
            pipe.sadd(PRICED_ZONES, cell)
            if abs(result.surge - prev) >= 0.01:
                changed.append({"h3_id": cell, "surge_multiplier": result.surge, "supply": supply, "demand": demand})
        await pipe.execute()

        if history:
            await self.persistence.record_surge(history)
        if changed and self.events:
            await self.events.publish("surge_updated", {"zones": changed})
        return results