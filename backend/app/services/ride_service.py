import time
import uuid
from typing import TYPE_CHECKING

from redis.asyncio import Redis

from app.core.events import EventBus
from app.services.driver_service import ACTIVE_ZONES
from app.services.persistence import PersistenceService
from app.spatial.h3_service import SpatialService

if TYPE_CHECKING:  # avoids a circular import at runtime
    from app.services.quote_service import QuoteService

RIDES_OPEN = "rides:open"  # waiting for a driver
RIDES_ACTIVE = "rides:active"  # driver assigned, trip in progress


def ride_key(ride_id: str) -> str:
    return f"ride:{ride_id}"


def cell_requests_key(cell: str) -> str:
    return f"cell:{cell}:requests"


def rider_lock_key(rider_id: str) -> str:
    return f"rider:{rider_id}:open_ride"


class RideNotFound(Exception):
    pass


class DuplicateRide(Exception):
    pass


def parse_ride(data: dict[str, str]) -> dict:
    def opt_float(name: str) -> float | None:
        value = data.get(name)
        return float(value) if value else None

    return {
        "ride_id": data["ride_id"],
        "rider_id": data["rider_id"],
        "pickup_lat": float(data["pickup_lat"]),
        "pickup_lng": float(data["pickup_lng"]),
        "pickup_h3": data["pickup_h3"],
        "dest_lat": float(data["dest_lat"]),
        "dest_lng": float(data["dest_lng"]),
        "created_at": float(data["created_at"]),
        "status": data["status"],
        "quoted_fare": opt_float("quoted_fare"),
        "surge_multiplier": opt_float("surge_multiplier"),
        "distance_km": opt_float("distance_km"),
        "duration_min": opt_float("duration_min"),
        "pickup_eta_seconds": opt_float("pickup_eta_seconds"),
        "driver_id": data.get("driver_id") or None,
    }


class RideRequestService:
    def __init__(
        self, redis: Redis, spatial: SpatialService, quotes: "QuoteService",
        persistence: PersistenceService, events: EventBus | None = None,
    ) -> None:
        self.redis, self.spatial, self.quotes = redis, spatial, quotes
        self.persistence, self.events = persistence, events

    async def create_request(
        self, rider_id: str, pickup_lat: float, pickup_lng: float, dest_lat: float, dest_lng: float
    ) -> dict:
        quote = await self.quotes.quote(pickup_lat, pickup_lng, dest_lat, dest_lng)
        pickup_h3 = quote["pickup_h3"]

        ride_id = uuid.uuid4().hex[:12]
        # SET ... NX only succeeds if the key does not exist: one open ride per rider.
        if not await self.redis.set(rider_lock_key(rider_id), ride_id, nx=True):
            raise DuplicateRide(f"Rider {rider_id} already has an open ride")

        record = {
            "ride_id": ride_id,
            "rider_id": rider_id,
            "pickup_lat": str(pickup_lat),
            "pickup_lng": str(pickup_lng),
            "pickup_h3": pickup_h3,
            "dest_lat": str(dest_lat),
            "dest_lng": str(dest_lng),
            "created_at": str(time.time()),
            "status": "QUOTED",  # REQUESTED -> QUOTED happens immediately because we price on creation
            "quoted_fare": str(quote["estimated_fare"]),
            "surge_multiplier": str(quote["surge_multiplier"]),
            "distance_km": str(quote["distance_km"]),
            "duration_min": str(quote["duration_min"]),
            "pickup_eta_seconds": "",
            "driver_id": "",
        }
        try:
            pipe = self.redis.pipeline()
            pipe.hset(ride_key(ride_id), mapping=record)
            pipe.sadd(RIDES_OPEN, ride_id)
            pipe.sadd(cell_requests_key(pickup_h3), ride_id)
            pipe.sadd(ACTIVE_ZONES, pickup_h3)
            await pipe.execute()
        except Exception:
            await self.redis.delete(rider_lock_key(rider_id))
            raise
        ride = parse_ride(record)
        await self.persistence.record_ride_created(ride)
        if self.events:
            await self.events.publish("ride_requested", ride)
        return ride

    async def get_ride(self, ride_id: str) -> dict:
        data = await self.redis.hgetall(ride_key(ride_id))
        if not data:
            raise RideNotFound(ride_id)
        return parse_ride(data)

    async def _fetch(self, set_key: str) -> list[dict]:
        ids = sorted(await self.redis.smembers(set_key))
        pipe = self.redis.pipeline()
        for ride_id in ids:
            pipe.hgetall(ride_key(ride_id))
        rows = await pipe.execute()
        return [parse_ride(row) for row in rows if row]

    async def list_open(self) -> list[dict]:
        return await self._fetch(RIDES_OPEN)

    async def list_active(self) -> list[dict]:
        return await self._fetch(RIDES_ACTIVE)

    async def list_live(self) -> list[dict]:
        return await self.list_open() + await self.list_active()