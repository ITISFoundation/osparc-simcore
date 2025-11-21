from typing import Final

from common_library.user_messages import user_message

MSG_BACKEND_SERVICE_UNAVAILABLE: Final[str] = user_message(
    "The service is currently unavailable. Please try again later.", _version=1
)

MSG_INTERNAL_ERROR_USER_FRIENDLY_TEMPLATE: Final[str] = user_message(
    "Something went wrong on our end. We've been notified and will resolve this issue as soon as possible. Thank you for your patience.",
    _version=2,
)

MSG_CLIENT_ERROR_USER_FRIENDLY_TEMPLATE: Final[str] = user_message(
    "Something went wrong with your request.",
    _version=1,
)
