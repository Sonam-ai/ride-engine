from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.spatial.h3_service import spatial_service

router = APIRouter(prefix="/api/v1/h3", tags=["h3"])


class CellInfo(BaseModel):
    h3_id: str
    resolution: int
    center_lat: float
    center_lng: float
    neighbors: list[str]


def _build_cell_info(cell: str) -> CellInfo:
    lat, lng = spatial_service.h3_to_lat_lng(cell)
    return CellInfo(
        h3_id=cell,
        resolution=spatial_service.get_resolution(cell),
        center_lat=lat,
        center_lng=lng,
        neighbors=spatial_service.get_neighbors(cell),
    )


@router.get("/locate", response_model=CellInfo)
async def locate(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude"),
) -> CellInfo:
    """Which H3 cell contains this coordinate?"""
    return _build_cell_info(spatial_service.lat_lng_to_h3(lat, lng))


@router.get("/cell/{h3_id}", response_model=CellInfo)
async def get_cell(h3_id: str) -> CellInfo:
    """Describe an H3 cell: center, resolution and its 6 neighbors."""
    try:
        return _build_cell_info(h3_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc