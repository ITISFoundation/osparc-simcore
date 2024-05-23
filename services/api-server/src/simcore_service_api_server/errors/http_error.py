import logging
from collections.abc import Callable

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from servicelib.error_codes import create_error_code
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..models.schemas.errors import ErrorGet

_logger = logging.getLogger(__file__)


def create_error_json_response(*errors, status_code: int) -> JSONResponse:
    # NOTE: do not forget to add in the decorator `responses={ ???: {"model": ErrorGet} }`
    # SEE https://fastapi.tiangolo.com/advanced/additional-responses/#additional-response-with-model
    error_model = ErrorGet(errors=list(errors))
    return JSONResponse(content=jsonable_encoder(error_model), status_code=status_code)


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return create_error_json_response(exc.detail, status_code=exc.status_code)


def make_handler_for_exception(
    exception_cls: type[BaseException],
    status_code: int,
    *,
    error_message: str,
    add_exception_to_message: bool = False,
    add_oec_to_message: bool = False,
) -> Callable:
    """
    Produces a handler for BaseException-type exceptions which converts them
    into an error JSON response with a given status code

    SEE https://docs.python.org/3/library/exceptions.html#concrete-exceptions
    """

    async def _http_error_handler(_: Request, exception: BaseException) -> JSONResponse:
        assert isinstance(exception, exception_cls)  # nosec

        msg = error_message
        if add_exception_to_message:
            msg += f" {exception}"

        if add_oec_to_message:
            error_code = create_error_code(exception)
            msg += f" [{error_code}]"
            _logger.exception(
                "Unexpected %s: %s",
                exception.__class__.__name__,
                msg,
                extra={"error_code": error_code},
            )
        return create_error_json_response(msg, status_code=status_code)

    return _http_error_handler
