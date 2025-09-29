from aiohttp.web import Application
from pydantic import Field
from settings_library.base import BaseCustomSettings

from ..application_keys import APP_SETTINGS_APPKEY


class ExporterSettings(BaseCustomSettings):
    EXPORTER_ENABLED: bool = Field(
        False, description="disabled by default since it is half finished"
    )


def get_plugin_settings(app: Application) -> ExporterSettings:
    settings = app[APP_SETTINGS_APPKEY].WEBSERVER_EXPORTER
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, ExporterSettings)  # nosec
    return settings
