from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import get_container
from app.core.config import settings
from app.core.container import Container

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])


class DemandIn(BaseModel):
    per_minute: float | None = Field(default=None, ge=0, le=300)
    factor: float | None = Field(default=None, gt=0, le=10)  # multiplies current demand


class SpikeIn(BaseModel):
    h3_id: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    duration_seconds: float = Field(default=60, gt=0, le=600)
    multiplier: float = Field(default=4.0, ge=1, le=10)


class DriversIn(BaseModel):
    delta: int = Field(ge=-500, le=500)  # positive adds drivers, negative removes


class ParamsIn(BaseModel):
    matching_interval: float | None = Field(default=None, ge=0.5, le=60)
    surge_sensitivity: float | None = Field(default=None, gt=0, le=3)


def _state(c: Container) -> dict:
    return {
        **c.simulation.state(),
        "matching_interval": settings.matching_interval,
        "surge_sensitivity": c.surge.engine.sensitivity,
    }


@router.get("/state")
async def get_state(c: Container = Depends(get_container)) -> dict:
    return _state(c)


@router.post("/start")
async def start(c: Container = Depends(get_container)) -> dict:
    await c.simulation.start()
    return _state(c)


@router.post("/pause")
async def pause(c: Container = Depends(get_container)) -> dict:
    await c.simulation.pause()
    return _state(c)


@router.post("/reset")
async def reset(c: Container = Depends(get_container)) -> dict:
    await c.simulation.reset()
    return _state(c)


@router.post("/demand")
async def set_demand(body: DemandIn, c: Container = Depends(get_container)) -> dict:
    if body.per_minute is None and body.factor is None:
        raise HTTPException(status_code=400, detail="Provide per_minute or factor")
    c.simulation.set_demand(body.per_minute, body.factor)
    return _state(c)


@router.post("/spike")
async def spike(body: SpikeIn, c: Container = Depends(get_container)) -> dict:
    """Concentrate heavy demand around a zone (or a coordinate, or the city center)."""
    if body.h3_id:
        try:
            lat, lng = c.spatial.h3_to_lat_lng(body.h3_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif body.latitude is not None and body.longitude is not None:
        lat, lng = body.latitude, body.longitude
    else:
        lat, lng = settings.city_lat, settings.city_lng
    await c.simulation.trigger_spike(lat, lng, body.duration_seconds, body.multiplier)
    return _state(c)


@router.post("/drivers")
async def change_drivers(body: DriversIn, c: Container = Depends(get_container)) -> dict:
    await c.simulation.change_drivers(body.delta)
    return _state(c)


@router.post("/params")
async def set_params(body: ParamsIn, c: Container = Depends(get_container)) -> dict:
    if body.matching_interval is not None:
        settings.matching_interval = body.matching_interval
    if body.surge_sensitivity is not None:
        c.surge.engine.sensitivity = body.surge_sensitivity
    return _state(c)


@router.post("/match-now")
async def match_now(c: Container = Depends(get_container)) -> dict:
    """Run one matching batch immediately instead of waiting for the interval."""
    return await c.matching.run_batch()


@router.post("/surge-now")
async def surge_now(c: Container = Depends(get_container)) -> dict:
    """Recompute surge for all zones immediately."""
    results = await c.surge.update_all()
    return {"zones_updated": len(results)}

@router.post("/trip-tick")
async def trip_tick(
    dt_seconds: float = Query(default=settings.trip_tick_seconds, gt=0, le=100000),
    c: Container = Depends(get_container),
) -> dict:
    """Advance all trips by dt_seconds of simulated driving (used by tests and load tests)."""
    await c.trip_sim.tick(dt_seconds)
    return {"ok": True}