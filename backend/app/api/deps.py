from fastapi import Depends, Request

from app.core.container import Container
from app.services.driver_service import DriverLocationService
from app.services.quote_service import QuoteService
from app.services.ride_service import RideRequestService
from app.services.trip_service import TripService
from app.services.zone_service import ZoneService


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_driver_service(c: Container = Depends(get_container)) -> DriverLocationService:
    return c.drivers


def get_ride_service(c: Container = Depends(get_container)) -> RideRequestService:
    return c.rides


def get_zone_service(c: Container = Depends(get_container)) -> ZoneService:
    return c.zones


def get_quote_service(c: Container = Depends(get_container)) -> QuoteService:
    return c.quotes


def get_trip_service(c: Container = Depends(get_container)) -> TripService:
    return c.trips