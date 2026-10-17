import asyncio
import logging
from collections.abc import Callable

from app.core.config import settings
from app.core.container import Container

logger = logging.getLogger("ride_engine.workers")


async def run_periodic(name: str, get_interval: Callable[[], float], func) -> None:
    while True:
        await asyncio.sleep(get_interval())
        try:
            await func()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("worker %s failed", name)


def start_workers(c: Container) -> list[asyncio.Task]:
    specs = [
        ("stale-sweeper", lambda: settings.sweep_interval_seconds, c.drivers.sweep_stale),
        ("surge", lambda: settings.surge_interval_seconds, c.surge.update_all),
        ("matching", lambda: settings.matching_interval, c.matching.run_batch),
        ("trips", lambda: settings.trip_tick_seconds, lambda: c.trip_sim.tick(settings.trip_tick_seconds)),
        ("sim-fleet", lambda: settings.gps_update_interval, c.simulation.fleet_tick),
        ("sim-demand", lambda: 1.0, c.simulation.demand_tick),
    ]
    return [asyncio.create_task(run_periodic(n, i, f), name=n) for n, i, f in specs]