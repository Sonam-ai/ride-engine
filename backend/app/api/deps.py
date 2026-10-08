from fastapi import Depends, Request
from redis.asyncio import Redis

from app.services.driver_service import DriverLocationService
from app.services.ride_service import RideRequestService
from app.services.zone_service import ZoneService
from app.spatial.h3_service import spatial_service


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_driver_service(redis: Redis = Depends(get_redis)) -> DriverLocationService:
    return DriverLocationService(redis, spatial_service)


def get_ride_service(redis: Redis = Depends(get_redis)) -> RideRequestService:
    return RideRequestService(redis, spatial_service)


def get_zone_service(redis: Redis = Depends(get_redis)) -> ZoneService:
    return ZoneService(redis, spatial_service)