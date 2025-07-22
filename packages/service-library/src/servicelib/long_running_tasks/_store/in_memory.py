from ..models import TaskData, TaskId
from .base import BaseStore


class InMemoryStore(BaseStore):
    def __init__(self):
        self._store: dict[TaskId, TaskData] = {}
        self._cancelled_tasks: set[TaskId] = set()

    async def get_task_data(self, key: TaskId) -> TaskData | None:
        return self._store.get(key, None)

    async def set_task_data(self, key: TaskId, value: TaskData) -> None:
        self._store[key] = value

    async def list_tasks_data(self) -> list[TaskData]:
        return list(self._store.values())

    async def delete_task_data(self, key: TaskId) -> None:
        self._store.pop(key, None)

    async def set_as_cancelled(self, key: TaskId) -> None:
        self._cancelled_tasks.add(key)

    async def get_cancelled(self) -> set[TaskId]:
        return self._cancelled_tasks
