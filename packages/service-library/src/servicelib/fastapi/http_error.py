from collections.abc import Awaitable, Callable

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.constants import REF_PREFIX
from fastapi.openapi.utils import validation_error_response_definition
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError


async def http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)

    return JSONResponse(
        content=jsonable_encoder({"errors": [exc.detail]}), status_code=exc.status_code
    )


async def http422_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    assert request  # nosec
    assert isinstance(exc, RequestValidationError | ValidationError)

    return JSONResponse(
        content=jsonable_encoder({"errors": exc.errors()}),
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


validation_error_response_definition["properties"] = {
    "errors": {
        "title": "Validation errors",
        "type": "array",
        "items": {"$ref": f"{REF_PREFIX}ValidationError"},
    },
}


def make_http_error_handler_for_exception(
    status_code: int, exception_cls: type[BaseException]
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    """
    Produces a handler for BaseException-type exceptions which converts them
    into an error JSON response with a given status code

    SEE https://docs.python.org/3/library/exceptions.html#concrete-exceptions
    """

    async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, exception_cls)  # nosec
        return JSONResponse(
            content=jsonable_encoder({"errors": [str(exc)]}),
            status_code=status_code,
        )

    return _http_error_handler
