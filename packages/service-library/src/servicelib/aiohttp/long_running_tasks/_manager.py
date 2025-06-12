import datetime

from aiohttp import web

from ...long_running_tasks.base_long_running_manager import BaseLongRunningManager
from ...long_running_tasks.task import TaskContext, TasksManager
from ._constants import APP_LONG_RUNNING_MANAGER_KEY
from ._dependencies import get_task_context


class AiohttpLongRunningManager(BaseLongRunningManager):
    def __init__(
        self,
        app: web.Application,
        stale_task_check_interval: datetime.timedelta,
        stale_task_detect_timeout: datetime.timedelta,
    ):
        self._app = app
        self._tasks_manager = TasksManager(
            stale_task_check_interval=stale_task_check_interval,
            stale_task_detect_timeout=stale_task_detect_timeout,
        )

    @property
    def tasks_manager(self) -> TasksManager:
        return self._tasks_manager

    async def setup(self) -> None:
        await self._tasks_manager.setup()

    async def teardown(self) -> None:
        await self._tasks_manager.teardown()

    @staticmethod
    def get_task_context(request: web.Request) -> TaskContext:
        return get_task_context(request)


def get_long_running_manager(app: web.Application) -> AiohttpLongRunningManager:
    output: AiohttpLongRunningManager = app[APP_LONG_RUNNING_MANAGER_KEY]
    return output
