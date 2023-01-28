import asyncio
import contextlib
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProgressBar:
    steps: int
    progress: float = 0
    _children: list = field(default_factory=list)
    _parent: Optional["ProgressBar"] = None
    _lock: asyncio.Lock = field(init=False)

    def __post_init__(self):
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.finish()

    async def start(self):
        pass

    async def update(self, value: float = 1):
        async with self._lock:
            self.progress += value
            if self._parent:
                await self._parent.update(value / self.steps)

    async def finish(self):
        pass

    @contextlib.asynccontextmanager
    async def sub_progress(self, steps):
        child = ProgressBar(steps=steps, _parent=self)
        self._children.append(child)
        yield child
