from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from httpx import HTTPError as HttpxException
from models_library.basic_types import BootModeEnum
from starlette import status
from starlette.exceptions import HTTPException

from ..core.settings import ApplicationSettings
from ._custom_handlers import custom_error_handler
from ._handlers_factory import make_handler_for_exception
from ._http_error_handlers import http_error_handler
from ._httpx_error_handlers import handle_httpx_client_exceptions
from ._log_streaming_error_handlers import log_handling_error_handler
from ._validation_error_handlers import http422_error_handler
from .custom import CustomBaseError
from .log_streaming import LogStreamingBaseError

MSG_INTERNAL_ERROR_USER_FRIENDLY_TEMPLATE = "Oops! Something went wrong, but we've noted it down and we'll sort it out ASAP. Thanks for your patience!"


def setup(app: FastAPI):
    settings: ApplicationSettings = app.state.settings
    assert isinstance(settings, ApplicationSettings)  # nosec

    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(HttpxException, handle_httpx_client_exceptions)
    app.add_exception_handler(RequestValidationError, http422_error_handler)
    app.add_exception_handler(LogStreamingBaseError, log_handling_error_handler)
    app.add_exception_handler(CustomBaseError, custom_error_handler)

    # SEE https://docs.python.org/3/library/exceptions.html#exception-hierarchy
    app.add_exception_handler(
        NotImplementedError,
        make_handler_for_exception(
            NotImplementedError,
            status.HTTP_501_NOT_IMPLEMENTED,
            error_message="This endpoint is still not implemented (under development)",
        ),
    )
    app.add_exception_handler(
        Exception,
        make_handler_for_exception(
            Exception,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_message=MSG_INTERNAL_ERROR_USER_FRIENDLY_TEMPLATE,
            add_exception_to_message=(settings.SC_BOOT_MODE == BootModeEnum.DEBUG),
            add_oec_to_message=True,
        ),
    )
