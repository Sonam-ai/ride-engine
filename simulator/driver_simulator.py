"""Simulates a fleet of drivers sending GPS pings to the backend.

Run from the backend folder (venv active):
    python ..\\simulator\\driver_simulator.py
"""
import asyncio
import math
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from geo_utils import bearing_deg, distance_km, offset_point, random_point_in_disk


@dataclass
class SimDriver:
    driver_id: str
    lat: float
    lng: float
    heading: float  # degrees, 0 = north
    speed_kmh: float
    online: bool = True
    pending_status: str | None = None  # sent once, then cleared

    def step(self, dt_seconds, rng, center_lat, center_lng, radius_km) -> None:
        """Move one tick: gentle heading changes, turn back toward the center at the edge."""
        if distance_km(self.lat, self.lng, center_lat, center_lng) > radius_km:
            self.heading = bearing_deg(self.lat, self.lng, center_lat, center_lng)
        else:
            self.heading = (self.heading + rng.gauss(0, 20)) % 360
        dist = self.speed_kmh * dt_seconds / 3600
        h = math.radians(self.heading)
        self.lat, self.lng = offset_point(
            self.lat, self.lng, dist * math.cos(h), dist * math.sin(h)
        )

    def maybe_toggle_online(self, rng) -> None:
        if self.online and rng.random() < 0.01:
            self.online, self.pending_status = False, "offline"
        elif not self.online and rng.random() < 0.10:
            self.online, self.pending_status = True, "available"


def make_fleet(count, center_lat, center_lng, radius_km, rng, speed_range=(15.0, 35.0)):
    fleet = []
    for i in range(count):
        lat, lng = random_point_in_disk(rng, center_lat, center_lng, radius_km)
        fleet.append(
            SimDriver(f"drv-{i + 1:03d}", lat, lng, rng.uniform(0, 360), rng.uniform(*speed_range))
        )
    return fleet


async def _ping(client: httpx.AsyncClient, d: SimDriver) -> float | None:
    body = {
        "driver_id": d.driver_id,
        "latitude": d.lat,
        "longitude": d.lng,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if d.pending_status:
        body["status"] = d.pending_status
        d.pending_status = None
    start = time.perf_counter()
    try:
        r = await client.post("/api/v1/drivers/location", json=body)
        r.raise_for_status()
    except httpx.HTTPError:
        return None
    return (time.perf_counter() - start) * 1000


async def run() -> None:
    api = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
    count = int(os.getenv("DRIVER_COUNT", "100"))
    interval = float(os.getenv("GPS_UPDATE_INTERVAL", "3"))
    lat = float(os.getenv("CITY_LAT", "12.9716"))
    lng = float(os.getenv("CITY_LNG", "77.5946"))
    radius = float(os.getenv("CITY_RADIUS_KM", "6"))
    seed = int(os.getenv("SIMULATION_SEED", "42"))

    rng = random.Random(seed)
    fleet = make_fleet(count, lat, lng, radius, rng)
    print(f"Simulating {count} drivers around ({lat}, {lng}), ping every {interval}s, seed {seed}")

    async with httpx.AsyncClient(base_url=api, timeout=5.0) as client:
        tick = 0
        while True:
            started = time.perf_counter()
            latencies = await asyncio.gather(*(_ping(client, d) for d in fleet))
            ok = [x for x in latencies if x is not None]
            tick += 1
            avg = sum(ok) / len(ok) if ok else 0.0
            print(f"tick {tick}: {len(ok)} ok, {len(latencies) - len(ok)} failed, avg {avg:.1f} ms")
            for d in fleet:
                d.step(interval, rng, lat, lng, radius)
                d.maybe_toggle_online(rng)
            await asyncio.sleep(max(0.0, interval - (time.perf_counter() - started)))


if __name__ == "__main__":
    asyncio.run(run())