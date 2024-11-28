from fastapi import status
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..log_streaming_errors import (
    LogStreamerNotRegisteredError,
    LogStreamerRegistrationConflictError,
    LogStreamingBaseError,
)
from ._utils import create_error_json_response


async def log_handling_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert request  # nosec
    assert isinstance(exc, LogStreamingBaseError)

    msg = f"{exc}"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    if isinstance(exc, LogStreamerNotRegisteredError):
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    elif isinstance(exc, LogStreamerRegistrationConflictError):
        status_code = status.HTTP_409_CONFLICT

    return create_error_json_response(msg, status_code=status_code)
