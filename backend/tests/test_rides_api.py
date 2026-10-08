LAT, LNG = 12.9716, 77.5946
CELL = "8860145b49fffff"


def payload(rider="r1", lat=LAT, lng=LNG):
    return {
        "rider_id": rider,
        "pickup": {"latitude": lat, "longitude": lng},
        "destination": {"latitude": LAT + 0.03, "longitude": LNG + 0.03},
    }


def test_request_is_created_in_the_right_cell(client):
    r = client.post("/api/v1/rides/request", json=payload())
    assert r.status_code == 201
    body = r.json()
    assert body["pickup_h3"] == CELL
    assert body["status"] == "REQUESTED"
    assert client.get(f"/api/v1/zones/{CELL}").json()["open_requests"] == 1


def test_get_ride(client):
    ride_id = client.post("/api/v1/rides/request", json=payload()).json()["ride_id"]
    assert client.get(f"/api/v1/rides/{ride_id}").json()["rider_id"] == "r1"


def test_duplicate_open_ride_is_rejected(client):
    assert client.post("/api/v1/rides/request", json=payload()).status_code == 201
    assert client.post("/api/v1/rides/request", json=payload()).status_code == 409


def test_cancel_removes_demand_and_frees_rider(client):
    ride_id = client.post("/api/v1/rides/request", json=payload()).json()["ride_id"]
    r = client.post(f"/api/v1/rides/{ride_id}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"
    assert client.get(f"/api/v1/zones/{CELL}").json()["open_requests"] == 0
    assert client.post("/api/v1/rides/request", json=payload()).status_code == 201


def test_cancelling_twice_is_409(client):
    ride_id = client.post("/api/v1/rides/request", json=payload()).json()["ride_id"]
    client.post(f"/api/v1/rides/{ride_id}/cancel")
    assert client.post(f"/api/v1/rides/{ride_id}/cancel").status_code == 409


def test_unknown_ride_is_404(client):
    assert client.get("/api/v1/rides/nope").status_code == 404


def test_bad_pickup_coordinates_are_422(client):
    assert client.post("/api/v1/rides/request", json=payload(lat=120)).status_code == 422


def test_zone_list_shows_demand_and_supply(client):
    client.post(
        "/api/v1/drivers/location", json={"driver_id": "d1", "latitude": LAT, "longitude": LNG}
    )
    client.post("/api/v1/rides/request", json=payload("r1"))
    client.post("/api/v1/rides/request", json=payload("r2"))
    zones = client.get("/api/v1/zones").json()
    assert zones[0]["available_drivers"] == 1
    assert zones[0]["open_requests"] == 2
    assert zones[0]["demand_supply_ratio"] == 2.0


def test_invalid_zone_id_is_400(client):
    assert client.get("/api/v1/zones/not-a-cell").status_code == 400