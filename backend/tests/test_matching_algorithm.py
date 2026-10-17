from app.algorithms.matching import (
    DriverPoint, MatchingConfig, RequestPoint, match_global, match_nearest_first,
)
from geo_utils import offset_point

LAT, LNG = 12.9716, 77.5946
cfg = MatchingConfig(max_distance_km=10.0, k_nearest=8)


def at(east_km: float, north_km: float = 0.0):
    return offset_point(LAT, LNG, north_km, east_km)


def total_km(assignments):
    return sum(a.distance_km for a in assignments)


def test_global_matching_beats_first_come_nearest_driver():
    drivers = [DriverPoint("D1", *at(0)), DriverPoint("D2", *at(4))]
    requests = [RequestPoint("R1", *at(1), 0), RequestPoint("R2", *at(-1), 0)]

    greedy = match_nearest_first(requests, drivers, cfg)
    optimal = match_global(requests, drivers, cfg)

    # R1 grabs its nearest driver D1 and strands R2 with far-away D2 (1 + 5 km) ...
    assert {a.ride_id: a.driver_id for a in greedy} == {"R1": "D1", "R2": "D2"}
    # ... while the optimum swaps them (3 + 1 km).
    assert {a.ride_id: a.driver_id for a in optimal} == {"R1": "D2", "R2": "D1"}
    assert total_km(optimal) < total_km(greedy)


def test_drivers_beyond_max_distance_are_never_matched():
    drivers = [DriverPoint("far", *at(25))]
    requests = [RequestPoint("R1", *at(0), 0)]
    assert match_global(requests, drivers, cfg) == []


def test_longer_waiting_rider_wins_when_drivers_are_scarce():
    drivers = [DriverPoint("D1", *at(1))]
    requests = [RequestPoint("fresh", *at(0), 10), RequestPoint("waiting", *at(0), 300)]
    result = match_global(requests, drivers, cfg)
    assert [a.ride_id for a in result] == ["waiting"]


def test_each_driver_and_request_is_used_at_most_once():
    drivers = [DriverPoint(f"D{i}", *at(i * 0.3)) for i in range(3)]
    requests = [RequestPoint(f"R{i}", *at(i * 0.2, 0.1), 0) for i in range(5)]
    result = match_global(requests, drivers, cfg)
    assert len(result) == 3
    assert len({a.driver_id for a in result}) == 3
    assert len({a.ride_id for a in result}) == 3


def test_no_drivers_or_no_requests_gives_no_matches():
    assert match_global([], [DriverPoint("D", LAT, LNG)], cfg) == []
    assert match_global([RequestPoint("R", LAT, LNG, 0)], [], cfg) == []