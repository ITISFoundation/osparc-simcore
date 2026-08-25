from common_library.user_messages import user_message
from servicelib.aiohttp import status
from simcore_postgres_database.utils_user_preferences import (
    CouldNotCreateOrUpdateUserPreferenceError,
)

from ....exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ...errors import (
    FrontendUserPreferenceIsNotDefinedError,
    FrontendUserPreferenceValueIsInvalidError,
)

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    CouldNotCreateOrUpdateUserPreferenceError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        user_message(
            "Could not create or modify preferences",
        ),
    ),
    FrontendUserPreferenceIsNotDefinedError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("Provided {frontend_preference_identifier} not found"),
    ),
    FrontendUserPreferenceValueIsInvalidError: HttpErrorInfo(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        user_message("The value {value} is not allowed for {frontend_preference_identifier}"),
    ),
}


handle_rest_requests_exceptions = exception_handling_decorator(to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP))
