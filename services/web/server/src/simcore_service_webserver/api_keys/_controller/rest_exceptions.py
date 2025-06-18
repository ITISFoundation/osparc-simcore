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
        user_message("API key display name duplicated"),
    ),
    ApiKeyNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("API key was not found"),
    ),
}


handle_plugin_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
# this is one decorator with a single exception handler
