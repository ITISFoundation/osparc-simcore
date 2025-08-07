from typing import Final

from servicelib.long_running_tasks.base_long_running_manager import (
    BaseLongRunningManager,
)
from servicelib.long_running_tasks.task import TasksManager


class NoWebAppLongRunningManager(BaseLongRunningManager):
    def __init__(self, tasks_manager: TasksManager):
        self._tasks_manager = tasks_manager

    @property
    def tasks_manager(self) -> TasksManager:
        return self._tasks_manager

    def setup(self) -> None:
        pass

    async def teardown(self) -> None:
        pass


TEST_CHECK_STALE_INTERVAL_S: Final[float] = 1
