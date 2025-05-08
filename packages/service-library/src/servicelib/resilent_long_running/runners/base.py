from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any

from .._models import JobUniqueId, RemoteHandlerName, StartParams


class BaseServerJobInterface(ABC):
    """user can implment this to provide their own execution backend"""

    @abstractmethod
    async def start(
        self,
        name: RemoteHandlerName,
        unique_id: JobUniqueId,
        params: StartParams,
        timeout: timedelta,  # noqa: ASYNC109
    ) -> None:
        """used to start a job"""

    @abstractmethod
    async def remove(self, unique_id: JobUniqueId) -> None:
        """aborts and removes a job"""

    @abstractmethod
    async def is_present(self, unique_id: JobUniqueId) -> bool:
        """returns True if the job exists"""

    @abstractmethod
    async def is_running(self, unique_id: JobUniqueId) -> bool:
        """returns True if the job is currently running"""

    @abstractmethod
    async def get_result(self, unique_id: JobUniqueId) -> Any | None:
        """provides the result of the job once finished"""
