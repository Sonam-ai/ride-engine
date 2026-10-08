from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

ID_PATTERN = r"^[A-Za-z0-9_-]+$"


class DriverStatus(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"
    STALE = "stale"


class DriverLocationIn(BaseModel):
    driver_id: str = Field(min_length=1, max_length=64, pattern=ID_PATTERN)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timestamp: datetime | None = None
    status: DriverStatus | None = None


class LocationAck(BaseModel):
    status: str
    driver_id: str
    h3_cell: str


class DriverOut(BaseModel):
    driver_id: str
    latitude: float
    longitude: float
    h3_cell: str
    status: DriverStatus
    last_updated: float
    trip_id: str | None = None