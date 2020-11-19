from typing import Callable

from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"errors": [exc.detail]}, status_code=exc.status_code)


def make_http_error_handler_for_exception(status_code: int) -> Callable:
    """
        Handles a BaseException as an error JSON response with a given status code

        SEE https://docs.python.org/3/library/exceptions.html#concrete-exceptions
    """
    async def _http_error_handler(_: Request, exc: BaseException) -> JSONResponse:
        return JSONResponse({"errors": [str(exc)]}, status_code=status_code)

    return _http_error_handler
