from common_library.user_messages import user_message
from models_library.notifications_errors import (
    NotificationsTemplateContextValidationError,
    NotificationsTemplateNotFoundError,
)
from servicelib.aiohttp import status

from ..exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    NotificationsTemplateContextValidationError: HttpErrorInfo(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        user_message(
            "Validation of context failed for notifications template '{template_name}'.",
            _version=1,
        ),
    ),
    NotificationsTemplateNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "Notifications template '{template_name}' for channel '{channel}' not found.",
            _version=1,
        ),
    ),
}


handle_notifications_exceptions = exception_handling_decorator(to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP))
