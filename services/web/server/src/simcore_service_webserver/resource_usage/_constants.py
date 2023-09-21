from typing import Final

APP_RABBITMQ_CONSUMERS_KEY: Final[str] = f"{__name__}.rabbit_consumers"

MSG_RESOURCE_USAGE_TRACKER_SERVICE_UNAVAILABLE: Final[
    str
] = "Currently resource usage tracker service is unavailable, please try again later"
