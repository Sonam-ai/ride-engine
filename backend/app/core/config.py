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
    database_url: str = "sqlite+aiosqlite:///./rides.db"
    driver_stale_seconds: int = 30
    sweep_interval_seconds: float = 10.0

    # fares
    currency: str = "INR"
    base_fare: float = 50.0
    per_km_rate: float = 12.0
    per_minute_rate: float = 2.0
    road_factor: float = 1.3  # road distance ~ 1.3 x straight line
    average_speed_kmh: float = 25.0

    # surge
    surge_min: float = 1.0
    surge_max: float = 4.0
    surge_alpha: float = 0.3
    surge_local_weight: float = 0.7
    surge_neighbor_weight: float = 0.3
    surge_sensitivity: float = 0.35
    surge_balanced_ratio: float = 1.0
    surge_min_supply: int = 1
    surge_interval_seconds: float = 5.0
    surge_history_min_delta: float = 0.05

    # matching
    matching_interval: float = 5.0
    max_pickup_distance_km: float = 5.0
    matching_k_nearest: int = 8
    pickup_time_weight: float = 1.0
    distance_weight: float = 0.5
    wait_priority_weight: float = 0.2
    request_timeout_seconds: float = 120.0

    # trip simulation (drivers drive to pickup and destination)
    trip_tick_seconds: float = 1.0
    trip_time_scale: float = 8.0  # simulated time runs 8x faster than real time
    trip_sim_moves_busy_drivers: bool = True

        # built-in simulation
    driver_count: int = 100
    gps_update_interval: float = 3.0
    city_radius_km: float = 6.0
    simulation_seed: int = 42
    simulation_autostart: bool = False
    demand_per_minute: float = 20.0

    # browsers allowed to call the API (the dashboard)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")


settings = Settings()