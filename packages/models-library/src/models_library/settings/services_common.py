from pydantic import BaseSettings, Field, PositiveInt

_MINUTE = 60
_HOUR = 60 * _MINUTE


class ServicesCommonSettings(BaseSettings):
    # set this interval to 1 hour
    director_dynamic_service_save_timeout: PositiveInt = Field(
        _HOUR,
        description=(
            "When stopping a dynamic service, if it has "
            "big payloads it is important to have longer timeouts."
        ),
    )
    webserver_director_stop_service_timeout: PositiveInt = Field(
        _HOUR + 10,
        description=(
            "The below will try to help explaining what is happening: "
            "webserver -(stop_service)-> director-v* -(save_state)-> service_x"
            "- webserver requests stop_service and uses a 01:00:10 timeout"
            "- director-v* requests save_state and uses a 01:00:00 timeout"
            "The +10 seconds is used to make sure the director replies"
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
