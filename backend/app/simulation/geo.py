import math
import random

KM_PER_DEG_LAT = 111.32


def km_per_deg_lng(lat: float) -> float:
    return KM_PER_DEG_LAT * math.cos(math.radians(lat))


def offset_point(lat: float, lng: float, north_km: float, east_km: float) -> tuple[float, float]:
    return lat + north_km / KM_PER_DEG_LAT, lng + east_km / km_per_deg_lng(lat)


def bearing_deg(from_lat: float, from_lng: float, to_lat: float, to_lng: float) -> float:
    """Compass direction: 0 = north, 90 = east."""
    north = (to_lat - from_lat) * KM_PER_DEG_LAT
    east = (to_lng - from_lng) * km_per_deg_lng(from_lat)
    return math.degrees(math.atan2(east, north)) % 360


def random_point_in_disk(rng: random.Random, lat: float, lng: float, radius_km: float) -> tuple[float, float]:
    r = radius_km * math.sqrt(rng.random())  # sqrt keeps points evenly spread
    theta = rng.uniform(0, 2 * math.pi)
    return offset_point(lat, lng, r * math.cos(theta), r * math.sin(theta))