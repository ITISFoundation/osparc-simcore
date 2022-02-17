""" resource manager subsystem's configuration

    - config-file schema
    - settings
"""

from copy import deepcopy

from aiohttp.web import Application
from pydantic import Field, PositiveInt
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY, APP_SETTINGS_KEY
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

    cfg_test = deepcopy(cfg)

    cfg_enabled = cfg_test.pop("enabled", None)
    cfg_redis_enabled = cfg_test.get("redis", {}).pop("enabled", None)

    if app_settings := app.get(APP_SETTINGS_KEY):
        if app_settings.WEBSERVER_REDIS:
            assert app_settings.WEBSERVER_REDIS == WEBSERVER_REDIS

        if app_settings.WEBSERVER_RESOURCE_MANAGER:
            assert app_settings.WEBSERVER_REDIS == WEBSERVER_REDIS

        assert cfg_enabled == (app_settings.WEBSERVER_RESOURCE_MANAGER is not None)
        assert cfg_redis_enabled == (app_settings.WEBSERVER_REDIS is not None)

    assert cfg_test == {  # nosec
        "resource_deletion_timeout_seconds": WEBSERVER_RESOURCE_MANAGER.RESOURCE_MANAGER_RESOURCE_TTL_S,
        "garbage_collection_interval_seconds": WEBSERVER_RESOURCE_MANAGER.RESOURCE_MANAGER_GARBAGE_COLLECTION_INTERVAL_S,
        "redis": {
            "host": WEBSERVER_REDIS.REDIS_HOST,
            "port": WEBSERVER_REDIS.REDIS_PORT,
        },
    }
    return cfg, WEBSERVER_RESOURCE_MANAGER, WEBSERVER_REDIS
