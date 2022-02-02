""" resource manager subsystem's configuration

    - config-file schema
    - settings
"""

from aiohttp.web import Application
from pydantic import Field, PositiveInt
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY
from settings_library.base import BaseCustomSettings
from settings_library.redis import RedisSettings

from .config import CONFIG_SECTION_NAME

CONFIG_SECTION_NAME = "resource_manager"


# lock names and format strings
GUEST_USER_RC_LOCK_FORMAT = f"{__name__}:redlock:garbage_collect_user:{{user_id}}"


class ResourceManagerSettings(BaseCustomSettings):

    RESOURCE_MANAGER_RESOURCE_TTL_S: PositiveInt = Field(
        900,
        description="Expiration time (or Time to live (TTL) in redis jargon) for a registered resource",
        # legacy!
        env=[
            "RESOURCE_MANAGER_RESOURCE_TTL_S",
            "WEBSERVER_RESOURCES_DELETION_TIMEOUT_SECONDS",  # legacy
        ],
    )

    RESOURCE_MANAGER_GARBAGE_COLLECTION_INTERVAL_S: PositiveInt = Field(
        30,
        description="Waiting time between consecutive runs of the garbage-colector",
        # legacy
        env=[
            "RESOURCE_MANAGER_GARBAGE_COLLECTION_INTERVAL_S",
            "WEBSERVER_GARBAGE_COLLECTION_INTERVAL_SECONDS",  # legacy
        ],
    )


def assert_valid_config(app: Application):
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    WEBSERVER_RESOURCE_MANAGER = ResourceManagerSettings()
    WEBSERVER_REDIS = RedisSettings()

    assert cfg == {  # nosec
        "enabled": (
            WEBSERVER_REDIS is not None and WEBSERVER_RESOURCE_MANAGER is not None
        ),
        "resource_deletion_timeout_seconds": WEBSERVER_RESOURCE_MANAGER.RESOURCE_MANAGER_RESOURCE_TTL_S,
        "garbage_collection_interval_seconds": WEBSERVER_RESOURCE_MANAGER.RESOURCE_MANAGER_GARBAGE_COLLECTION_INTERVAL_S,
        "redis": {
            "enabled": WEBSERVER_REDIS is not None,
            "host": WEBSERVER_REDIS.REDIS_HOST,
            "port": WEBSERVER_REDIS.REDIS_PORT,
        },
    }
    return cfg, WEBSERVER_RESOURCE_MANAGER, WEBSERVER_REDIS
