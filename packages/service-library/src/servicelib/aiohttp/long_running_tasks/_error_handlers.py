from aiohttp import web

from ...json_serialization import json_dumps
from ...long_running_tasks._errors import TaskNotCompletedError, TaskNotFoundError


@web.middleware
async def base_long_running_error_handler(request, handler):
    try:
        return await handler(request)
    except (TaskNotFoundError, TaskNotCompletedError) as exc:
        error_fields = dict(code=exc.code, message=f"{exc}")
        raise web.HTTPNotFound(
            reason=f"{json_dumps(error_fields)}",
        ) from exc
