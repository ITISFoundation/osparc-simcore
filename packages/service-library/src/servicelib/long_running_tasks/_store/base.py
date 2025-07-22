from abc import abstractmethod

from ..models import TaskId, TrackedTask


class BaseStore:

    @abstractmethod
    async def get_task(self, key: TaskId) -> TrackedTask | None:
        """Retrieve a tracked task by its key."""

    @abstractmethod
    async def set_task(self, key: TaskId, value: TrackedTask) -> None:
        """Set a tracked task with its key."""

    @abstractmethod
    async def list_tasks(self) -> list[TrackedTask]:
        """List all tracked tasks."""

    @abstractmethod
    async def delete_task(self, key: TaskId) -> None:
        """Delete a tracked task by its key."""

    @abstractmethod
    async def set_as_cancelled(self, key: TaskId) -> None:
        """Mark a tracked task as cancelled."""

    @abstractmethod
    async def get_cancelled(self) -> set[TaskId]:
        """Get cancelled tasks."""
