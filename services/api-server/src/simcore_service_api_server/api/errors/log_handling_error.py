from fastapi import status
from starlette.requests import Request
from starlette.responses import JSONResponse

from ...services.log_streaming import (
    LogDistributionBaseError,
    LogStreamerNotRegisteredError,
    LogStreamerRegistionConflictError,
)
from .http_error import create_error_json_response


async def log_handling_error_handler(
    _: Request, exc: LogDistributionBaseError
) -> JSONResponse:
    msg = f"{exc}"
    status_code: int = 500
    if isinstance(exc, LogStreamerNotRegisteredError):
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    elif isinstance(exc, LogStreamerRegistionConflictError):
        status_code = status.HTTP_409_CONFLICT

    return create_error_json_response(msg, status_code=status_code)
