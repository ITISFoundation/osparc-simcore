from pydantic import BaseSettings, PositiveInt


class ServicesCommonSettings(BaseSettings):
    # set this interval to 1 hour
    director_stop_service_timeout: PositiveInt = 60 * 60
    storage_service_upload_download_timeout: PositiveInt = 60 * 60

    class Config:
        env_prefix = "SERVICES_COMMON_"
        case_sensitive = False
