from ..models import TaskId, TrackedTask
from .base import BaseStore


class InMemoryStore(BaseStore):
    def __init__(self):
        self._store: dict[TaskId, TrackedTask] = {}

    async def get(self, key: TaskId) -> TrackedTask | None:
        return self._store.get(key, None)

    async def set(self, key: TaskId, value: TrackedTask) -> None:
        self._store[key] = value

    async def list(self) -> list[TrackedTask]:
        return list(self._store.values())

    async def delete(self, key: TaskId) -> None:
        self._store.pop(key, None)
