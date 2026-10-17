import asyncio

import pytest

from app.core.config import settings
from app.core.container import Container

LAT, LNG = 12.9716, 77.5946
SIM = "/api/v1/simulation"


def test_simulation_starts_with_the_configured_fleet(client):
    assert client.get(f"{SIM}/state").json()["running"] is False
    state = client.post(f"{SIM}/start").json()
    assert state["running"] is True and state["driver_count"] == settings.driver_count
    assert len(client.get("/api/v1/drivers").json()) == settings.driver_count


def test_pause_keeps_the_fleet_but_stops_the_simulation(client):
    client.post(f"{SIM}/start")
    state = client.post(f"{SIM}/pause").json()
    assert state["running"] is False and state["driver_count"] == settings.driver_count


def test_drivers_can_be_added_and_removed(client):
    client.post(f"{SIM}/start")
    assert client.post(f"{SIM}/drivers", json={"delta": 10}).json()["driver_count"] == settings.driver_count + 10
    assert client.post(f"{SIM}/drivers", json={"delta": -20}).json()["driver_count"] == settings.driver_count - 10
    assert len(client.get("/api/v1/drivers").json()) == settings.driver_count - 10


def test_demand_can_be_scaled_or_set(client):
    base = settings.demand_per_minute
    assert client.post(f"{SIM}/demand", json={"factor": 2}).json()["demand_per_minute"] == pytest.approx(base * 2)
    assert client.post(f"{SIM}/demand", json={"per_minute": 5}).json()["demand_per_minute"] == 5
    assert client.post(f"{SIM}/demand", json={}).status_code == 400
    assert client.post(f"{SIM}/demand", json={"per_minute": 1000}).status_code == 422


def test_spike_starts_the_simulation_and_runs_for_a_while(client):
    state = client.post(f"{SIM}/spike", json={"duration_seconds": 30}).json()
    assert state["running"] is True and state["spike_seconds_left"] > 0
    assert client.post(f"{SIM}/spike", json={"h3_id": "bad"}).status_code == 400


def test_reset_wipes_live_state(client):
    client.post(f"{SIM}/start")
    state = client.post(f"{SIM}/reset").json()
    assert state["running"] is False and state["driver_count"] == 0
    assert client.get("/api/v1/drivers").json() == []


def test_parameters_can_be_changed_and_are_validated(client, monkeypatch):
    monkeypatch.setattr(settings, "matching_interval", settings.matching_interval)  # restored after the test
    state = client.post(f"{SIM}/params", json={"matching_interval": 10, "surge_sensitivity": 0.7}).json()
    assert state["matching_interval"] == 10 and state["surge_sensitivity"] == 0.7
    assert client.post(f"{SIM}/params", json={"matching_interval": 0.01}).status_code == 422


def test_websocket_sends_snapshot_then_events_and_survives_reconnect(client):
    with client.websocket_connect("/ws/dashboard") as ws:
        assert ws.receive_json()["event"] == "snapshot"
        client.post("/api/v1/drivers/location", json={"driver_id": "d1", "latitude": LAT, "longitude": LNG})
        msg = ws.receive_json()
        assert msg["event"] == "driver_location_updated"
        assert msg["data"]["driver_id"] == "d1" and "timestamp" in msg
    with client.websocket_connect("/ws/dashboard") as ws:  # reconnect: the snapshot catches us up
        snapshot = ws.receive_json()
        assert [d["driver_id"] for d in snapshot["data"]["drivers"]] == ["d1"]


def test_websocket_streams_ride_events(client):
    with client.websocket_connect("/ws/dashboard") as ws:
        ws.receive_json()  # snapshot
        client.post(
            "/api/v1/rides/request",
            json={
                "rider_id": "r1",
                "pickup": {"latitude": LAT, "longitude": LNG},
                "destination": {"latitude": LAT + 0.03, "longitude": LNG + 0.03},
            },
        )
        msg = ws.receive_json()
        assert msg["event"] == "ride_requested" and msg["data"]["rider_id"] == "r1"


def test_simulated_demand_and_movement_without_http():
    async def scenario():
        c = await Container.create("memory", "sqlite+aiosqlite:///:memory:")
        try:
            await c.simulation.start()
            before = {d["driver_id"]: (d["latitude"], d["longitude"]) for d in await c.drivers.list_drivers()}
            await c.simulation.fleet_tick()
            after = {d["driver_id"]: (d["latitude"], d["longitude"]) for d in await c.drivers.list_drivers()}
            assert before != after  # drivers moved

            c.simulation.set_demand(300, None)
            for _ in range(5):
                await c.simulation.demand_tick()
            assert len(await c.rides.list_open()) > 0
        finally:
            await c.close()

    asyncio.run(scenario())