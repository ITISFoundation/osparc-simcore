from typing import Callable, Optional

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from starlette.requests import Request
from starlette.responses import JSONResponse


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        content=jsonable_encoder({"errors": [exc.detail]}), status_code=exc.status_code
    )


def make_http_error_handler_for_exception(
    status_code: int,
    exception_cls: type[BaseException],
    *,
    override_detail_message: Optional[str] = None,
) -> Callable:
    """
    Produces a handler for BaseException-type exceptions which converts them
    into an error JSON response with a given status code

    SEE https://docs.python.org/3/library/exceptions.html#concrete-exceptions
    """

    async def _http_error_handler(_: Request, exc: type[BaseException]) -> JSONResponse:
        assert isinstance(exc, exception_cls)  # nosec
        details = override_detail_message or f"{exc}"
        return JSONResponse(
            content=jsonable_encoder({"errors": [details]}), status_code=status_code
        )

    return _http_error_handler
