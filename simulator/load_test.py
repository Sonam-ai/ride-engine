"""HTTP load test against a running backend.

From the backend folder with the venv active:
    python ..\\simulator\\load_test.py --drivers 100 --duration 30 --rides-per-min 60
WARNING: it RESETS the live simulation state (Redis) first.
"""
import argparse
import asyncio
import json
import os
import random
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

import httpx
import websockets
from geo_utils import random_point_in_disk

API = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
LAT = float(os.getenv("CITY_LAT", "12.9716"))
LNG = float(os.getenv("CITY_LNG", "77.5946"))
RADIUS = float(os.getenv("CITY_RADIUS_KM", "6"))


def pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * p / 100))]


class Metrics:
    def __init__(self) -> None:
        self.lat: dict[str, list[float]] = defaultdict(list)
        self.errors: Counter = Counter()
        self.assigned = 0


async def timed_post(client: httpx.AsyncClient, m: Metrics, name: str, path: str, body=None, params=None):
    start = time.perf_counter()
    try:
        r = await client.post(path, json=body, params=params)
        r.raise_for_status()
    except httpx.HTTPError:
        m.errors[name] += 1
        return None
    m.lat[name].append((time.perf_counter() - start) * 1000)
    return r


async def ws_listener(lags: list[float], stop: asyncio.Event) -> None:
    url = API.replace("http", "ws", 1) + "/ws/dashboard"
    try:
        async with websockets.connect(url) as ws:
            while not stop.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1)
                except asyncio.TimeoutError:
                    continue
                msg = json.loads(raw)
                if msg.get("event") == "driver_location_updated":
                    sent = datetime.fromisoformat(msg["timestamp"])
                    lags.append((datetime.now(timezone.utc) - sent).total_seconds() * 1000)
    except Exception as exc:  # report but do not crash the test
        print("websocket listener stopped:", exc)


async def run(drivers: int, duration: float, rides_per_min: float, interval: float) -> None:
    rng = random.Random(42)
    m = Metrics()
    ws_lags: list[float] = []
    stop = asyncio.Event()
    limits = httpx.Limits(max_connections=200, max_keepalive_connections=100)

    async with httpx.AsyncClient(base_url=API, timeout=15, limits=limits) as client:
        await client.post("/api/v1/simulation/reset")  # empty and paused
        fleet = [(f"load-{i:04d}", *random_point_in_disk(rng, LAT, LNG, RADIUS)) for i in range(drivers)]
        ws_task = asyncio.create_task(ws_listener(ws_lags, stop))
        await asyncio.sleep(0.5)

        async def ride_loop() -> None:
            n = 0
            while True:
                n += 1
                plat, plng = random_point_in_disk(rng, LAT, LNG, RADIUS)
                dlat, dlng = random_point_in_disk(rng, LAT, LNG, RADIUS)
                trip = {
                    "pickup": {"latitude": plat, "longitude": plng},
                    "destination": {"latitude": dlat, "longitude": dlng},
                }
                await timed_post(client, m, "quote", "/api/v1/rides/quote", trip)
                await timed_post(client, m, "ride_request", "/api/v1/rides/request", {"rider_id": f"load-r{n:06d}", **trip})
                await asyncio.sleep(rng.expovariate(rides_per_min / 60))

        async def match_loop() -> None:
            while True:
                await asyncio.sleep(5)
                start = time.perf_counter()
                r = await timed_post(client, m, "matching_wall", "/api/v1/simulation/match-now")
                if r is not None:
                    body = r.json()
                    m.lat["matching_server"].append(body["elapsed_ms"])
                    m.assigned += body["assigned"]
                _ = start

        async def trip_loop() -> None:
            while True:
                await asyncio.sleep(1)
                await timed_post(client, m, "trip_tick", "/api/v1/simulation/trip-tick", params={"dt_seconds": 1})

        side = [asyncio.create_task(f()) for f in (ride_loop, match_loop, trip_loop)]
        started = time.perf_counter()
        rounds = 0
        while time.perf_counter() - started < duration:
            t0 = time.perf_counter()
            await asyncio.gather(
                *(
                    timed_post(
                        client, m, "gps_ingest", "/api/v1/drivers/location",
                        {"driver_id": d, "latitude": lat, "longitude": lng},
                    )
                    for d, lat, lng in fleet
                )
            )
            rounds += 1
            await asyncio.sleep(max(0.0, interval - (time.perf_counter() - t0)))

        stop.set()
        for task in side:
            task.cancel()
        await asyncio.gather(*side, return_exceptions=True)
        await ws_task
        stats = (await client.get("/api/v1/stats")).json()

    m.lat["websocket_lag"] = ws_lags
    print(f"\nLoad test: {drivers} drivers, GPS every {interval}s, ~{rides_per_min} rides/min, {duration}s\n")
    print("| Metric | samples | p50 ms | p95 ms | p99 ms | max ms | errors |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for name in ("gps_ingest", "quote", "ride_request", "matching_server", "matching_wall", "websocket_lag"):
        v = m.lat.get(name, [])
        print(
            f"| {name} | {len(v)} | {pct(v, 50):.1f} | {pct(v, 95):.1f} | {pct(v, 99):.1f} | "
            f"{max(v) if v else float('nan'):.1f} | {m.errors[name]} |"
        )
    print(f"\nGPS rounds completed: {rounds} (target {int(duration / interval)})")
    print(f"Assigned in matching batches: {m.assigned} | completed trips: {stats['completed_trips']} "
          f"| pending: {stats['open_requests']} | average surge: x{stats['average_surge']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--drivers", type=int, default=100)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--rides-per-min", type=float, default=60)
    parser.add_argument("--interval", type=float, default=3.0)
    args = parser.parse_args()
    asyncio.run(run(args.drivers, args.duration, args.rides_per_min, args.interval))