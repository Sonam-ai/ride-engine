LAT, LNG = 12.9716, 77.5946


def test_end_to_end_ride_through_the_api(client):
    # 1. a driver reports a position about 1 km from the rider
    r = client.post(
        "/api/v1/drivers/location", json={"driver_id": "d1", "latitude": LAT, "longitude": LNG + 0.01}
    )
    assert r.status_code == 200

    # 2. quote, then request a ride
    trip = {
        "pickup": {"latitude": LAT, "longitude": LNG},
        "destination": {"latitude": LAT + 0.03, "longitude": LNG + 0.03},
    }
    assert client.post("/api/v1/rides/quote", json=trip).json()["estimated_fare"] > 0
    ride = client.post("/api/v1/rides/request", json={"rider_id": "r1", **trip}).json()
    ride_id = ride["ride_id"]
    assert ride["status"] == "QUOTED"

    # 3. matching assigns the driver
    batch = client.post("/api/v1/simulation/match-now").json()
    assert batch["assigned"] == 1
    assigned = client.get(f"/api/v1/rides/{ride_id}").json()
    assert assigned["status"] == "ASSIGNED" and assigned["driver_id"] == "d1"
    assert client.get("/api/v1/drivers/d1").json()["status"] == "busy"

    # 4. the driver drives to the rider, then to the destination
    for _ in range(5):
        client.post("/api/v1/simulation/trip-tick", params={"dt_seconds": 10000})
    done = client.get(f"/api/v1/rides/{ride_id}").json()
    assert done["status"] == "COMPLETED"
    assert client.get("/api/v1/drivers/d1").json()["status"] == "available"

    # 5. everything was persisted and is traceable
    response = client.get(f"/api/v1/rides/{ride_id}/events")
    assert response.status_code == 200, response.text
    events = [e["event_type"] for e in response.json()]
    assert events == [
        "ride_created", "quote_generated", "matching_started", "driver_assigned",
        "driver_en_route", "driver_arrived", "trip_started", "trip_completed", "fare_calculated",
    ]
    stats = client.get("/api/v1/stats").json()
    assert stats["completed_trips"] == 1 and stats["total_matches"] == 1