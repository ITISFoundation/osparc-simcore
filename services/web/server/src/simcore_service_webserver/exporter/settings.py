from aiohttp.web import Application
from pydantic import Field, PositiveInt
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from settings_library.base import BaseCustomSettings


class ExporterSettings(BaseCustomSettings):
    EXPORTER_MAX_UPLOAD_FILE_SIZE: PositiveInt = Field(
        10,
        description="size in GB of the maximum projects/import request",
    )
    EXPORTER_DOWNLOADER_MAX_TIMEOUT_SECONDS: PositiveInt = Field(
        60 * 60,
        description="maximum timeout for each individual file used in the file_downlaoder",
    )


def get_settings(app: Application) -> ExporterSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_EXPORTER
    assert settings  # nosec
    return settings
