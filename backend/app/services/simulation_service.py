import asyncio
import logging
import math
import random
import time

from redis.asyncio import Redis

from app.core.config import settings
from app.core.events import EventBus
from app.services.driver_service import DriverLocationService, StaleLocationUpdate, driver_key
from app.services.ride_service import DuplicateRide, RideRequestService
from app.simulation.demand import make_request
from app.simulation.fleet import SimDriver, make_fleet

logger = logging.getLogger("ride_engine.simulation")

MAX_DRIVERS = 1000
MAX_DEMAND = 300.0


def poisson(rng: random.Random, lam: float) -> int:
    """Number of random arrivals in one time step (Knuth's method; fine for small lam)."""
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= limit:
            return k - 1


class SimulationService:
    """Built-in simulation: a fleet of wandering drivers plus random ride demand."""

    def __init__(
        self, redis: Redis, drivers: DriverLocationService, rides: RideRequestService, events: EventBus | None = None
    ) -> None:
        self.redis, self.drivers, self.rides, self.events = redis, drivers, rides, events
        self._lock = asyncio.Lock()
        self._reset_state()

    def _reset_state(self) -> None:
        self.rng = random.Random(settings.simulation_seed)
        self.fleet: list[SimDriver] = []
        self.running = False
        self.demand_per_minute = settings.demand_per_minute
        self.spike: dict | None = None
        self._rider_counter = 0
        self._next_driver = 1

    def state(self) -> dict:
        left = max(0.0, self.spike["until"] - time.time()) if self.spike else 0.0
        return {
            "running": self.running,
            "demand_per_minute": round(self.demand_per_minute, 1),
            "driver_count": len(self.fleet),
            "spike_seconds_left": round(left),
        }

    def _new_drivers(self, count: int) -> list[SimDriver]:
        fleet = make_fleet(count, settings.city_lat, settings.city_lng, settings.city_radius_km, self.rng)
        for d in fleet:  # keep ids unique when drivers are added later
            d.driver_id = f"drv-{self._next_driver:03d}"
            self._next_driver += 1
        return fleet

    async def start(self) -> None:
        async with self._lock:
            if not self.fleet:
                self.fleet = self._new_drivers(settings.driver_count)
            self.running = True
            await self._ping_all(move=False)

    async def pause(self) -> None:
        self.running = False

    async def reset(self) -> None:
        """Wipe live state (Redis) and the fleet. Database history is kept."""
        async with self._lock:
            await self.redis.flushdb()
            self._reset_state()
        if self.events:
            await self.events.publish("simulation_reset", {})

    def set_demand(self, per_minute: float | None, factor: float | None) -> None:
        value = per_minute if per_minute is not None else self.demand_per_minute * (factor or 1.0)
        self.demand_per_minute = min(MAX_DEMAND, max(0.0, value))

    async def trigger_spike(self, lat: float, lng: float, duration: float, multiplier: float) -> None:
        if not self.running:
            await self.start()
        self.spike = {"lat": lat, "lng": lng, "until": time.time() + duration, "multiplier": multiplier}

    async def change_drivers(self, delta: int) -> None:
        async with self._lock:
            if delta > 0:
                added = self._new_drivers(min(delta, MAX_DRIVERS - len(self.fleet)))
                self.fleet.extend(added)
                await self._ping_all(move=False)
                return
            to_remove = -delta
            for d in reversed(list(self.fleet)):
                if to_remove <= 0:
                    break
                if await self.redis.hget(driver_key(d.driver_id), "status") == "busy":
                    continue  # never remove a driver in the middle of a trip
                await self.drivers.remove_driver(d.driver_id)
                self.fleet.remove(d)
                to_remove -= 1

    async def _ping_all(self, move: bool) -> None:
        for d in list(self.fleet):
            if move:
                d.step(settings.gps_update_interval, self.rng, settings.city_lat, settings.city_lng, settings.city_radius_km)
            try:
                result = await self.drivers.update_location(d.driver_id, d.lat, d.lng, time.time(), d.pending_status)
            except StaleLocationUpdate:
                continue
            d.pending_status = None
            if result["status"] == "busy":
                # the trip simulator moves busy drivers; follow their real position
                d.lat, d.lng = result["latitude"], result["longitude"]
            elif move:
                d.maybe_toggle_online(self.rng)

    async def fleet_tick(self) -> None:
        async with self._lock:
            await self._ping_all(move=self.running)

    async def demand_tick(self) -> None:
        """Called once per second."""
        if not self.running or self.demand_per_minute <= 0:
            return
        rate, hotspot, share = self.demand_per_minute, None, 0.0
        if self.spike and time.time() < self.spike["until"]:
            rate *= self.spike["multiplier"]
            hotspot, share = (self.spike["lat"], self.spike["lng"]), 0.9
        elif self.spike:
            self.spike = None
        for _ in range(poisson(self.rng, rate / 60)):
            self._rider_counter += 1
            body = make_request(
                self.rng, f"rdr-{self._rider_counter:06d}", settings.city_lat, settings.city_lng,
                settings.city_radius_km, hotspot, share,
            )
            try:
                await self.rides.create_request(
                    body["rider_id"], body["pickup"]["latitude"], body["pickup"]["longitude"],
                    body["destination"]["latitude"], body["destination"]["longitude"],
                )
            except DuplicateRide:
                pass