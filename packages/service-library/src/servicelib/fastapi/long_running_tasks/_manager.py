import datetime

from fastapi import FastAPI
from settings_library.redis import RedisSettings

from ...long_running_tasks.base_long_running_manager import BaseLongRunningManager
from ...long_running_tasks.task import RedisNamespace, TasksManager


class FastAPILongRunningManager(BaseLongRunningManager):
    def __init__(
        self,
        app: FastAPI,
        stale_task_check_interval: datetime.timedelta,
        stale_task_detect_timeout: datetime.timedelta,
        redis_settings: RedisSettings,
        redis_namespace: RedisNamespace,
    ):
        self._app = app
        self._tasks_manager = TasksManager(
            stale_task_check_interval=stale_task_check_interval,
            stale_task_detect_timeout=stale_task_detect_timeout,
            redis_settings=redis_settings,
            redis_namespace=redis_namespace,
        )

    @property
    def tasks_manager(self) -> TasksManager:
        return self._tasks_manager

    async def setup(self) -> None:
        await self._tasks_manager.setup()

    async def teardown(self) -> None:
        await self._tasks_manager.teardown()
