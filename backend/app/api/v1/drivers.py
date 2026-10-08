import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_driver_service
from app.schemas.driver import DriverLocationIn, DriverOut, DriverStatus, LocationAck
from app.services.driver_service import DriverLocationService, DriverNotFound, StaleLocationUpdate

router = APIRouter(prefix="/api/v1/drivers", tags=["drivers"])


def _to_epoch(ts: datetime | None) -> float:
    if ts is None:
        return time.time()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.timestamp()


@router.post("/location", response_model=LocationAck)
async def update_location(
    body: DriverLocationIn, service: DriverLocationService = Depends(get_driver_service)
) -> LocationAck:
    """Ingest one GPS ping. Writes to Redis only (never PostgreSQL)."""
    try:
        driver = await service.update_location(
            body.driver_id,
            body.latitude,
            body.longitude,
            _to_epoch(body.timestamp),
            body.status.value if body.status else None,
        )
    except StaleLocationUpdate as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return LocationAck(status="ok", driver_id=driver["driver_id"], h3_cell=driver["h3_cell"])


@router.get("", response_model=list[DriverOut])
async def list_drivers(
    status: DriverStatus | None = None,
    service: DriverLocationService = Depends(get_driver_service),
) -> list[dict]:
    return await service.list_drivers(status.value if status else None)


@router.get("/{driver_id}", response_model=DriverOut)
async def get_driver(
    driver_id: str, service: DriverLocationService = Depends(get_driver_service)
) -> dict:
    try:
        return await service.get_driver(driver_id)
    except DriverNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found") from exc