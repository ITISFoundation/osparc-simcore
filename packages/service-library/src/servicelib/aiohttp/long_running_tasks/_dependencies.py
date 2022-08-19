from typing import Any

from aiohttp import web

from ...long_running_tasks._task import TasksManager
from ._constants import (
    APP_LONG_RUNNING_TASKS_MANAGER_KEY,
    RQT_LONG_RUNNING_TASKS_CONTEXT_KEY,
)


def get_tasks_manager(app: web.Application) -> TasksManager:
    return app[APP_LONG_RUNNING_TASKS_MANAGER_KEY]


def get_task_context(request: web.Request) -> dict[str, Any]:
    return request[RQT_LONG_RUNNING_TASKS_CONTEXT_KEY]
