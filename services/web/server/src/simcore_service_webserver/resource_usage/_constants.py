from typing import Final

from common_library.user_messages import user_message

APP_RABBITMQ_CONSUMERS_KEY: Final[str] = f"{__name__}.rabbit_consumers"

MSG_RESOURCE_USAGE_TRACKER_SERVICE_UNAVAILABLE: Final[str] = user_message(
    "Currently resource usage tracker service is unavailable, please try again later"
)

MSG_RESOURCE_USAGE_TRACKER_NOT_FOUND: Final[str] = user_message("Not Found")
