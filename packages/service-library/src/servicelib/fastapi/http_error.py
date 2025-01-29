from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.constants import REF_PREFIX
from fastapi.openapi.utils import validation_error_response_definition
from fastapi.requests import Request
from fastapi.responses import JSONResponse


def make_default_http_error_handler(
    *, envelope_error: bool
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, HTTPException)

        error_content = {"errors": [exc.detail]}
        if envelope_error:
            error_content = {"error": error_content}
        return JSONResponse(
            content=jsonable_encoder(error_content),
            status_code=exc.status_code,
        )

    return _http_error_handler


validation_error_response_definition["properties"] = {
    "errors": {
        "title": "Validation errors",
        "type": "array",
        "items": {"$ref": f"{REF_PREFIX}ValidationError"},
    },
}


def make_http_error_handler_for_exception(
    status_code: int,
    exception_cls: type[BaseException],
    *,
    envelope_error: bool,
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    """
    Produces a handler for BaseException-type exceptions which converts them
    into an error JSON response with a given status code

    SEE https://docs.python.org/3/library/exceptions.html#concrete-exceptions
    """

    async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, exception_cls)  # nosec
        error_content = {"errors": [f"{exc}"]}
        if envelope_error:
            error_content = {"error": error_content}
        return JSONResponse(
            content=jsonable_encoder(error_content),
            status_code=status_code,
        )

    return _http_error_handler
