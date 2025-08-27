from aiohttp import web

from ...long_running_tasks.manager import LongRunningManager
from ...long_running_tasks.models import TaskContext
from ._constants import APP_LONG_RUNNING_MANAGER_KEY
from ._request import get_task_context


class AiohttpLongRunningManager(LongRunningManager):

    @staticmethod
    def get_task_context(request: web.Request) -> TaskContext:
        return get_task_context(request)


def get_long_running_manager(app: web.Application) -> AiohttpLongRunningManager:
    output: AiohttpLongRunningManager = app[APP_LONG_RUNNING_MANAGER_KEY]
    return output
