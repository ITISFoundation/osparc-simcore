from datetime import timedelta

from pydantic import Field
from settings_library.base import BaseCustomSettings
from settings_library.resource_usage_tracker import (
    DEFAULT_RESOURCE_USAGE_HEARTBEAT_INTERVAL,
)


class ResourceTrackingSettings(BaseCustomSettings):
    RESOURCE_TRACKING_HEARTBEAT_INTERVAL: timedelta = Field(
        default=DEFAULT_RESOURCE_USAGE_HEARTBEAT_INTERVAL,
        description="each time the status of the service is propagated",
    )
