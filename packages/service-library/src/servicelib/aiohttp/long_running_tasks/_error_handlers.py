from aiohttp import web

from ...json_serialization import json_dumps
from ...long_running_tasks._errors import (
    TaskCancelledError,
    TaskNotCompletedError,
    TaskNotFoundError,
)


@web.middleware
async def base_long_running_error_handler(request, handler):
    try:
        return await handler(request)
    except (TaskNotFoundError, TaskNotCompletedError) as exc:
        error_fields = dict(code=exc.code, message=f"{exc}")
        raise web.HTTPNotFound(
            reason=f"{json_dumps(error_fields)}",
        ) from exc
    except TaskCancelledError as exc:
        # NOTE: only use-case would be accessing an already cancelled task
        # which should not happen, so we return a conflict
        error_fields = dict(code=exc.code, message=f"{exc}")
        raise web.HTTPConflict(reason=f"{json_dumps(error_fields)}") from exc
