from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(title="Ride Engine")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "city": settings.city_name}