from pydantic import Field, PositiveInt
from settings_library.base import BaseCustomSettings
from settings_library.redis import RedisSettings

CONFIG_SECTION_NAME = "resource_manager"


# lock names and format strings
GUEST_USER_RC_LOCK_FORMAT = f"{__name__}:redlock:garbage_collect_user:{{user_id}}"


class ResourceManagerSettings(BaseCustomSettings):

    RESOURCE_MANAGER_RESOURCE_TTL_S: PositiveInt = Field(
        900,
        description="Expiration time (or Time to live (TTL) in redis jargon) for a registered resource",
        # legacy!
        env=["WEBSERVER_RESOURCES_DELETION_TIMEOUT_SECONDS"],
    )

    RESOURCE_MANAGER_GARBAGE_COLLECTION_INTERVAL_S: PositiveInt = Field(
        30,
        description="Waiting time between consecutive runs of the garbage-colector",
        # legacy
        env=["WEBSERVER_GARBAGE_COLLECTION_INTERVAL_SECONDS"],
    )

    RESOURCE_MANAGER_REDIS: RedisSettings
