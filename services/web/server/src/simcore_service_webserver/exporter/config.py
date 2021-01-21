from aiohttp.web import Application
from pydantic import BaseSettings, Field, PositiveInt
from servicelib.application_keys import APP_CONFIG_KEY

CONFIG_SECTION_NAME = "exporter"
# NOTE: we are saving it in a separate item to config
EXPORTER_SETTINGS_KEY = f"{__name__}.ExporterSettings"


class ExporterSettings(BaseSettings):
    enabled: bool = True
    max_upload_file_size: PositiveInt = Field(
        10, description="size in GB of the maximum projects/import request"
    )
    downloader_max_timeout_seconds: PositiveInt = Field(
        60 * 60,
        description="maximum timeout for each individual file used in the file_downlaoder",
    )

    class Config:
        case_sensitive = False
        env_prefix = "WEBSERVER_EXPORTER_"


def inject_settings(app: Application) -> None:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    settings = ExporterSettings(**cfg)
    app[EXPORTER_SETTINGS_KEY] = settings


def get_settings(app: Application) -> ExporterSettings:
    return app[EXPORTER_SETTINGS_KEY]
