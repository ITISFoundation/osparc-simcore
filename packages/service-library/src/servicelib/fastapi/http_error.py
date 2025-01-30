from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import FastAPI, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.constants import REF_PREFIX
from fastapi.openapi.utils import validation_error_response_definition
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

validation_error_response_definition["properties"] = {
    "errors": {
        "title": "Validation errors",
        "type": "array",
        "items": {"$ref": f"{REF_PREFIX}ValidationError"},
    },
}


TException = TypeVar("TException")


def make_http_error_handler_for_exception(
    status_code: int,
    exception_cls: type[TException],
    *,
    envelope_error: bool,
    error_extractor: Callable[[TException], list[str]] | None = None,
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    """
    Produces a handler for BaseException-type exceptions which converts them
    into an error JSON response with a given status code

    SEE https://docs.python.org/3/library/exceptions.html#concrete-exceptions
    """

    async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, exception_cls)  # nosec
        error_content = {
            "errors": error_extractor(exc) if error_extractor else [f"{exc}"]
        }

        if envelope_error:
            error_content = {"error": error_content}
        return JSONResponse(
            content=jsonable_encoder(error_content),
            status_code=status_code,
        )

    return _http_error_handler


def _request_validation_error_extractor(
    validation_error: RequestValidationError,
) -> list[str]:
    return [f"{e}" for e in validation_error.errors()]


def _make_default_http_error_handler(
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


def set_app_default_http_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        HTTPException, _make_default_http_error_handler(envelope_error=True)
    )

    app.add_exception_handler(
        RequestValidationError,
        make_http_error_handler_for_exception(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            RequestValidationError,
            envelope_error=True,
            error_extractor=_request_validation_error_extractor,
        ),
    )

    app.add_exception_handler(
        ValidationError,
        make_http_error_handler_for_exception(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            ValidationError,
            envelope_error=True,
        ),
    )
