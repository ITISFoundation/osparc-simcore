from aiohttp import web

from ...long_running_tasks.task import TasksManager
from ._constants import APP_LONG_RUNNING_TASKS_MANAGER_KEY

# NOTE: figure out how to remove these and expose them differently if possible


def get_tasks_manager(app: web.Application) -> TasksManager:
    output: TasksManager = app[APP_LONG_RUNNING_TASKS_MANAGER_KEY]
    return output
