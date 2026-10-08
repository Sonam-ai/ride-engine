from collections import Counter

from redis.asyncio import Redis

from app.services.driver_service import DriverLocationService
from app.services.ride_service import RIDES_ACTIVE, RIDES_OPEN
from app.services.surge_service import PRICED_ZONES, zone_key
from app.services.trip_service import STATS_KEY


class StatsService:
    def __init__(self, redis: Redis, drivers: DriverLocationService) -> None:
        self.redis, self.drivers = redis, drivers

    async def get(self) -> dict:
        by_status = Counter(d["status"] for d in await self.drivers.list_drivers())
        pipe = self.redis.pipeline()
        pipe.scard(RIDES_OPEN)
        pipe.scard(RIDES_ACTIVE)
        pipe.hgetall(STATS_KEY)
        pipe.smembers(PRICED_ZONES)
        open_requests, active_rides, counters, priced = await pipe.execute()

        priced = sorted(priced)
        pipe = self.redis.pipeline()
        for cell in priced:
            pipe.hget(zone_key(cell), "surge")
        surges = [float(s) for s in await pipe.execute() if s]
        top = max(zip(surges, priced), default=None)

        matches = int(counters.get("matches", 0))
        return {
            "drivers": {
                "total": sum(by_status.values()),
                "available": by_status.get("available", 0),
                "busy": by_status.get("busy", 0),
                "offline": by_status.get("offline", 0),
                "stale": by_status.get("stale", 0),
            },
            "open_requests": open_requests,
            "active_rides": active_rides,
            "completed_trips": int(counters.get("completed", 0)),
            "cancelled_trips": int(counters.get("cancelled", 0)),
            "expired_requests": int(counters.get("expired", 0)),
            "total_matches": matches,
            "avg_pickup_eta_seconds": round(float(counters.get("pickup_eta_sum", 0)) / matches, 1) if matches else None,
            "avg_matching_seconds": round(float(counters.get("match_latency_sum", 0)) / matches, 2) if matches else None,
            "average_surge": round(sum(surges) / len(surges), 3) if surges else 1.0,
            "highest_surge_zone": {"h3_id": top[1], "surge_multiplier": top[0]} if top else None,
        }