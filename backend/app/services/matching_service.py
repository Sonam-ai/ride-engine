import logging
import time
import uuid

from app.algorithms.matching import DriverPoint, MatchingConfig, RequestPoint, match_global
from app.algorithms.state_machine import InvalidTransition
from app.core.config import settings
from app.services.driver_service import DriverLocationService
from app.services.ride_service import RideNotFound, RideRequestService
from app.services.trip_service import TripService

logger = logging.getLogger("ride_engine.matching")


class MatchingService:
    def __init__(
        self, drivers: DriverLocationService, rides: RideRequestService,
        trips: TripService, config: MatchingConfig,
    ) -> None:
        self.drivers, self.rides, self.trips, self.config = drivers, rides, trips, config

    async def run_batch(self) -> dict:
        batch_id = uuid.uuid4().hex[:8]
        started = time.perf_counter()
        now = time.time()

        pending, expired = [], 0
        for ride in await self.rides.list_open():
            if now - ride["created_at"] > settings.request_timeout_seconds:
                try:
                    await self.trips.cancel(ride["ride_id"], reason="expired")
                    expired += 1
                except (InvalidTransition, RideNotFound):
                    pass
            elif ride["status"] in ("QUOTED", "MATCHING"):
                pending.append(ride)

        ready = []
        for ride in pending:
            try:
                if ride["status"] == "QUOTED":
                    await self.trips.to_matching(ride["ride_id"])
                ready.append(ride)
            except (InvalidTransition, RideNotFound):
                pass  # cancelled while we were looking at it

        available = await self.drivers.list_drivers("available")
        requests = [
            RequestPoint(r["ride_id"], r["pickup_lat"], r["pickup_lng"], now - r["created_at"]) for r in ready
        ]
        points = [DriverPoint(d["driver_id"], d["latitude"], d["longitude"]) for d in available]
        assignments = match_global(requests, points, self.config)

        assigned = 0
        for a in assignments:
            if await self.trips.assign_driver(a.ride_id, a.driver_id, a.distance_km, a.eta_seconds, a.cost, batch_id):
                assigned += 1

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        if ready or expired:
            logger.info(
                "batch %s: pending=%d drivers=%d assigned=%d expired=%d in %.1f ms",
                batch_id, len(ready), len(points), assigned, expired, elapsed_ms,
            )
        return {
            "batch_id": batch_id, "pending": len(ready), "available_drivers": len(points),
            "assigned": assigned, "expired": expired, "elapsed_ms": elapsed_ms,
        }