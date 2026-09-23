"""Bounded full-state stream. A fresh connection always receives a complete snapshot."""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/api/ws")
async def stream(socket: WebSocket):
    await socket.accept()
    engine = socket.app.state.engine
    previous_environment = None
    sequence = 0
    try:
        while True:
            snapshot = await asyncio.to_thread(engine.snapshot, include_environment=False)
            version = snapshot.get("environment_version")
            if sequence == 0 or version != previous_environment:
                snapshot = await asyncio.to_thread(engine.snapshot, include_environment=True)
                previous_environment = snapshot.get("environment_version")
            sequence += 1
            await asyncio.wait_for(socket.send_json({
                "type": "snapshot", "sequence": sequence, "data": snapshot,
            }), timeout=5.0)
            # Simulation advances independently; a slow subscriber cannot accumulate a queue.
            await asyncio.sleep(0.2)
    except (WebSocketDisconnect, asyncio.TimeoutError, OSError, RuntimeError):
        return
