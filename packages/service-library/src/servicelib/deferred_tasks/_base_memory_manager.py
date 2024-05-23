from abc import ABC, abstractmethod

from ._models import TaskUID
from ._task_schedule import TaskSchedule


class BaseMemoryManager(ABC):
    """Basis for implementing memory management to keep track ledger entries"""

    @abstractmethod
    async def get_task_unique_identifier(self) -> TaskUID:
        """provides a unique identifier for the task"""

    @abstractmethod
    async def get(self, task_uid: TaskUID) -> TaskSchedule | None:
        """returns the given entry for provided task unique id"""

    @abstractmethod
    async def save(self, task_uid: TaskUID, task_schedule: TaskSchedule) -> None:
        """overwrites the entry at the given task unique id with the provided entry"""

    @abstractmethod
    async def remove(self, task_uid: TaskUID) -> None:
        """removes the entry for the provided task unique id"""

    @abstractmethod
    async def list(self) -> list[TaskSchedule]:
        """returns a list with all the currently existing entries"""
