from aiohttp import web
from common_library.user_messages import user_message
from servicelib.aiohttp import status
from servicelib.aiohttp.rest_middlewares import handle_aiohttp_web_http_error

from ....exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ....users.exceptions import AlreadyPreRegisteredError
from ...constants import MSG_2FA_UNAVAILABLE, MSG_WRONG_PASSWORD
from ...errors import (
    SendingVerificationEmailError,
    SendingVerificationSmsError,
    WrongPasswordError,
)

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    AlreadyPreRegisteredError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "An account for the email {email} has been submitted. If you haven't received any updates, please contact support.",
            _version=1,
        ),
    ),
    SendingVerificationSmsError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        MSG_2FA_UNAVAILABLE,
    ),
    SendingVerificationEmailError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        MSG_2FA_UNAVAILABLE,
    ),
}


async def _handle_legacy_error_response(request: web.Request, exception: Exception):
    """
    This handlers keeps compatibility with error responses that include deprecated
    `ErrorGet.errors` field

    SEE packages/models-library/src/models_library/rest_error.py
    """
    assert isinstance(  # nosec
        exception, WrongPasswordError
    ), f"Expected WrongPasswordError, got {type(exception)}"

    return handle_aiohttp_web_http_error(
        request=request,
        exception=web.HTTPUnauthorized(text=MSG_WRONG_PASSWORD),
    )


handle_rest_requests_exceptions = exception_handling_decorator(
    {
        **to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP),
        WrongPasswordError: _handle_legacy_error_response,
    },
)
