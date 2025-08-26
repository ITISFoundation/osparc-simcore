import logging
from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from servicelib.logging_errors import create_troubleshootting_log_kwargs
from servicelib.status_codes_utils import is_5xx_server_error
from starlette.requests import Request
from starlette.responses import JSONResponse

_logger = logging.getLogger(__name__)


async def http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)

    return JSONResponse(
        content=jsonable_encoder({"errors": [exc.detail]}), status_code=exc.status_code
    )


def make_http_error_handler_for_exception(
    status_code: int, exception_cls: type[BaseException]
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    """
    Produces a handler for BaseException-type exceptions which converts them
    into an error JSON response with a given status code

    SEE https://docs.python.org/3/library/exceptions.html#concrete-exceptions
    """

    async def _http_error_handler(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, exception_cls)  # nosec

        if is_5xx_server_error(status_code):
            _logger.exception(
                **create_troubleshootting_log_kwargs(
                    f"HTTP error handler caught an {exception_cls.__name__} exception and responds with {status_code} status code",
                    error=exc,
                    error_context={"request": request, "status_code": status_code},
                )
            )

        return JSONResponse(
            content=jsonable_encoder({"errors": [str(exc)]}), status_code=status_code
        )

    return _http_error_handler
