from pydantic import BaseSettings, Field, PositiveInt


class ExporterSettings(BaseSettings):
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


exporter_settings = ExporterSettings()
