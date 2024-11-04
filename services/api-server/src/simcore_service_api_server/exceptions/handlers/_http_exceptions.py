from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from ._utils import create_error_json_response


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert request  # nosec
    assert isinstance(exc, HTTPException)  # nosec

    return create_error_json_response(exc.detail, status_code=exc.status_code)
