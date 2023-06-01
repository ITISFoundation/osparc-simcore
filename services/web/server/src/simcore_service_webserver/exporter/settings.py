from aiohttp.web import Application
from pydantic import Field
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from settings_library.base import BaseCustomSettings


class ExporterSettings(BaseCustomSettings):
    EXPORTER_ENABLED: bool = Field(
        False, description="disabled by default since it is half finished"
    )


def get_plugin_settings(app: Application) -> ExporterSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_EXPORTER
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, ExporterSettings)  # nosec
    return settings
