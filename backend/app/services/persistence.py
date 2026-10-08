import logging
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models.models import (
    Driver, FareTransaction, Ride, RideAssignment, Rider, SurgeHistory, TripEvent,
)

logger = logging.getLogger("ride_engine.persistence")


class PersistenceService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def _run(self, name: str, op) -> None:
        try:
            async with self.session_factory() as session:
                await op(session)
                await session.commit()
        except Exception:
            logger.exception("database write failed: %s", name)

    async def record_ride_created(self, ride: dict) -> None:
        async def op(s: AsyncSession) -> None:
            await s.merge(Rider(id=ride["rider_id"]))
            await s.flush()
            s.add(
                Ride(
                    id=ride["ride_id"],
                    rider_id=ride["rider_id"],
                    pickup_lat=ride["pickup_lat"],
                    pickup_lng=ride["pickup_lng"],
                    pickup_h3=ride["pickup_h3"],
                    dest_lat=ride["dest_lat"],
                    dest_lng=ride["dest_lng"],
                    status=ride["status"],
                    quoted_fare=ride["quoted_fare"],
                    surge_multiplier=ride["surge_multiplier"],
                    requested_at=datetime.fromtimestamp(ride["created_at"], timezone.utc),
                )
            )
            await s.flush()
            s.add(TripEvent(ride_id=ride["ride_id"], event_type="ride_created"))
            s.add(
                TripEvent(
                    ride_id=ride["ride_id"],
                    event_type="quote_generated",
                    detail=f"fare={ride['quoted_fare']} surge={ride['surge_multiplier']}",
                )
            )

        await self._run("ride_created", op)

    async def record_event(
        self, ride_id: str, event_type: str, detail: str | None = None, status: str | None = None
    ) -> None:
        async def op(s: AsyncSession) -> None:
            s.add(TripEvent(ride_id=ride_id, event_type=event_type, detail=detail))
            if status:
                await s.execute(update(Ride).where(Ride.id == ride_id).values(status=status))

        await self._run(event_type, op)

    async def record_assignment(
        self, ride_id: str, driver_id: str, batch_id: str,
        distance_km: float, eta_seconds: float, cost: float, latency_seconds: float,
    ) -> None:
        async def op(s: AsyncSession) -> None:
            await s.merge(Driver(id=driver_id))
            await s.flush()
            s.add(
                RideAssignment(
                    ride_id=ride_id, driver_id=driver_id, batch_id=batch_id,
                    pickup_distance_km=distance_km, pickup_eta_seconds=eta_seconds,
                    cost=cost, matching_latency_seconds=latency_seconds,
                )
            )
            s.add(TripEvent(ride_id=ride_id, event_type="driver_assigned", detail=f"driver={driver_id} batch={batch_id}"))
            await s.execute(
                update(Ride).where(Ride.id == ride_id).values(status="ASSIGNED", driver_id=driver_id)
            )

        await self._run("driver_assigned", op)

    async def record_completion(self, ride: dict, driver_id: str | None, final_fare: float) -> None:
        async def op(s: AsyncSession) -> None:
            s.add(TripEvent(ride_id=ride["ride_id"], event_type="trip_completed"))
            await s.execute(
                update(Ride)
                .where(Ride.id == ride["ride_id"])
                .values(status="COMPLETED", final_fare=final_fare, completed_at=datetime.now(timezone.utc))
            )
            s.add(
                FareTransaction(
                    ride_id=ride["ride_id"], driver_id=driver_id, amount=final_fare,
                    currency=settings.currency, surge_multiplier=ride.get("surge_multiplier"),
                    distance_km=ride.get("distance_km"), duration_min=ride.get("duration_min"),
                )
            )
            s.add(TripEvent(ride_id=ride["ride_id"], event_type="fare_calculated", detail=f"amount={final_fare}"))

        await self._run("trip_completed", op)

    async def record_surge(self, rows: list[dict]) -> None:
        async def op(s: AsyncSession) -> None:
            s.add_all([SurgeHistory(**row) for row in rows])

        await self._run("surge_history", op)