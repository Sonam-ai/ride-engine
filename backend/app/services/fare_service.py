from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class FareBreakdown:
    distance_km: float
    duration_min: float
    base_fare: float
    distance_fare: float
    time_fare: float
    subtotal: float
    surge_multiplier: float
    total: float
    currency: str


class FareService:
    def __init__(
        self, base_fare: float, per_km_rate: float, per_minute_rate: float,
        road_factor: float, average_speed_kmh: float, currency: str,
    ) -> None:
        self.base_fare, self.per_km_rate, self.per_minute_rate = base_fare, per_km_rate, per_minute_rate
        self.road_factor, self.average_speed_kmh, self.currency = road_factor, average_speed_kmh, currency

    @classmethod
    def from_settings(cls) -> "FareService":
        return cls(
            settings.base_fare, settings.per_km_rate, settings.per_minute_rate,
            settings.road_factor, settings.average_speed_kmh, settings.currency,
        )

    def route_estimate(self, straight_line_km: float) -> tuple[float, float]:
        """No road network: estimate road distance and trip time from the straight line."""
        distance = straight_line_km * self.road_factor
        return round(distance, 3), round(distance / self.average_speed_kmh * 60, 2)

    def estimate(self, distance_km: float, duration_min: float, surge: float) -> FareBreakdown:
        distance_fare = self.per_km_rate * distance_km
        time_fare = self.per_minute_rate * duration_min
        subtotal = self.base_fare + distance_fare + time_fare
        return FareBreakdown(
            distance_km, duration_min, self.base_fare, round(distance_fare, 2), round(time_fare, 2),
            round(subtotal, 2), surge, round(subtotal * surge, 2), self.currency,
        )