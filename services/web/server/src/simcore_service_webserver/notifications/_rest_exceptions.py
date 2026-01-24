from common_library.user_messages import user_message
from models_library.notifications_errors import NotificationsTemplateNotFoundError
from servicelib.aiohttp import status

from ..exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    NotificationsTemplateNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "Notifications template '{template_name}' for channel '{channel}' not found.",
            _version=1,
        ),
    ),
}


handle_notifications_exceptions = exception_handling_decorator(to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP))
