from abc import ABC, abstractmethod

from .task import TasksManager


class BaseLongRunningManager(ABC):
    """
    Provides a commond inteface for aiohttp and fastapi services
    """

    @property
    @abstractmethod
    def tasks_manager(self) -> TasksManager:
        pass

    @abstractmethod
    async def setup(self) -> None:
        pass

    @abstractmethod
    async def teardown(self) -> None:
        pass
