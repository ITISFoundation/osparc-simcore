import logging

from aiohttp import web
from common_library.json_serialization import json_dumps

from ...long_running_tasks._errors import (
    TaskCancelledError,
    TaskNotCompletedError,
    TaskNotFoundError,
)

_logger = logging.getLogger(__name__)


@web.middleware
async def base_long_running_error_handler(request, handler):
    try:
        return await handler(request)
    except (TaskNotFoundError, TaskNotCompletedError) as exc:
        _logger.debug("", exc_info=True)
        error_fields = dict(code=exc.code, message=f"{exc}")
        raise web.HTTPNotFound(
            reason=f"{json_dumps(error_fields)}",
        ) from exc
    except TaskCancelledError as exc:
        # NOTE: only use-case would be accessing an already cancelled task
        # which should not happen, so we return a conflict
        _logger.debug("", exc_info=True)
        error_fields = dict(code=exc.code, message=f"{exc}")
        raise web.HTTPConflict(reason=f"{json_dumps(error_fields)}") from exc
