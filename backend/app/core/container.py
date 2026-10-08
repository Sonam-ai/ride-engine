from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.algorithms.matching import MatchingConfig
from app.algorithms.surge import SurgePricingEngine
from app.core.database import create_db
from app.core.events import EventBus
from app.core.redis_client import create_redis
from app.models.models import Base
from app.services.driver_service import DriverLocationService
from app.services.fare_service import FareService
from app.services.matching_service import MatchingService
from app.services.persistence import PersistenceService
from app.services.quote_service import QuoteService
from app.services.ride_service import RideRequestService
from app.services.stats_service import StatsService
from app.services.surge_service import SurgeService
from app.services.trip_service import TripService
from app.services.zone_service import ZoneService
from app.spatial.h3_service import SpatialService, spatial_service
from app.workers.trip_worker import TripSimulator


@dataclass
class Container:
    redis: Redis
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    events: EventBus
    spatial: SpatialService
    persistence: PersistenceService
    drivers: DriverLocationService
    surge: SurgeService
    quotes: QuoteService
    rides: RideRequestService
    zones: ZoneService
    trips: TripService
    matching: MatchingService
    trip_sim: TripSimulator
    stats: StatsService

    @classmethod
    async def create(cls, redis_url: str | None = None, database_url: str | None = None) -> "Container":
        redis = create_redis(redis_url)
        engine, session_factory = create_db(database_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        events = EventBus()
        spatial = spatial_service
        persistence = PersistenceService(session_factory)
        drivers = DriverLocationService(redis, spatial)
        surge = SurgeService(redis, spatial, SurgePricingEngine.from_settings(), persistence, events)
        quotes = QuoteService(surge, FareService.from_settings(), spatial)
        rides = RideRequestService(redis, spatial, quotes, persistence, events)
        trips = TripService(redis, persistence, events)
        return cls(
            redis=redis, engine=engine, session_factory=session_factory, events=events, spatial=spatial,
            persistence=persistence, drivers=drivers, surge=surge, quotes=quotes, rides=rides,
            zones=ZoneService(redis, spatial), trips=trips,
            matching=MatchingService(drivers, rides, trips, MatchingConfig.from_settings()),
            trip_sim=TripSimulator(redis, trips, drivers),
            stats=StatsService(redis, drivers),
        )

    async def close(self) -> None:
        await self.redis.aclose()
        await self.engine.dispose()