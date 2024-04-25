from collections.abc import Callable

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from servicelib.error_codes import create_error_code
from starlette.requests import Request
from starlette.responses import JSONResponse

from ...models.schemas.errors import ErrorGet


def create_error_json_response(*errors, status_code: int) -> JSONResponse:
    # NOTE: do not forget to add in the decorator `responses={ ???: {"model": ErrorGet} }`
    # SEE https://fastapi.tiangolo.com/advanced/additional-responses/#additional-response-with-model
    error_model = ErrorGet(errors=list(errors))
    return JSONResponse(content=jsonable_encoder(error_model), status_code=status_code)


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return create_error_json_response(exc.detail, status_code=exc.status_code)


def make_http_error_handler_for_exception(
    exception_cls: type[BaseException],
    status_code: int,
    *,
    detail_message: str,
    add_exception_to_message: bool = False,
    add_oec_to_message: bool = False,
) -> Callable:
    """
    Produces a handler for BaseException-type exceptions which converts them
    into an error JSON response with a given status code

    SEE https://docs.python.org/3/library/exceptions.html#concrete-exceptions
    """

    async def _http_error_handler(_: Request, error: BaseException) -> JSONResponse:
        assert isinstance(error, exception_cls)  # nosec
        details = detail_message
        if add_exception_to_message:
            details += f"\n{error}"
        if add_oec_to_message:
            details += f"\n[OEC: {create_error_code(error)}]"
        return create_error_json_response(details, status_code=status_code)

    return _http_error_handler
