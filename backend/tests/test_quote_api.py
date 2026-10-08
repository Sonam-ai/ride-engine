LAT, LNG = 12.9716, 77.5946
TRIP = {
    "pickup": {"latitude": LAT, "longitude": LNG},
    "destination": {"latitude": LAT + 0.03, "longitude": LNG + 0.03},
}


def request_ride(client, rider):
    return client.post("/api/v1/rides/request", json={"rider_id": rider, **TRIP})


def test_quote_without_demand_has_no_surge(client):
    r = client.post("/api/v1/rides/quote", json=TRIP)
    assert r.status_code == 200
    body = r.json()
    assert body["surge_multiplier"] == 1.0
    assert body["currency"] == "INR"
    assert body["estimated_fare"] > body["base_fare"]


def test_quote_rises_when_demand_exceeds_supply(client):
    client.post("/api/v1/drivers/location", json={"driver_id": "d1", "latitude": LAT, "longitude": LNG})
    calm = client.post("/api/v1/rides/quote", json=TRIP).json()
    for i in range(6):
        assert request_ride(client, f"r{i}").status_code == 201
    busy = client.post("/api/v1/rides/quote", json=TRIP).json()
    assert busy["demand"] == 6 and busy["supply"] == 1
    assert busy["surge_multiplier"] > 1.2
    assert busy["estimated_fare"] > calm["estimated_fare"]


def test_ride_stores_the_quoted_price(client):
    ride = request_ride(client, "r1").json()
    assert ride["status"] == "QUOTED"
    assert ride["quoted_fare"] > 0
    assert ride["surge_multiplier"] == 1.0


def test_quote_rejects_bad_coordinates(client):
    bad = {**TRIP, "pickup": {"latitude": 200, "longitude": 0}}
    assert client.post("/api/v1/rides/quote", json=bad).status_code == 422


def test_complete_requires_an_in_progress_trip(client):
    ride_id = request_ride(client, "r1").json()["ride_id"]
    assert client.post(f"/api/v1/rides/{ride_id}/complete").status_code == 409


def test_stats_endpoint_shape(client):
    body = client.get("/api/v1/stats").json()
    assert body["drivers"]["total"] == 0
    assert body["completed_trips"] == 0
    assert body["highest_surge_zone"] is None