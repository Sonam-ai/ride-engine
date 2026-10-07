from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    city_name: str = "Bangalore"
    city_lat: float = 12.9716
    city_lng: float = 77.5946
    h3_resolution: int = 8
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")


settings = Settings()