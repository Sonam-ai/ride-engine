import math

import numpy as np

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, a)))


def haversine_matrix_km(lat1, lng1, lat2, lng2) -> np.ndarray:
    """All pairwise distances at once. lat1/lng1 have shape (R,1), lat2/lng2 shape (1,D)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def move_towards(lat: float, lng: float, target_lat: float, target_lng: float, step_km: float):
    """Move up to step_km toward the target. Returns (lat, lng, arrived)."""
    dist = haversine_km(lat, lng, target_lat, target_lng)
    if dist <= step_km or dist == 0:
        return target_lat, target_lng, True
    f = step_km / dist
    return lat + (target_lat - lat) * f, lng + (target_lng - lng) * f, False