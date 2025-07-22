from abc import abstractmethod

from ..models import TaskContext, TaskData, TaskId


class BaseStore:

    @abstractmethod
    async def get_task_data(self, task_id: TaskId) -> TaskData | None:
        """Retrieve a tracked task by its key."""

    @abstractmethod
    async def set_task_data(self, task_id: TaskId, value: TaskData) -> None:
        """Set a tracked task with its key."""

    @abstractmethod
    async def list_tasks_data(self) -> list[TaskData]:
        """List all tracked tasks."""

    @abstractmethod
    async def delete_task_data(self, task_id: TaskId) -> None:
        """Delete a tracked task by its key."""

    @abstractmethod
    async def set_as_cancelled(
        self, task_id: TaskId, with_task_context: TaskContext | None
    ) -> None:
        """Mark a tracked task as cancelled."""

    @abstractmethod
    async def get_cancelled(self) -> dict[TaskId, TaskContext | None]:
        """Get cancelled tasks."""
