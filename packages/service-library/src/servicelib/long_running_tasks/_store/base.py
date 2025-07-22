from abc import abstractmethod

from ..models import TaskData, TaskId


class BaseStore:

    @abstractmethod
    async def get_task_data(self, key: TaskId) -> TaskData | None:
        """Retrieve a tracked task by its key."""

    @abstractmethod
    async def set_task_data(self, key: TaskId, value: TaskData) -> None:
        """Set a tracked task with its key."""

    @abstractmethod
    async def list_tasks_data(self) -> list[TaskData]:
        """List all tracked tasks."""

    @abstractmethod
    async def delete_task_data(self, key: TaskId) -> None:
        """Delete a tracked task by its key."""

    @abstractmethod
    async def set_as_cancelled(self, key: TaskId) -> None:
        """Mark a tracked task as cancelled."""

    @abstractmethod
    async def get_cancelled(self) -> set[TaskId]:
        """Get cancelled tasks."""
