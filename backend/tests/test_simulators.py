import random

from driver_simulator import SimDriver, make_fleet
from geo_utils import distance_km
from rider_simulator import make_request

LAT, LNG = 12.9716, 77.5946


def test_fleet_is_reproducible_with_same_seed():
    a = make_fleet(10, LAT, LNG, 6, random.Random(1))
    b = make_fleet(10, LAT, LNG, 6, random.Random(1))
    assert [(d.lat, d.lng) for d in a] == [(d.lat, d.lng) for d in b]


def test_driver_moves_the_expected_distance():
    d = SimDriver("x", LAT, LNG, heading=90, speed_kmh=36.0)
    before = (d.lat, d.lng)
    d.step(10, random.Random(0), LAT, LNG, 6)
    assert abs(distance_km(*before, d.lat, d.lng) - 0.1) < 0.005  # 36 km/h * 10 s


def test_drivers_stay_inside_the_city():
    rng = random.Random(2)
    fleet = make_fleet(20, LAT, LNG, 6, rng)
    for _ in range(500):
        for d in fleet:
            d.step(3, rng, LAT, LNG, 6)
    assert all(distance_km(d.lat, d.lng, LAT, LNG) < 6.5 for d in fleet)


def test_hotspot_requests_cluster_near_hotspot():
    rng = random.Random(3)
    spot = (LAT + 0.02, LNG + 0.02)
    for i in range(50):
        req = make_request(rng, f"r{i}", LAT, LNG, 6, hotspot=spot, hotspot_share=1.0)
        p = req["pickup"]
        assert distance_km(p["latitude"], p["longitude"], *spot) < 0.85


def test_requests_without_hotspot_stay_in_city():
    rng = random.Random(4)
    for i in range(50):
        p = make_request(rng, f"r{i}", LAT, LNG, 6)["pickup"]
        assert distance_km(p["latitude"], p["longitude"], LAT, LNG) < 6.05