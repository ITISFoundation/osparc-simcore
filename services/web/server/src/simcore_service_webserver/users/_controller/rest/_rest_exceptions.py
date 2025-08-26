from common_library.user_messages import user_message
from servicelib.aiohttp import status

from ....exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ...exceptions import (
    AlreadyPreRegisteredError,
    MissingGroupExtraPropertiesForProductError,
    PendingPreRegistrationNotFoundError,
    PhoneRegistrationCodeInvalidError,
    PhoneRegistrationPendingNotFoundError,
    PhoneRegistrationSessionInvalidError,
    UserNameDuplicateError,
    UserNotFoundError,
)

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    PendingPreRegistrationNotFoundError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        user_message(
            "No pending registration request found for email {email} in {product_name}.",
            _version=2,
        ),
    ),
    UserNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "The requested user could not be found. "
            "This may be because the user is not registered or has privacy settings enabled.",
            _version=1,
        ),
    ),
    UserNameDuplicateError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "The username '{user_name}' is already in use. "
            "Please try '{alternative_user_name}' instead.",
            _version=1,
        ),
    ),
    AlreadyPreRegisteredError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "Found {num_found} existing account(s) for '{email}'. Unable to pre-register an existing user.",
            _version=1,
        ),
    ),
    MissingGroupExtraPropertiesForProductError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        user_message(
            "This product is currently being configured and is not yet ready for use. "
            "Please try again later.",
            _version=1,
        ),
    ),
    PhoneRegistrationPendingNotFoundError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        user_message(
            "No pending phone registration found. Please start the phone registration process first.",
            _version=1,
        ),
    ),
    PhoneRegistrationSessionInvalidError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        user_message(
            "Your phone registration session is invalid or has expired. Please start the phone registration process again.",
            _version=1,
        ),
    ),
    PhoneRegistrationCodeInvalidError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        user_message(
            "The confirmation code you entered is incorrect. Please check and try again.",
            _version=1,
        ),
    ),
}

handle_rest_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
