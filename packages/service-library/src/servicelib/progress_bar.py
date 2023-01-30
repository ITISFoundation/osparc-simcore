import asyncio
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProgressData:
    steps: int
    _continuous_progress: float = 0
    _children: list = field(default_factory=list)
    _parent: Optional["ProgressData"] = None
    _lock: asyncio.Lock = field(init=False)

    def __post_init__(self) -> None:
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "ProgressData":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.finish()

    async def start(self) -> None:
        pass

    async def update(self, value: float = 1) -> None:
        async with self._lock:
            new_progress_value = self._continuous_progress + value
            if round(new_progress_value) > self.steps:
                raise ValueError(
                    f"Progress cannot be updated by {value} as it cannot be higher than {self.steps}"
                )
            self._continuous_progress += value
            if self._parent:
                await self._parent.update(value / self.steps)

    async def finish(self) -> None:
        pass

    def sub_progress(self, steps) -> "ProgressData":
        if len(self._children) == self.steps:
            raise RuntimeError(
                "Too many sub progresses created already. Wrong usage of the progress bar"
            )
        child = ProgressData(steps=steps, _parent=self)
        self._children.append(child)
        return child
