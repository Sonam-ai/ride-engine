"""Generates ride requests with configurable demand.

Examples (from the backend folder, venv active):
    python ..\\simulator\\rider_simulator.py --pattern normal --duration 60
    python ..\\simulator\\rider_simulator.py --pattern high --hotspot 12.9716,77.5946 --hotspot-share 0.8
"""
import argparse
import asyncio
import os
import random

import httpx
from geo_utils import distance_km, random_point_in_disk

PATTERNS = {"low": 6, "normal": 20, "high": 50, "spike": 120}  # requests per minute


def make_request(
    rng, rider_id, center_lat, center_lng, radius_km,
    hotspot=None, hotspot_share=0.0, hotspot_radius_km=0.8,
) -> dict:
    if hotspot and rng.random() < hotspot_share:
        plat, plng = random_point_in_disk(rng, hotspot[0], hotspot[1], hotspot_radius_km)
    else:
        plat, plng = random_point_in_disk(rng, center_lat, center_lng, radius_km)
    for _ in range(10):  # destination at least 1.5 km away
        dlat, dlng = random_point_in_disk(rng, center_lat, center_lng, radius_km)
        if distance_km(plat, plng, dlat, dlng) >= 1.5:
            break
    return {
        "rider_id": rider_id,
        "pickup": {"latitude": plat, "longitude": plng},
        "destination": {"latitude": dlat, "longitude": dlng},
    }


async def run(pattern: str, duration: float, hotspot, hotspot_share: float) -> None:
    api = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
    lat = float(os.getenv("CITY_LAT", "12.9716"))
    lng = float(os.getenv("CITY_LNG", "77.5946"))
    radius = float(os.getenv("CITY_RADIUS_KM", "6"))
    rng = random.Random(int(os.getenv("SIMULATION_SEED", "42")))
    per_minute = PATTERNS[pattern]
    print(f"Pattern '{pattern}': ~{per_minute} requests/min for {duration}s, hotspot={hotspot}")

    sent = failed = 0
    elapsed = 0.0
    async with httpx.AsyncClient(base_url=api, timeout=5.0) as client:
        while elapsed < duration:
            rider_id = f"rdr-{sent + failed + 1:05d}"
            body = make_request(rng, rider_id, lat, lng, radius, hotspot, hotspot_share)
            try:
                r = await client.post("/api/v1/rides/request", json=body)
                r.raise_for_status()
                sent += 1
            except httpx.HTTPError:
                failed += 1
            # Poisson arrivals: exponential gaps between requests
            gap = rng.expovariate(per_minute / 60)
            await asyncio.sleep(gap)
            elapsed += gap
    print(f"done: {sent} requests created, {failed} failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern", choices=PATTERNS, default="normal")
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--hotspot", help="lat,lng of a demand hotspot")
    parser.add_argument("--hotspot-share", type=float, default=0.7)
    args = parser.parse_args()
    spot = tuple(float(x) for x in args.hotspot.split(",")) if args.hotspot else None
    asyncio.run(run(args.pattern, args.duration, spot, args.hotspot_share))