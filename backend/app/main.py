from fastapi import FastAPI

from app.api.v1 import h3 as h3_routes
from app.core.config import settings

app = FastAPI(title="Ride Engine")
app.include_router(h3_routes.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "city": settings.city_name}