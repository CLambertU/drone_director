"""Wall-clock adapter. The simulation engine itself advances only fixed simulation steps."""

import asyncio
from time import monotonic

from backend.logging_config import get_logger

logger = get_logger(__name__)


class SimulationRunner:
    def __init__(self, engine, registry):
        self.engine = engine
        self.registry = registry
        self._stop = False
        self._task: asyncio.Task | None = None
        self.error: str | None = None

    def start(self) -> None:
        self._stop = False
        self._task = asyncio.create_task(self._run(), name="tianshu-simulation")

    async def stop(self) -> None:
        self._stop = True
        # Await an in-flight worker instead of cancelling to_thread and closing its DB.
        if self._task is not None:
            await self._task
            self._task = None

    def _advance(self, steps: int) -> None:
        with self.registry.lock:
            if self.engine.running:
                self.engine.step(steps)

    async def _run(self) -> None:
        previous = monotonic()
        accumulated = 0.0
        while not self._stop:
            await asyncio.sleep(0.02)
            current = monotonic()
            elapsed, previous = current - previous, current
            if not self.engine.running:
                accumulated = 0.0
                continue
            accumulated += elapsed * self.engine.speed
            tick = self.engine.tick_seconds
            steps = min(int(accumulated / tick), 5)
            if not steps:
                continue
            try:
                await asyncio.to_thread(self._advance, steps)
                accumulated -= steps * tick
                self.error = None
            except Exception:
                logger.exception("仿真步执行失败，已暂停")
                self.error = "仿真执行失败，请检查服务器日志"
                with self.registry.lock:
                    self.engine.running = False
                    self.engine.alert("runtime", self.error)
                accumulated = 0.0
