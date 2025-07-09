from common_library.user_messages import user_message
from servicelib.aiohttp import status

from ...exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ...users.exceptions import TokenNotFoundError

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    TokenNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "The API token for '{service}' could not be found.",
            _version=1,
        ),
    ),
}


handle_rest_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
