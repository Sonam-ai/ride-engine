from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.container import Container

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])


@router.post("/match-now")
async def match_now(c: Container = Depends(get_container)) -> dict:
    """Run one matching batch immediately instead of waiting for the interval."""
    return await c.matching.run_batch()


@router.post("/surge-now")
async def surge_now(c: Container = Depends(get_container)) -> dict:
    """Recompute surge for all zones immediately."""
    results = await c.surge.update_all()
    return {"zones_updated": len(results)}