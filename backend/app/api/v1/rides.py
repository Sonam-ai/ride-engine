from fastapi import APIRouter, Depends, HTTPException

from app.algorithms.state_machine import InvalidTransition
from app.api.deps import get_quote_service, get_ride_service, get_trip_service
from app.schemas.ride import QuoteOut, QuoteRequestIn, RideOut, RideRequestIn
from app.services.quote_service import QuoteService
from app.services.ride_service import DuplicateRide, RideNotFound, RideRequestService
from app.services.trip_service import TripService

router = APIRouter(prefix="/api/v1/rides", tags=["rides"])


@router.post("/quote", response_model=QuoteOut)
async def quote_ride(body: QuoteRequestIn, quotes: QuoteService = Depends(get_quote_service)) -> dict:
    """Price a trip without creating a ride: pickup cell, supply, demand, smoothed surge, fare."""
    return await quotes.quote(
        body.pickup.latitude, body.pickup.longitude, body.destination.latitude, body.destination.longitude
    )


@router.post("/request", response_model=RideOut, status_code=201)
async def request_ride(body: RideRequestIn, service: RideRequestService = Depends(get_ride_service)) -> dict:
    try:
        return await service.create_request(
            body.rider_id, body.pickup.latitude, body.pickup.longitude,
            body.destination.latitude, body.destination.longitude,
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
async def cancel_ride(ride_id: str, trips: TripService = Depends(get_trip_service)) -> dict:
    try:
        return await trips.cancel(ride_id)
    except RideNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Ride {ride_id} not found") from exc
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{ride_id}/complete", response_model=RideOut)
async def complete_ride(ride_id: str, trips: TripService = Depends(get_trip_service)) -> dict:
    """Finish a trip manually (only valid while IN_PROGRESS)."""
    try:
        return await trips.advance(ride_id, "COMPLETED")
    except RideNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Ride {ride_id} not found") from exc
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc