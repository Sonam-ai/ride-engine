import logging
import time

from redis.asyncio import Redis

from app.algorithms.state_machine import validate_transition
from app.core.events import EventBus
from app.services.driver_service import cell_available_key, driver_key
from app.services.persistence import PersistenceService
from app.services.ride_service import (
    RIDES_ACTIVE, RIDES_OPEN, RideNotFound, cell_requests_key, parse_ride, ride_key, rider_lock_key,
)

logger = logging.getLogger("ride_engine.trips")

STATS_KEY = "stats"
ADVANCE_TARGETS = {"DRIVER_EN_ROUTE", "DRIVER_ARRIVED", "IN_PROGRESS", "COMPLETED"}
EVENT_NAMES = {
    "MATCHING": "matching_started",
    "DRIVER_EN_ROUTE": "driver_en_route",
    "DRIVER_ARRIVED": "driver_arrived",
    "IN_PROGRESS": "trip_started",
    "CANCELLED": "ride_cancelled",
}


class TripService:
    def __init__(self, redis: Redis, persistence: PersistenceService, events: EventBus | None = None) -> None:
        self.redis, self.persistence, self.events = redis, persistence, events

    async def _load(self, ride_id: str) -> dict:
        data = await self.redis.hgetall(ride_key(ride_id))
        if not data:
            raise RideNotFound(ride_id)
        return data

    async def get(self, ride_id: str) -> dict:
        return parse_ride(await self._load(ride_id))

    async def _announce(self, ride_id: str, previous: str, target: str, **extra) -> None:
        logger.info("ride %s: %s -> %s", ride_id, previous, target)
        if self.events:
            await self.events.publish("ride_status_changed", {"ride_id": ride_id, "from": previous, "to": target, **extra})

    async def _release_driver(self, driver_id: str, ride_id: str) -> None:
        driver = await self.redis.hgetall(driver_key(driver_id))
        if not driver or driver.get("trip_id") != ride_id:
            return
        pipe = self.redis.pipeline()
        pipe.hset(driver_key(driver_id), "status", "available")
        pipe.hdel(driver_key(driver_id), "trip_id")
        pipe.sadd(cell_available_key(driver["h3_cell"]), driver_id)
        await pipe.execute()

    async def to_matching(self, ride_id: str) -> None:
        ride = await self._load(ride_id)
        validate_transition(ride["status"], "MATCHING")
        await self.redis.hset(ride_key(ride_id), "status", "MATCHING")
        await self.persistence.record_event(ride_id, EVENT_NAMES["MATCHING"], status="MATCHING")
        await self._announce(ride_id, ride["status"], "MATCHING")

    async def assign_driver(
        self, ride_id: str, driver_id: str, distance_km: float, eta_seconds: float, cost: float, batch_id: str
    ) -> bool:
        """Claim the driver and move the ride to ASSIGNED. Returns False if it is no longer possible."""
        ride = await self._load(ride_id)
        if ride["status"] != "MATCHING":
            return False
        driver = await self.redis.hgetall(driver_key(driver_id))
        if not driver or driver.get("status") != "available":
            return False

        latency = time.time() - float(ride["created_at"])
        pipe = self.redis.pipeline()
        pipe.hset(driver_key(driver_id), mapping={"status": "busy", "trip_id": ride_id})
        pipe.srem(cell_available_key(driver["h3_cell"]), driver_id)
        pipe.hset(
            ride_key(ride_id),
            mapping={"status": "ASSIGNED", "driver_id": driver_id, "pickup_eta_seconds": str(round(eta_seconds, 1))},
        )
        pipe.srem(RIDES_OPEN, ride_id)
        pipe.srem(cell_requests_key(ride["pickup_h3"]), ride_id)  # demand is satisfied
        pipe.sadd(RIDES_ACTIVE, ride_id)
        pipe.hincrby(STATS_KEY, "matches", 1)
        pipe.hincrbyfloat(STATS_KEY, "pickup_eta_sum", eta_seconds)
        pipe.hincrbyfloat(STATS_KEY, "match_latency_sum", latency)
        await pipe.execute()

        await self.persistence.record_assignment(ride_id, driver_id, batch_id, distance_km, eta_seconds, cost, latency)
        await self._announce(ride_id, "MATCHING", "ASSIGNED", driver_id=driver_id)
        if self.events:
            await self.events.publish(
                "driver_assigned",
                {"ride_id": ride_id, "driver_id": driver_id, "pickup_eta_seconds": round(eta_seconds, 1),
                 "pickup_lat": float(ride["pickup_lat"]), "pickup_lng": float(ride["pickup_lng"])},
            )
        return True

    async def advance(self, ride_id: str, target: str) -> dict:
        if target not in ADVANCE_TARGETS:
            raise ValueError(f"advance() cannot move a ride to {target}")
        ride = await self._load(ride_id)
        validate_transition(ride["status"], target)
        if target == "COMPLETED":
            await self._complete(ride)
        else:
            await self.redis.hset(ride_key(ride_id), "status", target)
            await self.persistence.record_event(ride_id, EVENT_NAMES[target], status=target)
        await self._announce(ride_id, ride["status"], target)
        return await self.get(ride_id)

    async def _complete(self, ride: dict) -> None:
        ride_id, driver_id = ride["ride_id"], ride.get("driver_id")
        pipe = self.redis.pipeline()
        pipe.hset(ride_key(ride_id), mapping={"status": "COMPLETED", "completed_at": str(time.time())})
        pipe.srem(RIDES_ACTIVE, ride_id)
        pipe.delete(rider_lock_key(ride["rider_id"]))
        pipe.hincrby(STATS_KEY, "completed", 1)
        await pipe.execute()
        if driver_id:
            await self._release_driver(driver_id, ride_id)
        fare = float(ride["quoted_fare"]) if ride.get("quoted_fare") else 0.0
        await self.persistence.record_completion(parse_ride(ride), driver_id or None, fare)

    async def cancel(self, ride_id: str, reason: str = "rider_cancelled") -> dict:
        ride = await self._load(ride_id)
        validate_transition(ride["status"], "CANCELLED")
        pipe = self.redis.pipeline()
        pipe.hset(ride_key(ride_id), "status", "CANCELLED")
        pipe.srem(RIDES_OPEN, ride_id)
        pipe.srem(RIDES_ACTIVE, ride_id)
        pipe.srem(cell_requests_key(ride["pickup_h3"]), ride_id)
        pipe.delete(rider_lock_key(ride["rider_id"]))
        pipe.hincrby(STATS_KEY, "expired" if reason == "expired" else "cancelled", 1)
        await pipe.execute()
        if ride.get("driver_id"):
            await self._release_driver(ride["driver_id"], ride_id)
        await self.persistence.record_event(ride_id, EVENT_NAMES["CANCELLED"], detail=reason, status="CANCELLED")
        await self._announce(ride_id, ride["status"], "CANCELLED", reason=reason)
        return await self.get(ride_id)