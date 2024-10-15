import logging

from fastapi.requests import Request
from fastapi.responses import JSONResponse
from models_library.error_codes import create_error_code
from servicelib.logging_errors import create_troubleshotting_log_kwargs

from ._utils import ExceptionHandler, create_error_json_response

_logger = logging.getLogger(__file__)


def make_handler_for_exception(
    exception_cls: type[BaseException],
    status_code: int,
    *,
    error_message: str,
    add_exception_to_message: bool = False,
    add_oec_to_message: bool = False,
) -> ExceptionHandler:
    """
    Produces a handler for BaseException-type exceptions which converts them
    into an error JSON response with a given status code

    SEE https://docs.python.org/3/library/exceptions.html#concrete-exceptions
    """

    async def _http_error_handler(
        request: Request, exception: BaseException
    ) -> JSONResponse:
        assert request  # nosec
        assert isinstance(exception, exception_cls)  # nosec

        msg = error_message
        if add_exception_to_message:
            msg += f" {exception}"

        if add_oec_to_message:
            error_code = create_error_code(exception)
            msg += f" [{error_code}]"

        _logger.exception(
            **create_troubleshotting_log_kwargs(
                f"Unexpected {exception.__class__.__name__}: {msg}",
                exception=exception,
            )
        )
        return create_error_json_response(msg, status_code=status_code)

    return _http_error_handler
