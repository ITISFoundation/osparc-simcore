from abc import abstractmethod

from ..models import TaskId, TrackedTask


class BaseStore:

    @abstractmethod
    async def get(self, key: TaskId) -> TrackedTask | None:
        """Retrieve a tracked task by its key."""

    @abstractmethod
    async def set(self, key: TaskId, value: TrackedTask) -> None:
        """Set a tracked task with its key."""

    @abstractmethod
    async def list(self) -> list[TrackedTask]:
        """List all tracked tasks."""

    @abstractmethod
    async def delete(self, key: TaskId) -> None:
        """Delete a tracked task by its key."""
