from common_library.user_messages import user_message
from models_library.notifications._errors import (
    NoActiveContactsError,
    TemplateContextValidationError,
    TemplateNotFoundError,
    UnsupportedChannelError,
)
from servicelib.aiohttp import status

from ...exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    NoActiveContactsError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        user_message(
            "No active recipients selected.",
            _version=1,
        ),
    ),
    TemplateContextValidationError: HttpErrorInfo(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        user_message(
            "Validation of context failed for notification template '{template_name}'.",
            _version=1,
        ),
    ),
    TemplateNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "Notification template '{template_name}' for channel '{channel}' not found.",
            _version=1,
        ),
    ),
    UnsupportedChannelError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        user_message(
            "Notification channel '{channel}' is not supported.",
            _version=1,
        ),
    ),
}


handle_notifications_exceptions = exception_handling_decorator(to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP))
