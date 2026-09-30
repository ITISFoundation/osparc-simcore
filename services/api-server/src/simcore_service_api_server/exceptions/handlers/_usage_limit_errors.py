from starlette.requests import Request
from starlette.responses import JSONResponse

from ...exceptions.usage_limit_errors import ChatboxUsageBaseError
from ._utils import create_error_json_response


async def usage_limit_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert request  # nosec
    assert isinstance(exc, ChatboxUsageBaseError)  # nosec

    headers = {}
    if (retry_after := exc.retry_after_seconds) is not None:
        headers["Retry-After"] = f"{retry_after}"

    return create_error_json_response(f"{exc}", status_code=exc.status_code, headers=headers)
