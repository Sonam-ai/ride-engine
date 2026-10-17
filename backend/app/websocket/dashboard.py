import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("ride_engine.websocket")
router = APIRouter()


@router.websocket("/ws/dashboard")
async def dashboard(websocket: WebSocket) -> None:
    container = websocket.app.state.container
    await websocket.accept()
    queue = container.events.subscribe()  # subscribe BEFORE the snapshot so no event is missed
    tasks: set[asyncio.Task] = set()
    try:
        drivers = await container.drivers.list_drivers()
        await websocket.send_json(
            {"event": "snapshot", "timestamp": datetime.now(timezone.utc).isoformat(), "data": {"drivers": drivers}}
        )

        async def sender() -> None:
            while True:
                await websocket.send_json(await queue.get())

        async def receiver() -> None:
            while True:
                await websocket.receive_text()  # raises WebSocketDisconnect when the client leaves

        tasks = {asyncio.create_task(sender()), asyncio.create_task(receiver())}
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            error = task.exception()
            if error and not isinstance(error, WebSocketDisconnect):
                logger.info("websocket closed: %r", error)
    except (WebSocketDisconnect, RuntimeError):
        pass  # client went away
    finally:
        for task in tasks:
            task.cancel()
        container.events.unsubscribe(queue)