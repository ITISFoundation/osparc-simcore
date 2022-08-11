from aiohttp import web

from ...long_running_tasks._task import TaskManager
from ._constants import APP_LONG_RUNNING_TASKS_MANAGER_KEY


def get_task_manager(app: web.Application) -> TaskManager:
    return app[APP_LONG_RUNNING_TASKS_MANAGER_KEY]
