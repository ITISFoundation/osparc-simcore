from aiohttp import web
from models_library.utils.fastapi_encoders import jsonable_encoder

from ...long_running_tasks._errors import BaseLongRunningError, TaskNotFoundError


@web.middleware
async def base_long_running_error_handler(request, handler):
    try:
        return await handler(request)
    except BaseLongRunningError as exc:
        error_fields = dict(code=exc.code, message=f"{exc}")
        if isinstance(exc, TaskNotFoundError):
            raise web.HTTPNotFound(reason=jsonable_encoder(error_fields))
        raise web.HTTPBadRequest(reason=jsonable_encoder(error_fields))
