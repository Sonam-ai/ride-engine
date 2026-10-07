import h3

from app.core.config import settings


class SpatialService:
    """Converts coordinates to H3 cells and answers neighborhood questions."""

    def __init__(self, resolution: int | None = None) -> None:
        self.resolution = settings.h3_resolution if resolution is None else resolution
        if not 0 <= self.resolution <= 15:
            raise ValueError("H3 resolution must be between 0 and 15")

    @staticmethod
    def validate_coordinates(latitude: float, longitude: float) -> None:
        if not -90 <= latitude <= 90:
            raise ValueError(f"Invalid latitude: {latitude}")
        if not -180 <= longitude <= 180:
            raise ValueError(f"Invalid longitude: {longitude}")

    @staticmethod
    def validate_cell(cell: str) -> None:
        if not h3.is_valid_cell(cell):
            raise ValueError(f"Invalid H3 cell: {cell}")

    def lat_lng_to_h3(self, latitude: float, longitude: float) -> str:
        self.validate_coordinates(latitude, longitude)
        return h3.latlng_to_cell(latitude, longitude, self.resolution)

    def h3_to_lat_lng(self, cell: str) -> tuple[float, float]:
        self.validate_cell(cell)
        return h3.cell_to_latlng(cell)

    def get_resolution(self, cell: str) -> int:
        self.validate_cell(cell)
        return h3.get_resolution(cell)

    def get_neighbors(self, cell: str, k: int = 1, include_self: bool = False) -> list[str]:
        self.validate_cell(cell)
        cells = set(h3.grid_disk(cell, k))  # h3 returns a list; we want set operations
        if not include_self:
            cells.discard(cell)
        return sorted(cells)

    @staticmethod
    def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Straight-line (great-circle) distance between two coordinates."""
        return h3.great_circle_distance((lat1, lng1), (lat2, lng2), unit="km")

    def get_distance_between_cells(self, cell_a: str, cell_b: str) -> float:
        """Distance in km between the centers of two cells."""
        lat_a, lng_a = self.h3_to_lat_lng(cell_a)
        lat_b, lng_b = self.h3_to_lat_lng(cell_b)
        return self.distance_km(lat_a, lng_a, lat_b, lng_b)

    def get_grid_distance(self, cell_a: str, cell_b: str) -> int:
        """Number of cell steps between two cells (neighbors = 1)."""
        self.validate_cell(cell_a)
        self.validate_cell(cell_b)
        return h3.grid_distance(cell_a, cell_b)


spatial_service = SpatialService()