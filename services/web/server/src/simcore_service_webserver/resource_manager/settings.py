from aiohttp import web
from pydantic import Field, PositiveInt
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from settings_library.base import BaseCustomSettings


class ResourceManagerSettings(BaseCustomSettings):

    RESOURCE_MANAGER_RESOURCE_TTL_S: PositiveInt = Field(
        900,
        description="Expiration time (or Time to live (TTL) in redis jargon) for a registered resource",
        # legacy!
    )


def get_plugin_settings(app: web.Application) -> ResourceManagerSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_RESOURCE_MANAGER
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, ResourceManagerSettings)  # nosec
    return settings
