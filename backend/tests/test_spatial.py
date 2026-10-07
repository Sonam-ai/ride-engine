import pytest

from app.spatial.h3_service import SpatialService

LAT, LNG = 12.9716, 77.5946
spatial = SpatialService(resolution=8)  # fixed, so tests don't depend on .env


def test_known_point_gives_known_cell():
    assert spatial.lat_lng_to_h3(LAT, LNG) == "8860145b49fffff"


def test_cell_center_maps_back_to_same_cell():
    cell = spatial.lat_lng_to_h3(LAT, LNG)
    lat, lng = spatial.h3_to_lat_lng(cell)
    assert spatial.lat_lng_to_h3(lat, lng) == cell


def test_neighbors_are_six_and_exclude_self():
    cell = spatial.lat_lng_to_h3(LAT, LNG)
    neighbors = spatial.get_neighbors(cell)
    assert len(neighbors) == 6
    assert cell not in neighbors


def test_neighbors_are_one_step_away():
    cell = spatial.lat_lng_to_h3(LAT, LNG)
    for n in spatial.get_neighbors(cell):
        assert spatial.get_grid_distance(cell, n) == 1


def test_neighbor_centers_are_about_one_km_apart():
    cell = spatial.lat_lng_to_h3(LAT, LNG)
    for n in spatial.get_neighbors(cell):
        assert 0.7 < spatial.get_distance_between_cells(cell, n) < 1.2


def test_distance_to_self_is_zero():
    cell = spatial.lat_lng_to_h3(LAT, LNG)
    assert spatial.get_distance_between_cells(cell, cell) == 0


def test_one_degree_latitude_is_about_111_km():
    d = spatial.distance_km(12.0, 77.0, 13.0, 77.0)
    assert abs(d - 111.2) < 0.5


@pytest.mark.parametrize("lat,lng", [(91, 0), (-91, 0), (0, 181), (0, -181)])
def test_invalid_coordinates_rejected(lat, lng):
    with pytest.raises(ValueError):
        spatial.lat_lng_to_h3(lat, lng)


def test_invalid_cell_rejected():
    with pytest.raises(ValueError):
        spatial.get_neighbors("not-a-cell")
        