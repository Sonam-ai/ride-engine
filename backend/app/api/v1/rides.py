from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_ride_service
from app.schemas.ride import RideOut, RideRequestIn
from app.services.ride_service import (
    DuplicateRide,
    InvalidRideState,
    RideNotFound,
    RideRequestService,
)

router = APIRouter(prefix="/api/v1/rides", tags=["rides"])


@router.post("/request", response_model=RideOut, status_code=201)
async def request_ride(
    body: RideRequestIn, service: RideRequestService = Depends(get_ride_service)
) -> dict:
    try:
        return await service.create_request(
            body.rider_id,
            body.pickup.latitude,
            body.pickup.longitude,
            body.destination.latitude,
            body.destination.longitude,
        )
    except DuplicateRide as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[RideOut])
async def list_open_rides(service: RideRequestService = Depends(get_ride_service)) -> list[dict]:
    """Rides currently waiting for a driver."""
    return await service.list_open()


@router.get("/{ride_id}", response_model=RideOut)
async def get_ride(ride_id: str, service: RideRequestService = Depends(get_ride_service)) -> dict:
    try:
        return await service.get_ride(ride_id)
    except RideNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Ride {ride_id} not found") from exc


@router.post("/{ride_id}/cancel", response_model=RideOut)
async def cancel_ride(ride_id: str, service: RideRequestService = Depends(get_ride_service)) -> dict:
    try:
        return await service.cancel(ride_id)
    except RideNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Ride {ride_id} not found") from exc
    except InvalidRideState as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc