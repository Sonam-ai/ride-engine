import logging
import time

from redis.asyncio import Redis

from app.algorithms.state_machine import InvalidTransition
from app.core.config import settings
from app.services.driver_service import DriverLocationService, DriverNotFound
from app.services.ride_service import RIDES_ACTIVE, RideNotFound
from app.services.trip_service import TripService
from app.spatial.distance import move_towards

logger = logging.getLogger("ride_engine.trip_sim")


class TripSimulator:
    """Moves assigned drivers: to the pickup, then to the destination, and finishes the trip."""

    def __init__(self, redis: Redis, trips: TripService, drivers: DriverLocationService) -> None:
        self.redis, self.trips, self.drivers = redis, trips, drivers

    async def tick(self, dt_seconds: float) -> None:
        step_km = settings.average_speed_kmh * dt_seconds / 3600 * settings.trip_time_scale
        for ride_id in sorted(await self.redis.smembers(RIDES_ACTIVE)):
            try:
                await self._advance_one(ride_id, step_km)
            except (InvalidTransition, RideNotFound, DriverNotFound):
                logger.info("ride %s changed while it was being simulated; skipping", ride_id)
            except Exception:
                logger.exception("trip simulation failed for ride %s", ride_id)

    async def _move_driver(self, driver_id: str, target_lat: float, target_lng: float, step_km: float) -> bool:
        d = await self.drivers.get_driver(driver_id)
        lat, lng, arrived = move_towards(d["latitude"], d["longitude"], target_lat, target_lng, step_km)
        await self.drivers.update_location(driver_id, lat, lng, time.time(), internal=True)
        return arrived

    async def _advance_one(self, ride_id: str, step_km: float) -> None:
        ride = await self.trips.get(ride_id)
        status, driver_id = ride["status"], ride["driver_id"]
        if status == "ASSIGNED":
            await self.trips.advance(ride_id, "DRIVER_EN_ROUTE")
        elif status == "DRIVER_EN_ROUTE":
            if await self._move_driver(driver_id, ride["pickup_lat"], ride["pickup_lng"], step_km):
                await self.trips.advance(ride_id, "DRIVER_ARRIVED")
        elif status == "DRIVER_ARRIVED":
            await self.trips.advance(ride_id, "IN_PROGRESS")
        elif status == "IN_PROGRESS":
            if await self._move_driver(driver_id, ride["dest_lat"], ride["dest_lng"], step_km):
                await self.trips.advance(ride_id, "COMPLETED")