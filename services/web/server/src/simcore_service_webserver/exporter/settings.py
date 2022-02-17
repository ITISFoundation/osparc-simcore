from aiohttp.web import Application
from pydantic import Field, PositiveInt
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from settings_library.base import BaseCustomSettings


class ExporterSettings(BaseCustomSettings):
    EXPORTER_MAX_UPLOAD_FILE_SIZE: PositiveInt = Field(
        10,
        description="size in GB of the maximum projects/import request",
        env=[
            "EXPORTER_MAX_UPLOAD_FILE_SIZE",
            "WEBSERVER_EXPORTER_MAX_UPLOAD_FILE_SIZE",
        ],
    )
    EXPORTER_DOWNLOADER_MAX_TIMEOUT_SECONDS: PositiveInt = Field(
        60 * 60,
        description="maximum timeout for each individual file used in the file_downlaoder",
        env=[
            "EXPORTER_DOWNLOADER_MAX_TIMEOUT_SECONDS",
            "WEBSERVER_EXPORTER_DOWNLOADER_MAX_TIMEOUT_SECONDS",
        ],
    )


def get_plugin_settings(app: Application) -> ExporterSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_EXPORTER
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, ExporterSettings)  # nosec
    return settings
