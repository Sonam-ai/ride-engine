from app.services.fare_service import FareService
from app.services.surge_service import SurgeService
from app.spatial.distance import haversine_km
from app.spatial.h3_service import SpatialService


class QuoteService:
    def __init__(self, surge: SurgeService, fare: FareService, spatial: SpatialService) -> None:
        self.surge, self.fare, self.spatial = surge, fare, spatial

    async def quote(self, pickup_lat: float, pickup_lng: float, dest_lat: float, dest_lng: float) -> dict:
        cell = self.spatial.lat_lng_to_h3(pickup_lat, pickup_lng)
        self.spatial.validate_coordinates(dest_lat, dest_lng)
        distance, duration = self.fare.route_estimate(haversine_km(pickup_lat, pickup_lng, dest_lat, dest_lng))
        result, supply, demand = await self.surge.preview(cell)
        fare = self.fare.estimate(distance, duration, result.surge)
        return {
            "pickup_h3": cell,
            "supply": supply,
            "demand": demand,
            "distance_km": distance,
            "duration_min": duration,
            "base_fare": fare.base_fare,
            "surge_multiplier": result.surge,
            "estimated_fare": fare.total,
            "currency": fare.currency,
        }