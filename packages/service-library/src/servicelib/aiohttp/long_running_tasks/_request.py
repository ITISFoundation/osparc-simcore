from typing import Any

from aiohttp import web

from ._constants import RQT_LONG_RUNNING_TASKS_CONTEXT_KEY


def get_task_context(request: web.Request) -> dict[str, Any]:
    output: dict[str, Any] = request[RQT_LONG_RUNNING_TASKS_CONTEXT_KEY]
    return output
