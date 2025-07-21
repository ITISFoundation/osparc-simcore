from common_library.user_messages import user_message
from servicelib.aiohttp import status

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
    WrongPasswordError: HttpErrorInfo(
        status.HTTP_401_UNAUTHORIZED,
        MSG_WRONG_PASSWORD,
    ),
}


handle_rest_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
