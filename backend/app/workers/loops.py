import asyncio
import logging

from app.core.config import settings
from app.core.container import Container

logger = logging.getLogger("ride_engine.workers")


async def run_periodic(name: str, interval: float, func) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            await func()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("worker %s failed", name)


def start_workers(c: Container) -> list[asyncio.Task]:
    specs = [
        ("stale-sweeper", settings.sweep_interval_seconds, c.drivers.sweep_stale),
        ("surge", settings.surge_interval_seconds, c.surge.update_all),
        ("matching", settings.matching_interval, c.matching.run_batch),
        ("trips", settings.trip_tick_seconds, lambda: c.trip_sim.tick(settings.trip_tick_seconds)),
    ]
    return [asyncio.create_task(run_periodic(n, i, f), name=n) for n, i, f in specs]