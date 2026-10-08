import pytest

from app.services.fare_service import FareService

fare = FareService(50.0, 12.0, 2.0, 1.3, 25.0, "INR")


def test_fare_formula():
    f = fare.estimate(distance_km=10, duration_min=20, surge=1.5)
    assert f.subtotal == 210.0  # 50 + 12*10 + 2*20
    assert f.total == 315.0


def test_no_surge_means_subtotal():
    assert fare.estimate(5, 10, 1.0).total == fare.estimate(5, 10, 1.0).subtotal


def test_route_estimate_uses_road_factor_and_speed():
    distance, minutes = fare.route_estimate(10.0)
    assert distance == pytest.approx(13.0)
    assert minutes == pytest.approx(31.2)