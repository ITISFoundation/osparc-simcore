from typing import Any, Final

from aiohttp import web

LONG_RUNNING_TASKS_CONTEXT_REQKEY: Final = f"{__name__}.LONG_RUNNING_TASKS_CONTEXT"


def get_task_context(request: web.Request) -> dict[str, Any]:
    ctx: dict[str, Any] = request[LONG_RUNNING_TASKS_CONTEXT_REQKEY]
    return ctx
