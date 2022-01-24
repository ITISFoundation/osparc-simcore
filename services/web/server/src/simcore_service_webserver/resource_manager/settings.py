""" resource manager subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict

from aiohttp.web import Application
from models_library.settings.redis import RedisConfig
from pydantic import Field, PositiveInt
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY, APP_SETTINGS_KEY
from settings_library.base import BaseCustomSettings

from .config import CONFIG_SECTION_NAME


class RedisSection(RedisConfig):
    enabled: bool = True


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


def assert_valid_config(app: Application) -> Dict:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    app_settings = app[APP_SETTINGS_KEY]
    assert cfg == {  # nosec
        "enabled": (
            app_settings.WEBSERVER_REDIS is not None
            and app_settings.WEBSERVER_RESOURCE_MANAGER is not None
        ),
        "resource_deletion_timeout_seconds": app_settings.WEBSERVER_RESOURCE_MANAGER.RESOURCE_MANAGER_RESOURCE_TTL_S,
        "garbage_collection_interval_seconds": app_settings.WEBSERVER_RESOURCE_MANAGER.RESOURCE_MANAGER_GARBAGE_COLLECTION_INTERVAL_S,
        "redis": {
            "enabled": app_settings.WEBSERVER_REDIS is not None,
            "host": app_settings.WEBSERVER_REDIS.REDIS_HOST,
            "port": app_settings.WEBSERVER_REDIS.REDIS_PORT,
        },
    }
    return cfg
