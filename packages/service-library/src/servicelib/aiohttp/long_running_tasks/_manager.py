from typing import Final

from aiohttp import web

from ...long_running_tasks.manager import LongRunningManager
from ...long_running_tasks.models import TaskContext
from ._request import get_task_context


class AiohttpLongRunningManager(LongRunningManager):

    @staticmethod
    def get_task_context(request: web.Request) -> TaskContext:
        return get_task_context(request)


LONG_RUNNING_MANAGER_APPKEY: Final = web.AppKey(
    "LONG_RUNNING_MANAGER", AiohttpLongRunningManager
)


def get_long_running_manager(app: web.Application) -> AiohttpLongRunningManager:
    return app[LONG_RUNNING_MANAGER_APPKEY]
