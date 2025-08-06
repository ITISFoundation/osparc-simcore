from abc import abstractmethod

from ..models import TaskContext, TaskData, TaskId


class BaseStore:

    @abstractmethod
    async def get_task_data(self, task_id: TaskId) -> TaskData | None:
        """Retrieve a tracked task"""

    @abstractmethod
    async def set_task_data(self, task_id: TaskId, value: TaskData) -> None:
        """Set a tracked task's data"""

    @abstractmethod
    async def list_tasks_data(self) -> list[TaskData]:
        """List all tracked tasks."""

    @abstractmethod
    async def delete_task_data(self, task_id: TaskId) -> None:
        """Delete a tracked task."""

    @abstractmethod
    async def set_as_cancelled(
        self, task_id: TaskId, with_task_context: TaskContext
    ) -> None:
        """Mark a tracked task as cancelled."""

    @abstractmethod
    async def delete_set_as_cancelled(self, task_id: TaskId) -> None:
        """Remove a task from the cancelled tasks."""

    @abstractmethod
    async def get_cancelled(self) -> dict[TaskId, TaskContext]:
        """Get cancelled tasks."""

    @abstractmethod
    async def setup(self) -> None:
        """Setup the store, if needed."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the store, if needed."""
