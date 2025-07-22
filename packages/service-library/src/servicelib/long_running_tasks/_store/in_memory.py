from ..models import TaskId, TrackedTask
from .base import BaseStore


class InMemoryStore(BaseStore):
    def __init__(self):
        self._store: dict[TaskId, TrackedTask] = {}
        self._cancelled_tasks: set[TaskId] = set()

    async def get_task(self, key: TaskId) -> TrackedTask | None:
        return self._store.get(key, None)

    async def set_task(self, key: TaskId, value: TrackedTask) -> None:
        self._store[key] = value

    async def list_tasks(self) -> list[TrackedTask]:
        return list(self._store.values())

    async def delete_task(self, key: TaskId) -> None:
        self._store.pop(key, None)

    async def set_as_cancelled(self, key: TaskId) -> None:
        self._cancelled_tasks.add(key)

    async def get_cancelled(self) -> set[TaskId]:
        return self._cancelled_tasks
