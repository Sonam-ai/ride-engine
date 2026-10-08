from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]  # .../ride-engine


class Settings(BaseSettings):
    city_name: str = "Bangalore"
    city_lat: float = 12.9716
    city_lng: float = 77.5946
    h3_resolution: int = 8
    log_level: str = "INFO"

    redis_url: str = "memory"
    driver_stale_seconds: int = 30
    sweep_interval_seconds: int = 10

    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")


settings = Settings()