import logging

from fastapi import status
from fastapi.encoders import jsonable_encoder
from starlette.requests import Request
from starlette.responses import JSONResponse

from ...long_running_tasks.errors import (
    BaseLongRunningError,
    TaskNotCompletedError,
    TaskNotFoundError,
)

_logger = logging.getLogger(__name__)


async def base_long_running_error_handler(
    _: Request, exception: BaseLongRunningError
) -> JSONResponse:
    _logger.debug("%s", exception, stack_info=True)
    error_fields = dict(code=exception.code, message=f"{exception}")
    status_code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(exception, (TaskNotFoundError, TaskNotCompletedError))
        else status.HTTP_400_BAD_REQUEST
    )
    return JSONResponse(content=jsonable_encoder(error_fields), status_code=status_code)
