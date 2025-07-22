from ..models import TaskId, TrackedTask
from .base import BaseStore


class InMemoryStore(BaseStore):
    def __init__(self):
        self._store: dict[TaskId, TrackedTask] = {}
        self._cancelled_tasks: dict[TaskId, bool] = {}

    async def get(self, key: TaskId) -> TrackedTask | None:
        return self._store.get(key, None)

    async def set(self, key: TaskId, value: TrackedTask) -> None:
        self._store[key] = value

    async def list(self) -> list[TrackedTask]:
        return list(self._store.values())

    async def delete(self, key: TaskId) -> None:
        self._store.pop(key, None)

    async def set_cancelled(self, key: TaskId) -> None:
        self._cancelled_tasks[key] = True

    async def is_cancelled(self, key: TaskId) -> bool:
        return self._cancelled_tasks.get(key, False)
