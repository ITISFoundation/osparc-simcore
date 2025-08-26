from common_library.user_messages import user_message
from servicelib.aiohttp import status

from ...exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ..errors import ApiKeyDuplicatedDisplayNameError, ApiKeyNotFoundError

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    ApiKeyDuplicatedDisplayNameError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message("An API key with this display name already exists", _version=1),
    ),
    ApiKeyNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("The requested API key could not be found", _version=1),
    ),
}


handle_plugin_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
# this is one decorator with a single exception handler
