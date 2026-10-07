from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_locate_returns_expected_cell():
    r = client.get("/api/v1/h3/locate", params={"lat": 12.9716, "lng": 77.5946})
    assert r.status_code == 200
    body = r.json()
    assert body["h3_id"] == "8860145b49fffff"
    assert body["resolution"] == 8
    assert len(body["neighbors"]) == 6


def test_locate_rejects_bad_latitude():
    r = client.get("/api/v1/h3/locate", params={"lat": 95, "lng": 77})
    assert r.status_code == 422


def test_cell_lookup_works():
    r = client.get("/api/v1/h3/cell/8860145b49fffff")
    assert r.status_code == 200
    assert r.json()["h3_id"] == "8860145b49fffff"


def test_cell_lookup_rejects_garbage():
    r = client.get("/api/v1/h3/cell/not-a-cell")
    assert r.status_code == 400