from aiohttp import web

from ...long_running_tasks.base_long_running_manager import BaseLongRunningManager
from ...long_running_tasks.models import TaskContext
from ._constants import APP_LONG_RUNNING_MANAGER_KEY
from ._request import get_task_context


class AiohttpLongRunningManager(BaseLongRunningManager):

    @staticmethod
    def get_task_context(request: web.Request) -> TaskContext:
        return get_task_context(request)


def get_long_running_manager(app: web.Application) -> AiohttpLongRunningManager:
    output: AiohttpLongRunningManager = app[APP_LONG_RUNNING_MANAGER_KEY]
    return output
