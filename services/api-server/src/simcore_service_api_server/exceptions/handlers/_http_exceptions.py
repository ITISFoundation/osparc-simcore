from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from ._utils import create_error_json_response


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    assert request  # nosec
    return create_error_json_response(exc.detail, status_code=exc.status_code)
