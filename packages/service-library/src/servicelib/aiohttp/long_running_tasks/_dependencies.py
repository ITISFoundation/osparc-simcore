from typing import Any

from aiohttp import web

from ...long_running_tasks.task import TasksManager
from ._constants import (
    APP_LONG_RUNNING_TASKS_MANAGER_KEY,
    RQT_LONG_RUNNING_TASKS_CONTEXT_KEY,
)


def get_tasks_manager(app: web.Application) -> TasksManager:
    output: TasksManager = app[APP_LONG_RUNNING_TASKS_MANAGER_KEY]
    return output


def get_task_context(request: web.Request) -> dict[str, Any]:
    output: dict[str, Any] = request[RQT_LONG_RUNNING_TASKS_CONTEXT_KEY]
    return output


def create_task_name_from_request(request: web.Request) -> str:
    return f"{request.method} {request.rel_url}"
