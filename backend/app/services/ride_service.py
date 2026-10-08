import time
import uuid

from redis.asyncio import Redis

from app.services.driver_service import ACTIVE_ZONES
from app.spatial.h3_service import SpatialService

RIDES_OPEN = "rides:open"
OPEN_STATUSES = {"REQUESTED", "QUOTED", "MATCHING"}  # waiting for a driver


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


class InvalidRideState(Exception):
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
        "driver_id": data.get("driver_id") or None,
    }


class RideRequestService:
    def __init__(self, redis: Redis, spatial: SpatialService) -> None:
        self.redis = redis
        self.spatial = spatial

    async def create_request(
        self, rider_id: str, pickup_lat: float, pickup_lng: float, dest_lat: float, dest_lng: float
    ) -> dict:
        pickup_h3 = self.spatial.lat_lng_to_h3(pickup_lat, pickup_lng)
        self.spatial.validate_coordinates(dest_lat, dest_lng)

        ride_id = uuid.uuid4().hex[:12]
        # SET ... NX only succeeds if the key does not exist: one open ride per rider.
        locked = await self.redis.set(rider_lock_key(rider_id), ride_id, nx=True)
        if not locked:
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
            "status": "REQUESTED",
            "quoted_fare": "",
            "surge_multiplier": "",
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
        return parse_ride(record)

    async def get_ride(self, ride_id: str) -> dict:
        data = await self.redis.hgetall(ride_key(ride_id))
        if not data:
            raise RideNotFound(ride_id)
        return parse_ride(data)

    async def list_open(self) -> list[dict]:
        ids = sorted(await self.redis.smembers(RIDES_OPEN))
        pipe = self.redis.pipeline()
        for ride_id in ids:
            pipe.hgetall(ride_key(ride_id))
        rows = await pipe.execute()
        return [parse_ride(row) for row in rows if row]

    async def cancel(self, ride_id: str) -> dict:
        data = await self.redis.hgetall(ride_key(ride_id))
        if not data:
            raise RideNotFound(ride_id)
        if data["status"] not in OPEN_STATUSES:
            raise InvalidRideState(f"Cannot cancel a ride in status {data['status']}")
        pipe = self.redis.pipeline()
        pipe.hset(ride_key(ride_id), "status", "CANCELLED")
        pipe.srem(RIDES_OPEN, ride_id)
        pipe.srem(cell_requests_key(data["pickup_h3"]), ride_id)
        pipe.delete(rider_lock_key(data["rider_id"]))
        await pipe.execute()
        data["status"] = "CANCELLED"
        return parse_ride(data)