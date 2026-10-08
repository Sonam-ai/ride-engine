from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.driver import ID_PATTERN


class RideStatus(str, Enum):
    REQUESTED = "REQUESTED"
    QUOTED = "QUOTED"
    MATCHING = "MATCHING"
    ASSIGNED = "ASSIGNED"
    DRIVER_EN_ROUTE = "DRIVER_EN_ROUTE"
    DRIVER_ARRIVED = "DRIVER_ARRIVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Point(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class RideRequestIn(BaseModel):
    rider_id: str = Field(min_length=1, max_length=64, pattern=ID_PATTERN)
    pickup: Point
    destination: Point


class RideOut(BaseModel):
    ride_id: str
    rider_id: str
    pickup_lat: float
    pickup_lng: float
    pickup_h3: str
    dest_lat: float
    dest_lng: float
    created_at: float
    status: RideStatus
    quoted_fare: float | None = None
    surge_multiplier: float | None = None
    driver_id: str | None = None