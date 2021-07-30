from pydantic import BaseSettings, Field, PositiveInt

_MINUTE = 60
_BASE_TIMEOUT_FOR_STOPPING_SERVICES = 60 * _MINUTE


class ServicesCommonSettings(BaseSettings):
    # set this interval to 1 hour
    director_dynamic_service_save_timeout: PositiveInt = Field(
        _BASE_TIMEOUT_FOR_STOPPING_SERVICES,
        description=(
            "When stopping a dynamic service, if it has "
            "big payloads it is important to have longer timeouts."
        ),
    )
    webserver_director_stop_service_timeout: PositiveInt = Field(
        _BASE_TIMEOUT_FOR_STOPPING_SERVICES + 10,
        description=(
            "When the webserver invokes the director API to stop "
            "a service which has a very long timeout, it also "
            "requires to wait that amount plus some extra padding."
        ),
    )
    storage_service_upload_download_timeout: PositiveInt = Field(
        _MINUTE * _MINUTE,
        description=(
            "When dynamic services upload and download data from storage, "
            "sometimes very big payloads are involved. In order to handle "
            "such payloads it is required to have long timeouts which "
            "allow the service to finish the operation."
        ),
    )

    class Config:
        env_prefix = "SERVICES_COMMON_"
        case_sensitive = False
