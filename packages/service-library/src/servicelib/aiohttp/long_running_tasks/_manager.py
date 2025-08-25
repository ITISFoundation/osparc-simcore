from aiohttp import web

from ...long_running_tasks.models import TaskContext
from ...long_running_tasks.server_long_running_manager import ServerLongRunningManager
from ._constants import APP_LONG_RUNNING_MANAGER_KEY
from ._request import get_task_context


class AiohttpLongRunningManager(ServerLongRunningManager):

    @staticmethod
    def get_task_context(request: web.Request) -> TaskContext:
        return get_task_context(request)


def get_long_running_manager(app: web.Application) -> AiohttpLongRunningManager:
    output: AiohttpLongRunningManager = app[APP_LONG_RUNNING_MANAGER_KEY]
    return output
