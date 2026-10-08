import asyncio
import time

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.container import Container
from app.models.models import FareTransaction, RideAssignment, Ride, SurgeHistory, TripEvent
from app.services.zone_service import surge_level

LAT, LNG = 12.9716, 77.5946
DEST = (LAT + 0.03, LNG + 0.03)


def run(scenario):
    async def wrapper():
        c = await Container.create("memory", "sqlite+aiosqlite:///:memory:")
        try:
            await scenario(c)
        finally:
            await c.close()

    asyncio.run(wrapper())


async def finish_trip(c, ride_id):
    for _ in range(10):
        await c.trip_sim.tick(10_000)  # a huge time step: every leg ends in one tick
        if (await c.trips.get(ride_id))["status"] == "COMPLETED":
            return
    raise AssertionError("trip did not complete")


def test_full_lifecycle_is_persisted_to_the_database():
    async def scenario(c):
        await c.drivers.update_location("d1", LAT, LNG + 0.01, time.time())
        ride = await c.rides.create_request("r1", LAT, LNG, *DEST)
        assert ride["status"] == "QUOTED"

        batch = await c.matching.run_batch()
        assert batch["assigned"] == 1
        assigned = await c.trips.get(ride["ride_id"])
        assert assigned["status"] == "ASSIGNED" and assigned["driver_id"] == "d1"
        assert assigned["pickup_eta_seconds"] > 0
        assert (await c.drivers.get_driver("d1"))["status"] == "busy"

        await finish_trip(c, ride["ride_id"])

        driver = await c.drivers.get_driver("d1")
        assert driver["status"] == "available" and driver["trip_id"] is None
        assert driver["latitude"] == pytest.approx(DEST[0]) and driver["longitude"] == pytest.approx(DEST[1])
        assert await c.rides.create_request("r1", LAT, LNG, *DEST)  # rider is free to ride again

        async with c.session_factory() as s:
            stored = (await s.execute(select(Ride).where(Ride.id == ride["ride_id"]))).scalar_one()
            assert stored.status == "COMPLETED" and stored.driver_id == "d1" and stored.final_fare > 0
            events = (
                await s.execute(select(TripEvent.event_type).where(TripEvent.ride_id == ride["ride_id"]).order_by(TripEvent.id))
            ).scalars().all()
            assert events == [
                "ride_created", "quote_generated", "matching_started", "driver_assigned",
                "driver_en_route", "driver_arrived", "trip_started", "trip_completed", "fare_calculated",
            ]
            assert (await s.execute(select(func.count()).select_from(FareTransaction))).scalar_one() == 1
            assert (await s.execute(select(func.count()).select_from(RideAssignment))).scalar_one() == 1

        stats = await c.stats.get()
        assert stats["completed_trips"] == 1 and stats["total_matches"] == 1

    run(scenario)


def test_driver_too_far_away_is_not_assigned():
    async def scenario(c):
        await c.drivers.update_location("far", LAT + 0.2, LNG, time.time())  # ~22 km away
        ride = await c.rides.create_request("r1", LAT, LNG, *DEST)
        batch = await c.matching.run_batch()
        assert batch["assigned"] == 0
        assert (await c.trips.get(ride["ride_id"]))["status"] == "MATCHING"

    run(scenario)


def test_cancelling_an_assigned_ride_frees_the_driver():
    async def scenario(c):
        await c.drivers.update_location("d1", LAT, LNG, time.time())
        ride = await c.rides.create_request("r1", LAT, LNG, *DEST)
        await c.matching.run_batch()
        await c.trips.cancel(ride["ride_id"])
        driver = await c.drivers.get_driver("d1")
        assert driver["status"] == "available" and driver["trip_id"] is None
        assert (await c.trips.get(ride["ride_id"]))["status"] == "CANCELLED"

    run(scenario)


def test_unmatched_requests_expire(monkeypatch):
    async def scenario(c):
        ride = await c.rides.create_request("r1", LAT, LNG, *DEST)
        monkeypatch.setattr(settings, "request_timeout_seconds", -1.0)
        batch = await c.matching.run_batch()
        assert batch["expired"] == 1
        assert (await c.trips.get(ride["ride_id"]))["status"] == "CANCELLED"
        assert (await c.stats.get())["expired_requests"] == 1

    run(scenario)


def test_gps_pings_cannot_teleport_a_busy_driver():
    async def scenario(c):
        await c.drivers.update_location("d1", LAT, LNG, time.time())
        await c.rides.create_request("r1", LAT, LNG, *DEST)
        await c.matching.run_batch()
        await c.drivers.update_location("d1", LAT + 0.5, LNG, time.time())  # outside ping
        assert (await c.drivers.get_driver("d1"))["latitude"] == pytest.approx(LAT)

    run(scenario)


def test_demand_spike_raises_surge_and_it_decays_afterwards():
    async def scenario(c):
        hot = c.spatial.lat_lng_to_h3(LAT, LNG)
        for i in range(5):
            await c.drivers.update_location(f"d{i}", LAT, LNG, time.time())
        for i in range(15):
            await c.rides.create_request(f"r{i}", LAT, LNG, *DEST)

        history = []
        for _ in range(6):
            history.append((await c.surge.update_all())[hot].surge)
        assert history == sorted(history) and history[0] < history[-1]  # smooth climb, not a jump
        assert 1.5 < history[-1] < 1.97
        zone = await c.zones.get_zone(hot)
        assert zone["surge_level"] in ("HIGH", "NORMAL") and zone["surge_multiplier"] == history[-1]

        for ride in await c.rides.list_open():
            await c.trips.cancel(ride["ride_id"])
        for _ in range(12):
            final = (await c.surge.update_all())[hot].surge
        assert final < 1.2  # demand is gone, surge decays back

        async with c.session_factory() as s:
            assert (await s.execute(select(func.count()).select_from(SurgeHistory))).scalar_one() > 0

    run(scenario)


def test_surge_level_labels_come_from_the_backend():
    assert surge_level(1.0) == "LOW"
    assert surge_level(1.3) == "NORMAL"
    assert surge_level(2.0) == "HIGH"
    assert surge_level(3.5) == "VERY_HIGH"