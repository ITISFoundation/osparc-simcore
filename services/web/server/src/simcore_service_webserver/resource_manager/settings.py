from aiohttp import web
from pydantic import Field, PositiveInt
from settings_library.base import BaseCustomSettings

from ..application_keys import APP_SETTINGS_APPKEY


class ResourceManagerSettings(BaseCustomSettings):

    RESOURCE_MANAGER_RESOURCE_TTL_S: PositiveInt = Field(
        900,
        description="Expiration time (or Time to live (TTL) in redis jargon) for a registered resource",
    )


def get_plugin_settings(app: web.Application) -> ResourceManagerSettings:
    settings = app[APP_SETTINGS_APPKEY].WEBSERVER_RESOURCE_MANAGER
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, ResourceManagerSettings)  # nosec
    return settings
