import random

from app.simulation.geo import random_point_in_disk
from app.spatial.distance import haversine_km


def make_request(
    rng: random.Random, rider_id: str, center_lat: float, center_lng: float, radius_km: float,
    hotspot: tuple[float, float] | None = None, hotspot_share: float = 0.0, hotspot_radius_km: float = 0.8,
) -> dict:
    if hotspot and rng.random() < hotspot_share:
        plat, plng = random_point_in_disk(rng, hotspot[0], hotspot[1], hotspot_radius_km)
    else:
        plat, plng = random_point_in_disk(rng, center_lat, center_lng, radius_km)
    for _ in range(10):  # destination at least 1.5 km away
        dlat, dlng = random_point_in_disk(rng, center_lat, center_lng, radius_km)
        if haversine_km(plat, plng, dlat, dlng) >= 1.5:
            break
    return {
        "rider_id": rider_id,
        "pickup": {"latitude": plat, "longitude": plng},
        "destination": {"latitude": dlat, "longitude": dlng},
    }