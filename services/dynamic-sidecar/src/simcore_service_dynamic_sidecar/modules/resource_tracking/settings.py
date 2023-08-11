from datetime import timedelta

from pydantic import Field
from settings_library.base import BaseCustomSettings


class ResourceTrackingSettings(BaseCustomSettings):
    RESOURCE_TRACKING_HEARTBEAT_INTERVAL: timedelta = Field(
        default_factory=lambda: timedelta(seconds=60),
        description="each time the status of the service is propagated",
    )
