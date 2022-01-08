from typing import Dict, Optional

from aiohttp.web import Application
from models_library.settings.redis import RedisConfig
from pydantic import BaseSettings, Field, PositiveInt
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

CONFIG_SECTION_NAME = "resource_manager"


# lock names and format strings
GUEST_USER_RC_LOCK_FORMAT = f"{__name__}:redlock:garbage_collect_user:{{user_id}}"


class RedisSection(RedisConfig):
    enabled: bool = True


class ResourceManagerSettings(BaseSettings):
    enabled: bool = True

    resource_deletion_timeout_seconds: Optional[PositiveInt] = Field(
        900,
        description="Expiration time (or Time to live (TTL) in redis jargon) for a registered resource",
    )
    garbage_collection_interval_seconds: Optional[PositiveInt] = Field(
        30, description="Waiting time between consecutive runs of the garbage-colector"
    )

    redis: RedisSection

    class Config:
        case_sensitive = False
        env_prefix = "WEBSERVER_"


def get_garbage_collector_interval(app: Application) -> int:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME][
        "garbage_collection_interval_seconds"
    ]


def assert_valid_config(app: Application) -> Dict:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    _settings = ResourceManagerSettings(**cfg)
    return cfg
