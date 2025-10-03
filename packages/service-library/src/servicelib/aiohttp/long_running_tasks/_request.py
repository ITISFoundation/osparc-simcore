from typing import Any, Final

from aiohttp import web

RQT_LONG_RUNNING_TASKS_CONTEXT_APPKEY: Final = web.AppKey(
    "RQT_LONG_RUNNING_TASKS_CONTEXT", dict[str, Any]
)


def get_task_context(request: web.Request) -> dict[str, Any]:
    return request[RQT_LONG_RUNNING_TASKS_CONTEXT_APPKEY]
