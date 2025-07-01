import logging
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

from ..logging_errors import create_troubleshootting_log_kwargs
from ..status_codes_utils import is_5xx_server_error

validation_error_response_definition["properties"] = {
    "errors": {
        "title": "Validation errors",
        "type": "array",
        "items": {"$ref": f"{REF_PREFIX}ValidationError"},
    },
}


TException = TypeVar("TException")

_logger = logging.getLogger(__name__)


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

    async def _http_error_handler(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, exception_cls)  # nosec
        error_content = {
            "errors": error_extractor(exc) if error_extractor else [f"{exc}"]
        }

        response = JSONResponse(
            content=jsonable_encoder(
                {"error": error_content} if envelope_error else error_content
            ),
            status_code=status_code,
        )

        if is_5xx_server_error(status_code):
            _logger.exception(
                create_troubleshootting_log_kwargs(
                    f"A 5XX server error happened in current service. Responding with {error_content} and {status_code} status code",
                    error=exc,
                    error_context={
                        "request": request,
                        "request.client_host": (
                            request.client.host if request.client else "unknown"
                        ),
                        "request.method": request.method,
                        "request.url_path": request.url.path,
                        "request.query_params": dict(request.query_params),
                        "request.headers": dict(request.headers),
                        "response": response,
                        "response.error_content": error_content,
                        "response.status_code": status_code,
                    },
                )
            )

        return response

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

        return JSONResponse(
            content=jsonable_encoder(
                {"error": error_content} if envelope_error else error_content
            ),
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
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            ValidationError,
            envelope_error=True,
        ),
    )

    # SEE https://docs.python.org/3/library/exceptions.html#exception-hierarchy
    app.add_exception_handler(
        NotImplementedError,
        make_http_error_handler_for_exception(
            status.HTTP_501_NOT_IMPLEMENTED, NotImplementedError, envelope_error=True
        ),
    )
    app.add_exception_handler(
        Exception,
        make_http_error_handler_for_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR, Exception, envelope_error=True
        ),
    )
