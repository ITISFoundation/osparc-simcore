from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from httpx import HTTPError as HttpxException
from models_library.basic_types import BootModeEnum
from starlette import status
from starlette.exceptions import HTTPException

from ..core.settings import ApplicationSettings
from ..models.custom_errors import CustomBaseError
from ..services.log_streaming import LogDistributionBaseException
from .custom_errors import custom_error_handler
from .http_error import http_error_handler, make_http_error_handler_for_exception
from .httpx_client_error import handle_httpx_client_exceptions
from .log_handling_error import log_handling_error_handler
from .validation_error import http422_error_handler


def setup(app: FastAPI):
    settings: ApplicationSettings = app.state.settings
    assert isinstance(settings, ApplicationSettings)  # nosec

    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(HttpxException, handle_httpx_client_exceptions)
    app.add_exception_handler(RequestValidationError, http422_error_handler)
    app.add_exception_handler(LogDistributionBaseException, log_handling_error_handler)
    app.add_exception_handler(CustomBaseError, custom_error_handler)

    # SEE https://docs.python.org/3/library/exceptions.html#exception-hierarchy
    app.add_exception_handler(
        NotImplementedError,
        make_http_error_handler_for_exception(
            NotImplementedError,
            status.HTTP_501_NOT_IMPLEMENTED,
            detail_message="Endpoint not implemented",
        ),
    )
    app.add_exception_handler(
        Exception,
        make_http_error_handler_for_exception(
            Exception,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail_message="Unexpected error",
            add_exception_to_message=(settings.SC_BOOT_MODE == BootModeEnum.DEBUG),
            add_oec_to_message=True,
        ),
    )
