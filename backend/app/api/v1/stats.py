from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.container import Container

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@router.get("")
async def get_stats(c: Container = Depends(get_container)) -> dict:
    """System-wide numbers for the dashboard side panel."""
    return await c.stats.get()