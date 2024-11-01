from collections.abc import Callable
from typing import Awaitable

from fastapi import HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse

from ...exceptions.errors import RutNotFoundError


async def http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)  # nosec
    return JSONResponse(
        content=jsonable_encoder({"errors": [exc.detail]}), status_code=exc.status_code
    )


def http404_error_handler(
    _: Request,  # pylint: disable=unused-argument
    exc: RutNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": f"{exc.msg_template}"},
    )


def make_http_error_handler_for_exception(
    status_code: int, exception_cls: type[BaseException]
) -> Callable[[Request, type[BaseException]], Awaitable[JSONResponse]]:
    """
    Produces a handler for BaseException-type exceptions which converts them
    into an error JSON response with a given status code

    SEE https://docs.python.org/3/library/exceptions.html#concrete-exceptions
    """

    async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, exception_cls)  # nosec
        return JSONResponse(
            content=jsonable_encoder({"errors": [str(exc)]}), status_code=status_code
        )

    return _http_error_handler
