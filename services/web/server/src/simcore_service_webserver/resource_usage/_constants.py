from typing import Final

from common_library.user_messages import user_message

APP_RABBITMQ_CONSUMERS_KEY: Final[str] = f"{__name__}.rabbit_consumers"

MSG_RESOURCE_USAGE_TRACKER_SERVICE_UNAVAILABLE: Final[str] = user_message(
    "The resource usage tracking service is temporarily unavailable. Please try again in a few moments.",
    _version=1,
)

MSG_RESOURCE_USAGE_TRACKER_NOT_FOUND: Final[str] = user_message(
    "The requested resource usage information could not be found.", _version=1
)
