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

MSG_WALLET_ACCESS_FORBIDDEN_ERROR: Final[str] = user_message(
    "You don't have permission to access this wallet. Contact support if you think this is a mistake.",
    _version=1,
)

MSG_PRICING_UNIT_CREATION_FAILED_ERROR: Final[str] = user_message(
    "Unable to create the pricing unit. Please check the provided information and try again.",
    _version=1,
)
