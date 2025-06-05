from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from httpx import HTTPError as HttpxException
from models_library.functions_errors import FunctionBaseError
from starlette import status
from starlette.exceptions import HTTPException

from ..._constants import MSG_INTERNAL_ERROR_USER_FRIENDLY_TEMPLATE
from ...exceptions.backend_errors import BaseBackEndError
from ..custom_errors import CustomBaseError
from ..log_streaming_errors import LogStreamingBaseError
from ._custom_errors import custom_error_handler
from ._handler_function_errors import function_error_handler
from ._handlers_backend_errors import backend_error_handler
from ._handlers_factory import make_handler_for_exception
from ._http_exceptions import http_exception_handler
from ._httpx_client_exceptions import handle_httpx_client_exceptions
from ._log_streaming_errors import log_handling_error_handler
from ._validation_errors import http422_error_handler


def setup(app: FastAPI, *, is_debug: bool = False):
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(HttpxException, handle_httpx_client_exceptions)
    app.add_exception_handler(RequestValidationError, http422_error_handler)
    app.add_exception_handler(LogStreamingBaseError, log_handling_error_handler)
    app.add_exception_handler(CustomBaseError, custom_error_handler)
    app.add_exception_handler(BaseBackEndError, backend_error_handler)
    app.add_exception_handler(FunctionBaseError, function_error_handler)

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
            add_exception_to_message=is_debug,
            add_oec_to_message=True,
        ),
    )
