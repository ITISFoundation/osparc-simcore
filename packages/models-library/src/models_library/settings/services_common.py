import warnings

from pydantic import BaseSettings, Field, PositiveInt

warnings.warn(
    f"{__name__} is deprecated, ONLY settings_library based settings should be used",
    DeprecationWarning,
)


_MINUTE = 60
_HOUR = 60 * _MINUTE


# TODO: port all these options to settings_library.base.BaseCustomSettings subclasses


class ServicesCommonSettings(BaseSettings):
    # set this interval to 1 hour
    director_dynamic_service_save_timeout: PositiveInt = Field(
        _HOUR,
        description=(
            "When stopping a dynamic service, if it has "
            "big payloads it is important to have longer timeouts."
        ),
    )
    storage_service_upload_download_timeout: PositiveInt = Field(
        _HOUR,
        description=(
            "When dynamic services upload and download data from storage, "
            "sometimes very big payloads are involved. In order to handle "
            "such payloads it is required to have long timeouts which "
            "allow the service to finish the operation."
        ),
    )
    restart_containers_timeout: PositiveInt = Field(
        1 * _MINUTE, description="timeout of containers restart"
    )

    class Config:
        env_prefix = "SERVICES_COMMON_"
        case_sensitive = False
