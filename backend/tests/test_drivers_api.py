import asyncio
import time
from datetime import datetime, timedelta, timezone

from app.core.redis_client import create_redis
from app.services.driver_service import DriverLocationService
from app.spatial.h3_service import SpatialService

LAT, LNG = 12.9716, 77.5946
CELL = "8860145b49fffff"


def ping(client, driver_id="d1", lat=LAT, lng=LNG, ts=None, status=None):
    body = {"driver_id": driver_id, "latitude": lat, "longitude": lng}
    if ts:
        body["timestamp"] = ts.isoformat()
    if status:
        body["status"] = status
    return client.post("/api/v1/drivers/location", json=body)


def zone(client, cell):
    return client.get(f"/api/v1/zones/{cell}").json()


def test_location_update_returns_cell(client):
    r = ping(client)
    assert r.status_code == 200
    assert r.json()["h3_cell"] == CELL


def test_get_driver_returns_stored_state(client):
    ping(client)
    body = client.get("/api/v1/drivers/d1").json()
    assert body["latitude"] == LAT
    assert body["status"] == "available"


def test_unknown_driver_is_404(client):
    assert client.get("/api/v1/drivers/nobody").status_code == 404


def test_invalid_latitude_is_422(client):
    assert ping(client, lat=95).status_code == 422


def test_stale_update_is_rejected(client):
    now = datetime.now(timezone.utc)
    assert ping(client, ts=now).status_code == 200
    assert ping(client, ts=now - timedelta(seconds=60)).status_code == 409


def test_moving_driver_changes_cell_membership(client):
    ping(client)
    far = ping(client, lat=LAT + 0.05)
    new_cell = far.json()["h3_cell"]
    assert new_cell != CELL
    assert zone(client, CELL)["total_drivers"] == 0
    assert zone(client, new_cell)["total_drivers"] == 1


def test_offline_driver_is_not_supply(client):
    ping(client)
    ping(client, status="offline")
    z = zone(client, CELL)
    assert z["total_drivers"] == 1
    assert z["available_drivers"] == 0


def test_list_drivers_can_filter_by_status(client):
    ping(client, "d1")
    ping(client, "d2")
    ping(client, "d3", status="offline")
    assert len(client.get("/api/v1/drivers").json()) == 3
    assert len(client.get("/api/v1/drivers", params={"status": "available"}).json()) == 2


def test_sweeper_marks_silent_drivers_stale_and_revives_them():
    async def scenario():
        redis = create_redis()
        svc = DriverLocationService(redis, SpatialService(resolution=8))
        await svc.update_location("d1", LAT, LNG, timestamp=time.time() - 100)
        assert await svc.sweep_stale() == 1
        assert (await svc.get_driver("d1"))["status"] == "stale"
        assert await redis.scard(f"cell:{CELL}:available") == 0
        await svc.update_location("d1", LAT, LNG, timestamp=time.time())
        assert (await svc.get_driver("d1"))["status"] == "available"
        await redis.aclose()

    asyncio.run(scenario())