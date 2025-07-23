from ..models import TaskContext, TaskData, TaskId
from .base import BaseStore


class InMemoryStore(BaseStore):
    def __init__(self, *args, **kwargs):
        _ = args
        _ = kwargs
        self._tasks_data: dict[TaskId, TaskData] = {}
        self._cancelled_tasks: dict[TaskId, TaskContext | None] = {}

    async def setup(self) -> None:
        pass

    async def teardown(self) -> None:
        pass

    async def get_task_data(self, task_id: TaskId) -> TaskData | None:
        return self._tasks_data.get(task_id, None)

    async def set_task_data(self, task_id: TaskId, value: TaskData) -> None:
        self._tasks_data[task_id] = value

    async def list_tasks_data(self) -> list[TaskData]:
        return list(self._tasks_data.values())

    async def delete_task_data(self, task_id: TaskId) -> None:
        self._tasks_data.pop(task_id, None)

    async def set_as_cancelled(
        self, task_id: TaskId, with_task_context: TaskContext | None
    ) -> None:
        self._cancelled_tasks[task_id] = with_task_context

    async def get_cancelled(self) -> dict[TaskId, TaskContext | None]:
        return self._cancelled_tasks
