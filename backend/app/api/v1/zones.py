from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_zone_service
from app.schemas.zone import ZoneOut
from app.services.zone_service import ZoneService

router = APIRouter(prefix="/api/v1/zones", tags=["zones"])


@router.get("", response_model=list[ZoneOut])
async def list_zones(service: ZoneService = Depends(get_zone_service)) -> list[dict]:
    """Active zones with supply and demand (feeds the dashboard heatmap)."""
    return await service.list_zones()


@router.get("/{h3_id}", response_model=ZoneOut)
async def get_zone(h3_id: str, service: ZoneService = Depends(get_zone_service)) -> dict:
    try:
        return await service.get_zone(h3_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc