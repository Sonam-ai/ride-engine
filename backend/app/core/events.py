import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger("ride_engine.events")


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self, maxsize: int = 1000) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    async def publish(self, event: str, data: dict) -> None:
        message = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), "data": data}
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("dropping %s event for a slow subscriber", event)