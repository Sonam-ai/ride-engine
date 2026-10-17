import math
import random
from dataclasses import dataclass

from app.simulation.geo import bearing_deg, offset_point, random_point_in_disk
from app.spatial.distance import haversine_km


@dataclass
class SimDriver:
    driver_id: str
    lat: float
    lng: float
    heading: float  # degrees, 0 = north
    speed_kmh: float
    online: bool = True
    pending_status: str | None = None  # sent once with the next ping, then cleared

    def step(self, dt_seconds: float, rng: random.Random, center_lat: float, center_lng: float, radius_km: float) -> None:
        """Wander: small heading changes, turn back toward the center at the city edge."""
        if haversine_km(self.lat, self.lng, center_lat, center_lng) > radius_km:
            self.heading = bearing_deg(self.lat, self.lng, center_lat, center_lng)
        else:
            self.heading = (self.heading + rng.gauss(0, 20)) % 360
        dist = self.speed_kmh * dt_seconds / 3600
        h = math.radians(self.heading)
        self.lat, self.lng = offset_point(self.lat, self.lng, dist * math.cos(h), dist * math.sin(h))

    def maybe_toggle_online(self, rng: random.Random) -> None:
        if self.online and rng.random() < 0.01:
            self.online, self.pending_status = False, "offline"
        elif not self.online and rng.random() < 0.10:
            self.online, self.pending_status = True, "available"


def make_fleet(count: int, center_lat: float, center_lng: float, radius_km: float, rng: random.Random) -> list[SimDriver]:
    fleet = []
    for i in range(count):
        lat, lng = random_point_in_disk(rng, center_lat, center_lng, radius_km)
        fleet.append(SimDriver(f"drv-{i + 1:03d}", lat, lng, rng.uniform(0, 360), rng.uniform(15.0, 35.0)))
    return fleet