from aiohttp import web

from ...long_running_tasks._task import TasksManager
from ._constants import APP_LONG_RUNNING_TASKS_MANAGER_KEY


def get_tasks_manager(app: web.Application) -> TasksManager:
    return app[APP_LONG_RUNNING_TASKS_MANAGER_KEY]
